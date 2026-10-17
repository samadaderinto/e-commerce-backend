from typing import Any
from types import SimpleNamespace
from unittest.mock import Mock, patch

from decimal import Decimal
from unittest.mock import patch

from django.db import transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.models import User
from product.models import Product
from store.models import Store

import product.search as search_module
from product.search import (
    ensure_products_index,
    product_document,
    schedule_delete_product,
    schedule_index_product,
    schedule_index_store_products,
    search_product_ids,
)


@override_settings(
    ELASTICSEARCH_ENABLED=True,
    ELASTICSEARCH_PRODUCTS_INDEX='commerce-products-test',
)
class ProductSearchIndexTests(SimpleTestCase):
    def setUp(self) -> None:
        self.previous_mapped_indices = set(search_module._mapped_text_indices)
        search_module._mapped_text_indices.clear()
        self.addCleanup(self._restore_mapped_indices)

    def _restore_mapped_indices(self) -> None:
        search_module._mapped_text_indices.clear()
        search_module._mapped_text_indices.update(self.previous_mapped_indices)

    def test_existing_index_gets_analyzed_category_and_tag_fields(self) -> None:
        elasticsearch = Mock()
        elasticsearch.indices.exists.return_value = True

        self.assertTrue(ensure_products_index(elasticsearch))

        elasticsearch.indices.put_mapping.assert_called_once_with(
            index='commerce-products-test',
            properties={
                'category_text': {'type': 'text'},
                'tags_text': {'type': 'text'},
            },
        )

    def test_product_documents_include_analyzed_category_and_tag_text(self) -> None:
        product = SimpleNamespace(
            id=17,
            title='Studio Headphones',
            description='Wireless audio equipment',
            brand='ProAce',
            category='electronics',
            store_id=4,
            store=SimpleNamespace(status='active', verified_at=object()),
            visibility=True,
            price=12.50,
            discount=0,
            available=3,
            average_rating=4.5,
            sales=8,
            sponsored=False,
            tags=SimpleNamespace(all=lambda: [SimpleNamespace(name='studio audio')]),
            created=None,
        )

        document = product_document(product)

        self.assertEqual(document['category_text'], 'electronics')
        self.assertEqual(document['tags_text'], ['studio audio'])

    @patch('product.search.client')
    def test_search_requires_all_terms_across_analyzed_catalog_fields(
        self, get_client: Mock
    ) -> None:
        elasticsearch = Mock()
        elasticsearch.search.return_value = {
            'hits': {
                'hits': [{'_id': '17'}],
                'total': {'value': 1},
            },
        }
        get_client.return_value = elasticsearch

        result = search_product_ids('electronics studio', limit=12)

        self.assertEqual(result, {'ids': [17], 'count': 1})
        request: dict[str, Any] = elasticsearch.search.call_args.kwargs
        must = request['query']['bool']['must']
        self.assertEqual(len(must), 2)
        multi_match = must[0]['multi_match']
        self.assertEqual(multi_match['fuzziness'], 'AUTO')
        self.assertIn('category_text^2', multi_match['fields'])
        self.assertIn('tags_text^2', multi_match['fields'])
        self.assertEqual(
            request['sort'],
            [{'_score': 'desc'}, {'created': 'desc'}, {'id': 'desc'}],
        )
        self.assertFalse(request['source'])
        self.assertFalse(request['request_cache'])

    @patch('product.search.client')
    def test_request_cache_opt_in_preserves_filters_order_and_page(
        self, get_client: Mock
    ) -> None:
        elasticsearch = get_client.return_value
        elasticsearch.search.return_value = {'hits': {'hits': [], 'total': {'value': 0}}}
        filters = {'category': 'audio', 'store_id': 4, 'deals': True,
                   'min_price': Decimal('10'), 'max_price': Decimal('50')}
        search_product_ids('wireless headphones', filters=filters, ordering='price',
                           offset=24, limit=24, use_request_cache=True)
        request = elasticsearch.search.call_args.kwargs
        self.assertTrue(request['request_cache'])
        self.assertFalse(request['source'])
        self.assertTrue(request['track_total_hits'])
        self.assertEqual(request['from_'], 24)
        self.assertEqual(request['sort'], [{'price': 'asc'}, {'id': 'desc'}])
        self.assertIn({'term': {'store_id': 4}}, request['query']['bool']['filter'])
        self.assertIn({'range': {'price': {'gte': 10, 'lte': 50}}}, request['query']['bool']['filter'])
        with override_settings(SEARCH_REQUEST_CACHE_ENABLED=False):
            search_product_ids('wireless headphones', use_request_cache=True)
        self.assertFalse(elasticsearch.search.call_args.kwargs['request_cache'])

    @patch('product.search.client')
    def test_partial_and_malformed_search_results_use_fallback(self, get_client: Mock) -> None:
        for result in (
            {'timed_out': True},
            {'_shards': {'failed': 1}},
            {'hits': {'hits': [{'_id': 'invalid'}], 'total': {'value': 1}}},
        ):
            get_client.return_value.search.return_value = result
            self.assertIsNone(search_product_ids('headphones'))
        self.assertFalse(get_client.return_value.search.call_args.kwargs['allow_partial_search_results'])

    @patch('elasticsearch.Elasticsearch')
    def test_connection_pool_is_bounded_configurable_and_reused(self, constructor: Mock) -> None:
        search_module._reset_client_after_fork()
        self.addCleanup(search_module._reset_client_after_fork)
        with override_settings(ELASTICSEARCH_CONNECTIONS_PER_NODE=32):
            first = search_module.client()
            self.assertIs(search_module.client(), first)
            self.assertEqual(constructor.call_count, 1)
            self.assertEqual(constructor.call_args.kwargs['connections_per_node'], 32)
        with override_settings(ELASTICSEARCH_CONNECTIONS_PER_NODE=16):
            search_module.client()
            self.assertEqual(constructor.call_count, 2)
            self.assertEqual(constructor.call_args.kwargs['connections_per_node'], 16)
            first.close.assert_called_once()


