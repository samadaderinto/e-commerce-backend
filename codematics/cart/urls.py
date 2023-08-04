from django.urls import path
from cart.views import cart_item_by_cartId, cart_item_by_id, get_cart,CartViewSet,CartItemViewSet

urlpatterns = [

    # path("carts/", CartViewSet.as_view(), name="cart_items_read"),
    # path("add_to_cart/", CartItemViewSet.as_view(), name="add_to_cart"),
    path("cart/<int:userId>/>str:ordered>", get_cart, name="cart_item_read"),
    # path("cart/<int:pk>/update/", get_cart, name="cart_update"),
    # path("cart/<int:pk>/delete/", get_cart, name="cart_item_delete"),
    path("show_item_cart/<int:cartId>/",  cart_item_by_cartId, name="products"),
    path("cartItemDetectSameItem/<int:pk>/<int:productId>/",
         get_cart, name="products"),
    path("cartItem/<int:pk>/", cart_item_by_id, name="products"),
]
