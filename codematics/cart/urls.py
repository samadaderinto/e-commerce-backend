from django.urls import path
from cart.views import CartViewSet

urlpatterns = [

    path('get/',
         CartViewSet.as_view({'get': 'get_or_create_cart'}), name="cart"),
    path('item/', 
         CartViewSet.as_view({'post': 'add_to_cart', 'delete': 'delete_cart_item'}), name="add_to_cart"),
]
