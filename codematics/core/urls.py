from django.urls import path

from core.views import (
    EmailTokenObtainPairView,
    ResetPassword,
    create_user,
    UserLogout,
    edit_review_by_product_id,
    edit_user_detail,
    delete_user_account,
    get_user,
    request_refund,
    PasswordTokenCheckAPI,
    ResetPassword,
    SetNewPassword,
    create_wishlist
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    
    
    
    
    
    path('users/<int:userId>/wishlist/create/<int:productId>',create_wishlist,name='create_wishlist'),
    path('auth/user/signup/', create_user, name="user_signup"),
    path('auth/user/login/', EmailTokenObtainPairView.as_view(),
         name='token_obtain_pair'),
    
    path('auth/user/login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/password_reset/', ResetPassword.as_view(), name='reset_password'),
    path('auth/password-reset/<uidb64>/<token>/', PasswordTokenCheckAPI.as_view(), name="password_reset"),
    path ('password-reset-complete/', SetNewPassword.as_view(), name='password_reset_complete'),


    path('refund/<int:orderId>/<str:userId>/request/', request_refund),

      # tested
     path("users/<int:userId>/edit/",edit_user_detail,name="edit_user_info"),
     path("users/<int:userId>/delete/",delete_user_account,name="edit_user_info"),
     path("users/<int:userId>/",get_user,name="edit_user_info"),
     
     
     path('auth/logout/', UserLogout.as_view(), name='logout'),


]
