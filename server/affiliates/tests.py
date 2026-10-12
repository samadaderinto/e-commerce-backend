from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from affiliates.models import AffiliateWallet, Marketer, Referral
from affiliates.services import reward_referral
from core.models import User
from storefront.views import AuthView


class AffiliateReferralTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            email="referrer@test.com",
            password="Strong-test-password-123",
            first_name="Ref",
            last_name="Errer",
            gender="male",
            phone1="+2348012345678",
        )
        self.marketer = Marketer.objects.create(user=self.referrer, name="Referrer")

    def test_reward_referral_adds_25_to_referrer_wallet(self):
        referred = User.objects.create_user(
            email="referred@test.com",
            password="Strong-test-password-123",
            first_name="New",
            last_name="User",
            gender="female",
            phone1="+2348012345679",
        )

        referral = reward_referral(self.marketer.marketer_id, referred)

        wallet = AffiliateWallet.objects.get(user=self.referrer)
        self.assertIsNotNone(referral)
        self.assertEqual(wallet.balance, Decimal("25.00"))
        self.assertEqual(wallet.transactions.count(), 1)
        self.assertEqual(referral.status, Referral.REWARDED)
        self.assertEqual(referral.reward_amount, Decimal("25.00"))

        # Verify Option A: The user's primary UserWallet was credited with $25.00 store credit
        from core.models import UserWallet, UserWalletTransaction
        user_wallet = UserWallet.objects.get(user=self.referrer)
        self.assertEqual(user_wallet.balance, Decimal("25.00"))
        self.assertEqual(user_wallet.transactions.filter(source=UserWalletTransaction.SOURCE_REFERRAL).count(), 1)

    def test_reward_referral_capped_at_four_users(self):
        # Create and reward 4 users ($100 total)
        for i in range(1, 5):
            u = User.objects.create_user(
                email=f"user{i}@test.com",
                password="Strong-test-password-123",
                first_name=f"User{i}",
                last_name="Test",
                gender="male",
                phone1=f"+234801234568{i}",
            )
            reward_referral(self.marketer.marketer_id, u)

        from core.models import UserWallet
        user_wallet = UserWallet.objects.get(user=self.referrer)
        affiliate_wallet = AffiliateWallet.objects.get(user=self.referrer)
        self.assertEqual(user_wallet.balance, Decimal("100.00"))
        self.assertEqual(affiliate_wallet.balance, Decimal("100.00"))
        self.assertEqual(Referral.objects.filter(marketer=self.marketer, status=Referral.REWARDED).count(), 4)

        # 5th referred user is capped (status pending, no extra $25 credited)
        u5 = User.objects.create_user(
            email="user5@test.com",
            password="Strong-test-password-123",
            first_name="User5",
            last_name="Test",
            gender="female",
            phone1="+2348012345699",
        )
        ref5 = reward_referral(self.marketer.marketer_id, u5)
        self.assertEqual(ref5.status, Referral.PENDING)

        user_wallet.refresh_from_db()
        affiliate_wallet.refresh_from_db()
        self.assertEqual(user_wallet.balance, Decimal("100.00"))
        self.assertEqual(affiliate_wallet.balance, Decimal("100.00"))

    def test_reward_referral_is_idempotent_for_same_referred_user(self):
        referred = User.objects.create_user(
            email="duplicate@test.com",
            password="Strong-test-password-123",
            first_name="Dupe",
            last_name="User",
            gender="female",
            phone1="+2348012345680",
        )

        first = reward_referral(self.marketer.marketer_id, referred)
        second = reward_referral(self.marketer.marketer_id, referred)

        wallet = AffiliateWallet.objects.get(user=self.referrer)
        self.assertEqual(first, second)
        self.assertEqual(wallet.balance, Decimal("25.00"))
        self.assertEqual(wallet.transactions.count(), 1)

    def test_user_cannot_reward_their_own_referral_code(self):
        referral = reward_referral(self.marketer.marketer_id, self.referrer)

        self.assertIsNone(referral)
        self.assertFalse(AffiliateWallet.objects.filter(user=self.referrer).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AffiliateRegistrationTests(TestCase):
    def test_registration_with_referral_code_rewards_referrer(self):
        referrer = User.objects.create_user(
            email="owner@test.com",
            password="Strong-test-password-123",
            first_name="Owner",
            last_name="Account",
            gender="male",
            phone1="+2348012345681",
        )
        marketer = Marketer.objects.create(user=referrer, name="Owner")
        factory = APIRequestFactory()

        request = factory.post(
            "/api/v1/auth/register/",
            {
                "email": "new-referred@test.com",
                "first_name": "New",
                "last_name": "Customer",
                "phone1": "+2348012345682",
                "password": "Strong-new-password-123",
                "referral_code": marketer.marketer_id,
            },
            format="json",
        )
        response = AuthView.as_view()(request, action="register")

        self.assertEqual(response.status_code, 201, response.data)
        # Deferred until email verification to protect against unverified email abuse
        self.assertFalse(AffiliateWallet.objects.filter(user=referrer).exists())
        self.assertEqual(Referral.objects.count(), 0)

        # Parse verification token from queued delivery
        from notification.models import NotificationDelivery
        import re
        delivery = NotificationDelivery.objects.get(recipient_email="new-referred@test.com")
        match = re.search(r"token=([^\s\"'>]+)", delivery.body)
        self.assertIsNotNone(match)
        token = match.group(1)

        # Verify email
        verify_req = factory.post(
            "/api/v1/auth/verify/",
            {"token": token},
            format="json",
        )
        verify_resp = AuthView.as_view()(verify_req, action="verify")
        self.assertEqual(verify_resp.status_code, 200, verify_resp.data)

        self.assertEqual(AffiliateWallet.objects.get(user=referrer).balance, Decimal("25.00"))
        self.assertEqual(Referral.objects.count(), 1)


class ClickBankOutboundTests(TestCase):
    def setUp(self):
        from store.models import Store
        from product.models import Product
        self.user = User.objects.create_user(
            email="vendor@test.com",
            password="Strong-test-password-123",
            first_name="Vendor",
            last_name="Owner",
            gender="male",
            phone1="+2348012345683",
        )
        from django.utils import timezone

        self.store = Store.objects.create(name="Affiliate Partner Hub", username="affiliate-hub", user=self.user, status=Store.STATUS_ACTIVE, is_official=True, verified_at=timezone.now())
        self.affiliate_product = Product.objects.create(
            store=self.store,
            title="Keto Diet Masterclass",
            description="Comprehensive guide to ketogenic lifestyle.",
            price=Decimal("47.00"),
            discount=0,
            available=999,
            category="beverages",
            product_type="affiliate_clickbank",
            affiliate_hoplink="https://hop.clickbank.net/?affiliate=proace&vendor=ketomaster",
            affiliate_vendor_nickname="ketomaster",
            affiliate_button_text="Get Keto Masterclass",
        )
        self.standard_product = Product.objects.create(
            store=self.store,
            title="Standard ProAce Protein",
            description="Whey protein powder.",
            price=Decimal("30.00"),
            discount=0,
            available=10,
            category="sports",
            product_type="standard",
        )

    def test_outbound_redirect_generates_tid_and_records_click(self):
        from affiliates.models import ClickBankOutboundClick
        factory = APIRequestFactory()
        from affiliates.views import AffiliatesViewSet
        view = AffiliatesViewSet.as_view({"get": "clickbank_outbound"})

        request = factory.get(f"/affiliate/clickbank/outbound/{self.affiliate_product.id}/")
        response = view(request, product_id=self.affiliate_product.id)

        self.assertEqual(response.status_code, 302)
        redirect_url = response["Location"]
        self.assertIn("hop.clickbank.net", redirect_url)
        self.assertIn("tid=cb_guest_", redirect_url)

        click = ClickBankOutboundClick.objects.get(product=self.affiliate_product)
        self.assertTrue(click.tracking_id.startswith("cb_guest_"))
        self.assertEqual(click.hoplink_used, redirect_url)

    @override_settings(CLICKBANK_AFFILIATE_NICKNAME="customproace")
    def test_outbound_redirect_injects_affiliate_nickname_from_settings(self):
        from affiliates.views import AffiliatesViewSet
        from product.models import Product
        p = Product.objects.create(
            store=self.store,
            title="Affiliate Without Aff Query",
            description="Testing nickname injection.",
            price=Decimal("19.00"),
            discount=0,
            available=999,
            category="beverages",
            product_type="affiliate_clickbank",
            affiliate_hoplink="https://hop.clickbank.net/?vendor=supervendor",
        )
        factory = APIRequestFactory()
        view = AffiliatesViewSet.as_view({"get": "clickbank_outbound"})
        request = factory.get(f"/affiliate/clickbank/outbound/{p.id}/")
        response = view(request, product_id=p.id)
        self.assertEqual(response.status_code, 302)
        redirect_url = response["Location"]
        self.assertIn("affiliate=customproace", redirect_url)
        self.assertIn("vendor=supervendor", redirect_url)
        self.assertIn("tid=cb_guest_", redirect_url)

    def test_cart_rejects_affiliate_clickbank_product(self):
        from cart.views import CartViewSet
        from rest_framework.test import force_authenticate
        factory = APIRequestFactory()
        view = CartViewSet.as_view({"post": "add_to_cart"})

        request = factory.post("/cart/add/", {"product": self.affiliate_product.id, "quantity": 1}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("fulfilled directly by our partner", response.data["message"])

    def test_merchant_product_serializer_affiliate_validation(self):
        from store.serializers import MerchantProductSerializer
        # 1. Missing hoplink fails
        invalid_data = {
            "title": "Affiliate Guide",
            "description": "A guide.",
            "price": "19.99",
            "category": "books",
            "product_type": "affiliate_clickbank",
            "affiliate_hoplink": "",
        }
        serializer = MerchantProductSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("affiliate_hoplink", serializer.errors)

        # 2. Invalid URL scheme fails
        invalid_data["affiliate_hoplink"] = "javascript:alert(1)"
        serializer = MerchantProductSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("affiliate_hoplink", serializer.errors)

        # 3. Valid hoplink succeeds and defaults inventory & weight
        valid_data = {
            "title": "Affiliate Guide",
            "description": "A guide.",
            "price": "19.99",
            "category": "books",
            "product_type": "affiliate_clickbank",
            "affiliate_hoplink": "https://hop.clickbank.net/?affiliate=proace&vendor=test",
            "affiliate_vendor_nickname": "test",
            "affiliate_button_text": "Buy Guide",
        }
        serializer = MerchantProductSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        validated = serializer.validated_data
        self.assertEqual(validated["product_type"], "affiliate_clickbank")
        self.assertEqual(validated["weight"], Decimal("0.00"))
        self.assertEqual(validated["available"], 999)
        self.assertEqual(validated["variants"], [])

    def test_staff_store_products_audit_includes_affiliate_fields_and_filters(self):
        from staff.views import StaffViewSet
        from rest_framework.test import force_authenticate
        staff_user = User.objects.create_user(
            email="staff-test@test.com",
            password="Strong-test-password-123",
            first_name="Staff",
            last_name="Auditor",
            gender="male",
            phone1="+2348012345689",
            is_staff=True,
        )
        factory = APIRequestFactory()
        view = StaffViewSet.as_view({"get": "store_products"})

        # Query with product_type=affiliate_clickbank
        request = factory.get(f"/admin/staff/stores/{self.store.id}/products/?product_type=affiliate_clickbank")
        force_authenticate(request, user=staff_user)
        response = view(request, store_pk=self.store.id)

        self.assertEqual(response.status_code, 200)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item["id"], self.affiliate_product.id)
        self.assertEqual(item["product_type"], "affiliate_clickbank")
        self.assertEqual(item["affiliate_vendor_nickname"], "ketomaster")
        self.assertIn("hop.clickbank.net", item["affiliate_hoplink"])

    def test_non_official_store_cannot_create_affiliate_clickbank_product(self):
        from store.views import MerchantProductViewSet
        from rest_framework.test import force_authenticate
        from store.models import Store
        non_official = Store.objects.create(name="Regular Seller", username="regular-seller", user=self.user, status=Store.STATUS_ACTIVE, is_official=False)

        factory = APIRequestFactory()
        view = MerchantProductViewSet.as_view({"post": "create"})
        request = factory.post(f"/stores/{non_official.id}/products/", {
            "title": "Unauthorized Affiliate Deal",
            "description": "Some description.",
            "price": "29.99",
            "category": "books",
            "product_type": "affiliate_clickbank",
            "affiliate_hoplink": "https://hop.clickbank.net/?affiliate=proace&vendor=test",
        }, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, store_pk=non_official.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("official platform catalog stores", str(response.data))

    def test_storefront_store_filter_excludes_affiliate_products_for_non_official_store(self):
        from storefront.views import ProductsView
        from store.models import Store
        from django.utils import timezone
        regular_store = Store.objects.create(name="Local Merchant", username="local-merchant", user=self.user, status=Store.STATUS_ACTIVE, verified_at=timezone.now(), is_official=False)
        from product.models import Product
        # Standard product owned by merchant
        p_std = Product.objects.create(
            store=regular_store,
            title="Local Handmade Candle",
            description="Nice candle.",
            price=Decimal("15.00"),
            discount=0,
            available=20,
            category="sports",
            product_type="standard",
            visibility=True,
        )
        # Even if an affiliate item had regular_store foreign key
        p_aff = Product.objects.create(
            store=regular_store,
            title="External Guide",
            description="Guide.",
            price=Decimal("10.00"),
            discount=0,
            available=999,
            category="books",
            product_type="affiliate_clickbank",
            affiliate_hoplink="https://hop.clickbank.net/?affiliate=proace&vendor=test",
            visibility=True,
        )

        factory = APIRequestFactory()
        view = ProductsView.as_view()
        request = factory.get(f"/products/?store={regular_store.id}")
        response = view(request)

        self.assertEqual(response.status_code, 200)
        product_ids = [item["id"] for item in (response.data["results"] if "results" in response.data else response.data)]
        self.assertIn(p_std.id, product_ids)
        self.assertNotIn(p_aff.id, product_ids)

    def test_affiliate_clickbank_product_sale_price_never_discounts(self):
        from product.models import Product
        p_aff = Product.objects.create(
            store=self.store,
            title="Keto Diet Plan",
            description="Guide.",
            price=Decimal("49.99"),
            discount=25,
            available=999,
            category="books",
            product_type=Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK,
            affiliate_hoplink="https://hop.clickbank.net/?affiliate=proace&vendor=test",
            visibility=True,
        )
        self.assertEqual(p_aff.sale_price, "49.99")

    def test_merchant_product_serializer_rejects_discount_and_flash_sale_for_clickbank(self):
        from store.serializers import MerchantProductSerializer
        from django.utils import timezone
        data = {
            "title": "Discounted Affiliate Guide",
            "description": "Some description.",
            "price": "39.99",
            "discount": 20,
            "category": "books",
            "product_type": "affiliate_clickbank",
            "affiliate_hoplink": "https://hop.clickbank.net/?affiliate=proace&vendor=test",
        }
        serializer = MerchantProductSerializer(data=data, context={"store": self.store})
        self.assertFalse(serializer.is_valid())
        self.assertIn("discount", serializer.errors)

        data_flash = {
            "title": "Flash Affiliate Guide",
            "description": "Some description.",
            "price": "39.99",
            "discount": 0,
            "flash_sale_end": timezone.now().isoformat(),
            "category": "books",
            "product_type": "affiliate_clickbank",
            "affiliate_hoplink": "https://hop.clickbank.net/?affiliate=proace&vendor=test",
        }
        serializer_flash = MerchantProductSerializer(data=data_flash, context={"store": self.store})
        self.assertFalse(serializer_flash.is_valid())
        self.assertIn("flash_sale_end", serializer_flash.errors)

    def test_coupon_admin_serializer_rejects_clickbank_product(self):
        from storefront.serializers import CouponAdminSerializer
        from payment.models import Coupon
        from django.utils import timezone
        data = {
            "code": "CLICK20",
            "discount": 20,
            "coupon_type": Coupon.PRODUCT,
            "product": self.affiliate_product.id,
            "valid_from": timezone.now(),
            "valid_to": timezone.now() + timezone.timedelta(days=7),
            "num_available": 10,
        }
        serializer = CouponAdminSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("product", serializer.errors)
        self.assertIn("ClickBank affiliate partner products", str(serializer.errors["product"]))
