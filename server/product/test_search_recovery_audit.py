"""Offline regression coverage for durable Elasticsearch synchronization."""
import uuid
from unittest.mock import Mock, patch

from celery.exceptions import Retry
from django.conf import settings
from django.db import transaction
from django.test import TestCase, override_settings

from product import search, tasks
from product.models import Product, SearchIndexJob


@override_settings(ELASTICSEARCH_ENABLED=True)
class SearchRecoveryTests(TestCase):
    def test_intents_rollback_with_business_transaction(self) -> None:
        with patch.object(tasks.index_product_task, "apply_async") as publish:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(ValueError):
                    with transaction.atomic():
                        search.schedule_index_product(17)
                        self.assertTrue(SearchIndexJob.objects.exists())
                        raise ValueError("rollback")
            publish.assert_not_called()
        self.assertFalse(SearchIndexJob.objects.exists())

    def test_publish_loss_and_coalescing_keep_latest_intent(self) -> None:
        with patch.object(tasks.index_product_task, "apply_async", side_effect=OSError):
            with self.captureOnCommitCallbacks(execute=True):
                search.schedule_index_product(17)
                first = SearchIndexJob.objects.get().revision
                search.schedule_index_product(17)
        self.assertNotEqual(SearchIndexJob.objects.get().revision, first)
        with patch.object(tasks.index_product_task, "apply_async") as publish:
            self.assertEqual(tasks.recover_search_index_jobs(), 1)
        publish.assert_called_once_with(args=(17,))
        self.assertEqual(SearchIndexJob.objects.count(), 1)

    def test_wrappers_retry_failures_and_only_clear_success(self) -> None:
        cases = [
            (SearchIndexJob.INDEX_PRODUCT, tasks.index_product_task, "index_product"),
            (SearchIndexJob.INDEX_STORE, tasks.index_store_products_task, "index_store_products"),
            (SearchIndexJob.DELETE_PRODUCT, tasks.delete_product_task, "delete_product"),
        ]
        for action, task, operation in cases:
            with self.subTest(action=action):
                SearchIndexJob.objects.create(action=action, target_id=17)
                with patch.object(tasks, operation, side_effect=OSError("offline")):
                    result = task.apply(args=(17,), retries=task.max_retries, throw=False)
                    self.assertTrue(result.failed())
                self.assertTrue(SearchIndexJob.objects.filter(action=action).exists())
                with patch.object(tasks, operation) as execute:
                    task.run(17)
                    execute.assert_called_once_with(17, strict=True)
                self.assertFalse(SearchIndexJob.objects.filter(action=action).exists())
                self.assertEqual(task.retry_backoff, 5)
                self.assertEqual(task.retry_backoff_max, 300)
                self.assertEqual(task.max_retries, 5)

    def test_refresh_during_execution_survives_acknowledgement(self) -> None:
        job = SearchIndexJob.objects.create(action=SearchIndexJob.INDEX_PRODUCT, target_id=17)
        revision = uuid.uuid4()

        def refresh(*args: object, **kwargs: object) -> None:
            SearchIndexJob.objects.filter(pk=job.pk).update(revision=revision)

        with patch.object(tasks, "index_product", side_effect=refresh):
            tasks.index_product_task.run(17)
        self.assertEqual(SearchIndexJob.objects.get().revision, revision)

    def test_worker_failure_requests_bounded_retry(self) -> None:
        SearchIndexJob.objects.create(action=SearchIndexJob.INDEX_PRODUCT, target_id=17)
        with (
            patch.object(tasks, "index_product", side_effect=OSError("offline")),
            patch.object(tasks.index_product_task, "retry", side_effect=Retry()) as retry,
        ):
            with self.assertRaises(Retry):
                tasks.index_product_task.run(17)
        self.assertGreaterEqual(retry.call_args.kwargs["countdown"], 0)
        self.assertLessEqual(retry.call_args.kwargs["countdown"], 300)
        self.assertTrue(SearchIndexJob.objects.exists())

    def test_bulk_partial_failure_preserves_store_intent(self) -> None:
        SearchIndexJob.objects.create(action=SearchIndexJob.INDEX_STORE, target_id=4)
        with (
            patch.object(search, "client"),
            patch.object(search, "ensure_products_index", return_value=True),
            patch("elasticsearch.helpers.bulk", side_effect=RuntimeError("partial bulk failure")),
        ):
            result = tasks.index_store_products_task.apply(args=(4,), retries=5, throw=False)
        self.assertTrue(result.failed())
        self.assertTrue(SearchIndexJob.objects.exists())

    def test_mapping_bad_request_is_not_mistaken_for_success(self) -> None:
        from elasticsearch.exceptions import BadRequestError

        es = Mock()
        es.indices.exists.side_effect = BadRequestError(
            "invalid mapping", meta=Mock(status=400), body={"error": "invalid mapping"}
        )
        with self.assertRaises(BadRequestError):
            search.ensure_products_index(es)

    def test_missing_and_disabled_intents_are_not_executed(self) -> None:
        with patch.object(tasks, "index_product") as execute:
            tasks.index_product_task.run(17)
            execute.assert_not_called()
            SearchIndexJob.objects.create(action=SearchIndexJob.INDEX_PRODUCT, target_id=17)
            with override_settings(ELASTICSEARCH_ENABLED=False):
                tasks.index_product_task.run(17)
                self.assertEqual(tasks.recover_search_index_jobs(), 0)
                search.schedule_index_product(18)
            execute.assert_not_called()
        self.assertEqual(SearchIndexJob.objects.count(), 1)

    def test_recovery_is_bounded_and_failed_batch_does_not_starve(self) -> None:
        for target in range(105):
            SearchIndexJob.objects.create(action=SearchIndexJob.INDEX_PRODUCT, target_id=target)
        with patch.object(tasks.index_product_task, "apply_async", side_effect=OSError) as publish:
            self.assertEqual(tasks.recover_search_index_jobs(limit=1000), 0)
            self.assertEqual(publish.call_count, 100)
        with patch.object(tasks.index_product_task, "apply_async") as publish:
            self.assertEqual(tasks.recover_search_index_jobs(limit=5), 5)
            self.assertEqual([call.kwargs["args"][0] for call in publish.call_args_list], list(range(100, 105)))
        self.assertEqual(SearchIndexJob.objects.count(), 105)

    def test_deleted_product_index_intent_deletes_obsolete_document(self) -> None:
        SearchIndexJob.objects.create(action=SearchIndexJob.INDEX_PRODUCT, target_id=17)
        with patch.object(search, "client") as client:
            tasks.index_product_task.run(17)
        client.return_value.delete.assert_called_once_with(
            index=settings.ELASTICSEARCH_PRODUCTS_INDEX, id=17, ignore=[404]
        )
        self.assertFalse(SearchIndexJob.objects.exists())

    def test_deleted_product_delete_failure_preserves_index_intent(self) -> None:
        SearchIndexJob.objects.create(action=SearchIndexJob.INDEX_PRODUCT, target_id=17)
        with patch.object(search, "client", side_effect=OSError):
            result = tasks.index_product_task.apply(args=(17,), retries=5, throw=False)
        self.assertTrue(result.failed())
        self.assertTrue(SearchIndexJob.objects.exists())

    def test_helpers_propagate_in_strict_mode_and_log_in_cli_mode(self) -> None:
        for operation in (search.index_store_products, search.delete_product):
            with self.subTest(operation=operation.__name__):
                with patch.object(search, "client", side_effect=OSError):
                    operation(17)
                    with self.assertRaises(OSError):
                        operation(17, strict=True)
        with patch.object(Product.objects, "select_related", side_effect=OSError):
            search.index_product(17)
            with self.assertRaises(OSError):
                search.index_product(17, strict=True)

    def test_beat_routes_recovery_to_worker_queue(self) -> None:
        name = "product.tasks.recover_search_index_jobs"
        self.assertEqual(settings.CELERY_TASK_ROUTES[name]["queue"], settings.CELERY_TASK_DEFAULT_QUEUE)
        self.assertEqual(settings.CELERY_BEAT_SCHEDULE["recover-search-index-jobs"]["task"], name)
