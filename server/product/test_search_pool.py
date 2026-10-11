"""Ensure network pools are shared across threads but isolated across processes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from product import search


@override_settings(ELASTICSEARCH_URL="http://search.test:9200", ELASTICSEARCH_TIMEOUT=2)
class SearchPoolTests(SimpleTestCase):
    def setUp(self) -> None:
        self.state = patch.multiple(
            search,
            _client_instance=None,
            _client_config=None,
            _client_lock=Lock(),
        )
        self.state.start()
        self.addCleanup(self.state.stop)

    @patch("elasticsearch.Elasticsearch")
    def test_concurrent_threads_construct_one_shared_pool(
        self, constructor: MagicMock
    ) -> None:
        barrier = Barrier(8)

        def connect() -> object:
            barrier.wait(timeout=5)
            return search.client()

        with ThreadPoolExecutor(max_workers=8) as executor:
            clients = list(executor.map(lambda _: connect(), range(8)))
        self.assertTrue(all(value is clients[0] for value in clients))
        constructor.assert_called_once()

    @patch("elasticsearch.Elasticsearch")
    def test_new_process_never_reuses_inherited_pool(self, constructor: MagicMock) -> None:
        with patch("product.search.os.getpid", return_value=100):
            first = search.client()
        with patch("product.search.os.getpid", return_value=200):
            search.client()
        self.assertEqual(constructor.call_count, 2)
        first.close.assert_not_called()

    @patch("elasticsearch.Elasticsearch")
    def test_settings_change_closes_replaced_local_pool(
        self, constructor: MagicMock
    ) -> None:
        first = search.client()
        with override_settings(ELASTICSEARCH_URL="http://replacement.test:9200"):
            search.client()
        first.close.assert_called_once()
        self.assertEqual(constructor.call_count, 2)

    @patch("elasticsearch.Elasticsearch")
    def test_fork_hook_resets_pool_and_lock(self, constructor: MagicMock) -> None:
        search.client()
        inherited_lock = search._client_lock
        inherited_lock.acquire()
        search._reset_client_after_fork()
        try:
            search.client()
            self.assertIsNot(search._client_lock, inherited_lock)
            self.assertEqual(constructor.call_count, 2)
        finally:
            inherited_lock.release()