@override_settings(ELASTICSEARCH_ENABLED=True)
class StoreSearchIndexSignalTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            email='store-search@test.com', password='test-password'
        )
        self.store = Store.objects.create(
            user=self.owner,
            name='Search store',
            status=Store.STATUS_PENDING,
        )
        Product.objects.create(
            store=self.store,
            title='Rolex Oyster Perpetual',
            description='A watch listing',
            price=Decimal('100.00'),
            discount=0,
            available=1,
            category='jewelry',
        )

    @patch('product.signals.schedule_index_store_products')
    def test_store_search_eligibility_changes_schedule_reindex_after_commit(
        self, schedule_reindex: Mock
    ) -> None:
        self.store.status = Store.STATUS_ACTIVE
        self.store.verified_at = timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            self.store.save(update_fields=['status', 'verified_at'])

        schedule_reindex.assert_called_once_with(self.store.pk)

    @patch('product.signals.schedule_index_store_products')
    def test_unrelated_store_edits_do_not_reindex_products(
        self, schedule_reindex: Mock
    ) -> None:
        self.store.name = 'Renamed search store'
        with self.captureOnCommitCallbacks(execute=True):
            self.store.save(update_fields=['name'])

        schedule_reindex.assert_not_called()

    def test_search_index_work_is_enqueued_after_commit(self) -> None:
        with (
            patch('product.tasks.index_product_task.apply_async') as index_product_task,
            patch('product.tasks.index_store_products_task.apply_async') as index_store_task,
            patch('product.tasks.delete_product_task.apply_async') as delete_product_task,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    schedule_index_product(17)
                    schedule_index_store_products(4)
                    schedule_delete_product(17)
                    index_product_task.assert_not_called()
                    index_store_task.assert_not_called()
                    delete_product_task.assert_not_called()

            index_product_task.assert_called_once_with(args=(17,))
            index_store_task.assert_called_once_with(args=(4,))
            delete_product_task.assert_called_once_with(args=(17,))
