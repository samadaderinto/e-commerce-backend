from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from cart.models import Cart, CartItem
from cart.views import CartViewSet
from core.models import User
from product.models import Product
from store.models import Store


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "cart-tests",
        }
    }
)
class CartViewSetTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="password123",
            first_name="Ada",
            last_name="Buyer",
            gender="female",
            phone1="+12015550123",
        )
        self.seller = User.objects.create_user(
            email="seller@example.com",
            password="password123",
            first_name="Sam",
            last_name="Seller",
            gender="male",
            phone1="+12015550124",
        )
        self.store = Store.objects.create(
            user=self.seller,
            username="seller-store",
            name="Seller Store",
        )
        self.product = Product.objects.create(
            store=self.store,
            title="Bluetooth Speaker",
            description="Portable speaker",
            price=Decimal("25000.00"),
            discount=10,
            available=5,
            category="electronics",
        )

    def view(self, method, action):
        def authenticated_view(request):
            force_authenticate(request, user=self.user)
            return CartViewSet.as_view({method: action})(request)
        return authenticated_view

    def test_owner_cannot_add_own_product_by_submitting_another_user(self):
        self.store.user = self.user
        self.store.save()
        request = self.factory.post('/cart/add/', {'user': self.seller.pk, 'product': self.product.pk}, format='json')
        response = self.view('post', 'add_to_cart')(request)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CartItem.objects.exists())

    def test_get_or_create_cart_returns_empty_cart(self):
        request = self.factory.get("/cart/get/", {"user": self.user.id})

        response = self.view("get", "get_or_create_cart")(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cart_items"], [])
        self.assertEqual(Cart.objects.filter(user=self.user, ordered=False).count(), 1)

    def test_add_to_cart_creates_item_with_quantity(self):
        request = self.factory.post(
            "/cart/add/",
            {"user": self.user.id, "product": self.product.id, "quantity": 2},
            format="json",
        )

        response = self.view("post", "add_to_cart")(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = CartItem.objects.get(cart__user=self.user, product=self.product)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(response.data["cart_items"][0]["quantity"], 2)

    def test_add_to_cart_increments_existing_item(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        request = self.factory.post(
            "/cart/add/",
            {"user": self.user.id, "product": self.product.id, "quantity": 3},
            format="json",
        )

        response = self.view("post", "add_to_cart")(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CartItem.objects.get(cart=cart, product=self.product).quantity, 4)

    def test_add_to_cart_rejects_quantity_above_stock(self):
        request = self.factory.post(
            "/cart/add/",
            {"user": self.user.id, "product": self.product.id, "quantity": 6},
            format="json",
        )

        response = self.view("post", "add_to_cart")(request)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(CartItem.objects.exists())

    def test_update_cart_item_sets_quantity(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        request = self.factory.patch(
            "/cart/update/",
            {"cart": cart.id, "product": self.product.id, "quantity": 5},
            format="json",
        )

        response = self.view("patch", "update_cart_item")(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CartItem.objects.get(cart=cart, product=self.product).quantity, 5)

    def test_decrease_to_zero_removes_item(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        request = self.factory.post(
            "/cart/decrease/",
            {"cart": cart.id, "product": self.product.id, "quantity": 2},
            format="json",
        )

        response = self.view("post", "decrease_cart_item")(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(CartItem.objects.filter(cart=cart, product=self.product).exists())
        self.assertEqual(response.data["cart_items"], [])

    def test_clear_cart_removes_all_items(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        request = self.factory.delete(
            "/cart/clear/",
            {"cart": cart.id},
            format="json",
        )

        response = self.view("delete", "clear_cart")(request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertFalse(CartItem.objects.filter(cart=cart).exists())
        self.assertEqual(response.data["cart_items"], [])
