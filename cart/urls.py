from django.urls import path
from cart.views import CartItemViewSet, CartViewSet, cart_item_by_cart_id, cart_item_by_id, get_cart 

urlpatterns = [

    path("carts/", CartViewSet.as_view(), name="cart_items_read"),
    path("add_to_cart/", CartItemViewSet.as_view(), name="cart_item_update"),
    path("cart/<int:userId>/>str:ordered>", get_cart, name="cart_item_read"),
    path("cart/<int:pk>/update/", get_cart, name="cart_item_update"),
    path("cart/<int:pk>/delete/", get_cart, name="cart_item_delete"),
    path("show_item_cart/<int:cartId>/",  cart_item_by_cart_id, name="products"),
    path("cartItemDetectSameItem/<int:pk>/<int:productId>/",
         get_cart, name="products"),
    path("cartItem/<int:pk>/", cart_item_by_id, name="products"),
]
