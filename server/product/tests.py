from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import ValidationError

from core.models import Review, User, Wishlist
from product.models import Product
from product.serializers import ProductSerializer
from store.models import Store
from utils.exceptions import custom_exception_handler


class ProductInteractionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="password",
            first_name="Buyer",
            last_name="One",
            gender="male",
            phone1="+2348012345678",
        )
        self.merchant = User.objects.create_user(
            email="merchant@example.com",
            password="password",
            first_name="Merchant",
            last_name="One",
            gender="female",
            phone1="+2348012345679",
        )
        self.store = Store.objects.create(
            user=self.merchant, username="merchant-store", name="Merchant Store"
        )
        self.product = Product.objects.create(
            store=self.store,
            title="Noise cancelling headphones",
            description="Comfortable wireless headphones",
            price=Decimal("120.00"),
            discount=10,
            available=8,
            category="electronics",
            visibility=True,
        )

    def test_wishlist_uniqueness_and_product_like_metadata(self):
        request = self.factory.post("/users/wishlist/add/", {}, format="json")
        request.user = self.user

        Wishlist.objects.create(user=self.user, product=self.product)
        self.assertEqual(Wishlist.objects.count(), 1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Wishlist.objects.create(user=self.user, product=self.product)
        self.assertEqual(Wishlist.objects.count(), 1)

        data = ProductSerializer(
            self.product, context={"request": request}
        ).data
        self.assertEqual(data["likes_count"], 1)
        self.assertTrue(data["is_liked"])

    def test_wishlist_delete_unlikes_product(self):
        wishlist = Wishlist.objects.create(user=self.user, product=self.product)
        wishlist.delete()
        self.assertFalse(Wishlist.objects.exists())

    def test_review_creation_updates_product_average_rating(self):
        payload = {
            "user": self.user.pk,
            "product": self.product.pk,
            "label": "Solid",
            "comment": "Great",
            "rating": 4,
        }
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            label=payload["label"],
            comment=payload["comment"],
            rating=payload["rating"],
        )
        review.set_avg_rating()
        self.product.refresh_from_db()
        self.assertEqual(self.product.average_rating, Decimal("4.00"))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(
                    user=self.user,
                    product=self.product,
                    label=payload["label"],
                    comment=payload["comment"],
                    rating=payload["rating"],
                )
        self.assertEqual(Review.objects.count(), 1)


class ApiExceptionHandlerTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_validation_errors_use_consistent_error_envelope(self):
        request = self.factory.post("/products/", {}, format="json")
        response = custom_exception_handler(
            ValidationError({"title": ["This field is required."]}),
            {"request": request, "view": None},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "invalid")
        self.assertEqual(response.data["error"]["message"], "Request validation failed.")
        self.assertEqual(
            response.data["error"]["details"]["title"],
            ["This field is required."],
        )

    def test_unhandled_errors_are_logged_and_hidden(self):
        request = self.factory.get("/products/")
        with self.assertLogs("codematics.api", level="ERROR"):
            response = custom_exception_handler(
                RuntimeError("database exploded"),
                {"request": request, "view": None},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"]["code"], "server_error")
        self.assertEqual(response.data["error"]["message"], "An unexpected error occurred.")
