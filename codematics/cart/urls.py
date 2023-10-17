from django.urls import path
from cart.views import CartViewSet, CartItemViewSet

urlpatterns = [

    path("<int:userId>/", CartViewSet, name="cart_items"),
    path("add_to_cart/", CartItemViewSet, name="add_to_cart")
]
