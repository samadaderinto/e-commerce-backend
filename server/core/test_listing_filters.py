from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User, UserWallet, UserWalletTransaction
from payment.models import Order
from staff.models import PlatformCommissionWithdrawal
from store.models import MerchantWallet, Store, StoreEarningsLedger, StorePayout


@override_settings(ROOT_URLCONF="storefront.urls")
class CollectionFilteringTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(email="filter-admin@example.com", password="test-password")
        self.owner = User.objects.create_user(email="filter-owner@example.com", password="test-password")
        self.other = User.objects.create_user(email="filter-other@example.com", password="test-password")
        self.store = Store.objects.create(user=self.owner, name="Filter store", username="filter-store", status="active")
        self.other_store = Store.objects.create(user=self.other, name="Other store", username="filter-other", status="active")
        self.wallet = MerchantWallet.objects.create(user=self.owner)
        self.client = APIClient()

    def test_payout_search_combined_filters_before_pagination(self) -> None:
        self.client.force_authenticate(self.admin)
        for index in range(25):
            StorePayout.objects.create(store=self.store, wallet=self.wallet, reference=f"SEARCH-{index}", amount=Decimal("25"))
        target = StorePayout.objects.create(
            store=self.store, wallet=self.wallet, reference="LATE-TARGET",
            amount=Decimal("70"), status="completed", payout_method="stripe_connect",
        )
        # Keep target older than the first unfiltered page.
        StorePayout.objects.filter(pk=target.pk).update(created=timezone.now() - timedelta(days=2))
        params = {
            "search": "LATE", "status": "completed", "payout_method": "stripe_connect",
            "min_amount": "60", "max_amount": "80",
            "start_date": (timezone.now() - timedelta(days=3)).date().isoformat(),
            "end_date": timezone.now().date().isoformat(), "limit": 1,
        }
        response = self.client.get("/api/v1/admin/staff/payouts/", params)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], target.pk)
        self.assertEqual(self.client.get("/api/v1/admin/staff/payouts/", {"offset": 20}).data["count"], 26)
        for invalid in [{"min_amount": "80", "max_amount": "60"}, {"status": "unknown"}, {"offset": -1}, {"start_date": "invalid"}]:
            self.assertEqual(self.client.get("/api/v1/admin/staff/payouts/", invalid).status_code, 400)

    def test_merchant_finance_filters_preserve_store_scope(self) -> None:
        self.client.force_authenticate(self.owner)
        target = StorePayout.objects.create(store=self.store, wallet=self.wallet, reference="SCOPE", amount=10)
        StorePayout.objects.create(store=self.other_store, reference="SCOPE", amount=10)
        response = self.client.get(f"/api/v1/stores/{self.store.pk}/payouts/", {"paginated": "1", "search": "SCOPE", "payout_method": "bank_transfer"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], target.pk)
        for index in range(55):
            StoreEarningsLedger.objects.create(wallet=self.wallet, store=self.store, reference=f"LEDGER-{index}", net_amount=10)
        response = self.client.get("/api/v1/stores/wallet/ledger/", {"store_id": self.store.pk, "search": "LEDGER", "entry_type": "sale", "offset": 50})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 55)
        self.assertEqual(len(response.data["results"]), 5)
        foreign = self.client.get("/api/v1/stores/wallet/ledger/", {"store_id": self.other_store.pk})
        self.assertEqual(foreign.data["count"], 0)

    def test_customer_history_pages_preserve_balance_and_ownership(self) -> None:
        self.client.force_authenticate(self.owner)
        for _ in range(105):
            Order.objects.create(user=self.owner, ordered=True, status="pending", total=10)
        Order.objects.create(user=self.other, ordered=True, status="pending", total=10)
        response = self.client.get("/api/v1/orders/", {"paginated": "1", "status": "pending", "offset": 100})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 105)
        self.assertEqual(len(response.data["results"]), 5)
        wallet = UserWallet.objects.create(user=self.owner, balance=Decimal("90"))
        for _ in range(35):
            UserWalletTransaction.objects.create(wallet=wallet, transaction_type="credit", amount=5, source="deposit", description="Funding")
        response = self.client.get("/api/v1/wallet/", {"search": "Funding", "transaction_type": "credit", "source": "deposit", "offset": 30})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 35)
        self.assertEqual(len(response.data["transactions"]), 5)
        self.assertEqual(response.data["balance"], "90.00")
        response = self.client.get("/api/v1/wallet/", {"source": "refund"})
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["balance"], "90.00")

    def test_treasury_history_filters_do_not_change_totals(self) -> None:
        self.client.force_authenticate(self.admin)
        for index in range(55):
            PlatformCommissionWithdrawal.objects.create(requested_by=self.admin, amount=1, payout_method="bank", status="completed", reference=f"TREASURY-{index}")
        url = "/api/v1/admin/staff/commission-wallet/"
        baseline = self.client.get(url).data
        response = self.client.get(url, {"search": "TREASURY", "status": "completed", "offset": 50})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["withdrawal_count"], 55)
        self.assertEqual(len(response.data["withdrawals"]), 5)
        for key in ["earned", "withdrawn_or_pending", "available"]:
            self.assertEqual(response.data[key], baseline[key])
