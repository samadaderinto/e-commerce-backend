from django.urls import path
from django.contrib.auth import views as auth_views
from .models import *
from .views import *
from rest_framework_simplejwt.views import (TokenObtainPairView,TokenRefreshView)

urlpatterns = [
    path("users/<int:userId>/", get_user, name="user"),
    path("users/create/", create_user, name="create_user"),
    path("users/<int:userId>/wishlist/", wishlist_by_user_id, name="products"),
    path("users/<int:userId>/reviews/", reviews_by_user_id, name="user_reviews"),
    path("users/<int:userId>/recents/", recent_product_by_user, name="products"),
    # path("users/<int:id>/orders/", ProductsDetailAPIView(), name="products"),
    # path("users/<int:id>/orders/<str:status>/", ProductsDetailAPIView(), name="products"),
    # path("users/<int:id>/orders/<str:status>/<int:pk>/", ProductsDetailAPIView(), name="products"),
    # path("users/<int:id>/orders/<str:status>/<int:pk>/rating/", ProductsDetailAPIView(), name="products"),
#     path("login/<str:email>/<str:password>/", login_user, name="products"),

    path("coupons/", get_coupon, name="products"),
    path("coupons/reedeem", redeem_coupon, name="products"),

    path("stores/", get_stores, name="products"),
    path("stores/<int:user>/", get_store, name="get_store"),
    path("stores/create/", create_store, name="create_store"),
    path("stores/<int:store>/products/",
         sellers_products, name="store_products"),

    path("products/", product_list, name="products"),
    path("products/<int:id>/", product_by_id, name="product"),
    path("products/find", search_productListView.as_view(), name="products"),
    path("products/<int:productId>/reviews/",
         reviews_by_product_id, name="products"),

    path('rate/<int:post_id>/<int:rating>/', views.rate),
    path('', views.index),
    path("cart/", cart_list, name="cart_items_read"),
    # path("cartItem/create/", CartCreateAPIView.as_view(), name="cart_item_update"),
    # path("cart/<int:pk>/", CartDetailAPIView.as_view(), name="cart_item_read"),
    # path("cart/<int:pk>/update/", CartUpdateAPIView.as_view(), name="cart_item_update"),
    # path("cart/<int:pk>/delete/", CartDeleteAPIView.as_view(), name="cart_item_delete"),
    path("show_item_cart/<int:cartId>/",  cart_item_by_cart_id, name="products"),
    # path("cartItemDetectSameItem/<int:pk>/<int:productId>/", ProductsDetailAPIView(), name="products"),
    path("cartItem/<int:pk>/", cart_item_by_id, name="products"),



    # path("productImg/", ProductsDetailAPIView(), name="products"),
    # path("productImg/<int:productId>/", ProductsDetailAPIView(), name="products"),
    # path("ProductImg/id/<int:id>/", ProductsDetailAPIView(), name="products"),
    # path("product/find/<str:category>/", ProductsDetailAPIView(), name="products"),
    path("file_upload/", file_upload.as_view(), name="file_upload"),
    # path("delete_file/<str:filename>/", delete_file, name="file_delete"),

    path("filter/categories/<str:categories>/",filter_by_categories, name="products"),
    # path("filter/price/<int:minprice>/<int:maxprice>",filter_range_price, name="products"),
    # path("filter/price/min/<int:minprice>/", ProductsDetailAPIView(), name="products"),
    # path("filter/price/max/<int:maxprice>/", ProductsDetailAPIView(), name="products"),

    # path("filter/rating/min/<int:minrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/rating/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),

    # path("filter/color/<str:color>/", ProductsDetailAPIView(), name="products"),

    # path("filter/price_and_rating/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/price_and_color/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/price_and_category/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/price_and_brand/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),

    # path("filter/category_and_rating/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/category_and_color/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/category_and_brand/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),

    # path("filter/color_and_brand/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/color_and_rating/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),

    # path("filter/price_and_rating_and_brand/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/price_and_color_and_brand/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/price_and_category_and_brand/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),

    # path("filter/category_and_rating_and_price/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/category_and_color_and_price/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),
    # path("filter/category_and_brand_and_price/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),

    # path("filter/category_and_rating_and_price_and_brand/max/<int:maxrating>/", ProductsDetailAPIView(), name="products"),

    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    
    path('password_reset/', Reset_password.as_view(),name='resetpassword'),

    # path('refunds/', auth_PasswordResetCompleteView.as_view())
    # path('refunds/<int:orderId>/', auth_PasswordResetCompleteView.as_view())
    # path('refund/<int:orderId>/<str:email>/request/', auth_PasswordResetCompleteView.as_view())
    # path('refund/<int:orderId>/<str:email>/request/response/', auth_PasswordResetCompleteView.as_view())
]



