from django.urls import path

from staff.views import get_coupons
from core.views import EmailTokenObtainPairView, Reset_password, UserLogout, edit_review_by_product_id, product_by_id, product_list, search_productListView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [


    path("products/<int:id>/", product_by_id, name="product"),

    path("products/", product_list, name="products"),
    path("products/find/", search_productListView.as_view(), name="products"),
    path("products/<int:productId>/reviews/",
         edit_review_by_product_id, name="products"),
    
    
    path("productcard/<int:id>/", product_by_id, name="product"),

    path("coupons/", get_coupons, name="products"),
   

    path('auth/login/', EmailTokenObtainPairView.as_view(),
         name='token_obtain_pair'),
    path('auth/login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', UserLogout, name='logout'),
    path('auth/password_reset/', Reset_password.as_view(), name='reset_password'),

    path('refunds/', Reset_password.as_view()),
    path('refunds/<int:orderId>/', Reset_password.as_view()),
    path('refund/<int:orderId>/<str:email>/request/', Reset_password.as_view()),
    path('refund/<int:orderId>/<str:email>/request/response/', Reset_password.as_view()),



]
