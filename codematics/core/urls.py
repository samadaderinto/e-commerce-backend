from django.urls import path

from core.views import (
    EmailTokenObtainPairView,
    ResetPassword,
    create_user,
    UserLogout,
    edit_user_detail,
    delete_user_account,
    delete_review,
    get_user,
    request_refund,
    delete_address,
    PasswordTokenCheckAPI,
    get_reviews,
    ResetPassword,
    SetNewPassword,
    get_wishlist,
    create_recent,
    get_recents,
    create_wishlist,
    create_review,
    create_address,
    redirect_url

)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    
    path('/<str:refferal_url>', redirect_url, name='redirect_on_affiliate_link_click'),
    
    
    
    
    path('auth/user/signup/', create_user, name="user_signup"),
    path('auth/user/login/', EmailTokenObtainPairView.as_view(),
         name='token_obtain_pair'),
    
    path('auth/user/login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/password_reset/', ResetPassword.as_view(), name='reset_password'),
    path('auth/password-reset/<uidb64>/<token>/', PasswordTokenCheckAPI.as_view(), name="password_reset"),
    path ('password-reset-complete/', SetNewPassword.as_view(), name='password_reset_complete'),

    
    

      # tested
      
     path('users/address/add/',create_address,name="create_address"),
     path('users/<int:userId>/address/<int:AddressId>/delete/',delete_address,name="delete_address"),
     path('users/<int:userId>/recents/add/<int:productId>/',create_recent,name='add_recent'),
     path('users/<int:userId>/recents/get',get_recents,name="get_recent"),
     path('users/reviews/create/',create_review,name='create_review'),
     path('users/<int:userId>/reviews/get',get_reviews,name='get_reviews'),
     path("users/<int:productId>/reviews/delete/", delete_review, name="products"),
     path('users/<int:userId>/wishlist/create/<int:productId>/',create_wishlist,name='create_wishlist'),
     path('users/<int:userId>/wishlist/get/',get_wishlist,name='get_wishlist'),
     path("users/<int:userId>/edit/",edit_user_detail,name="edit_user_info"),
     path("users/<int:userId>/delete/",delete_user_account,name="edit_user_info"),
     path("users/<int:userId>/",get_user,name="edit_user_info"),
     path('users/refund/request/', request_refund,name="request_refund"),
     
     
     path('auth/logout/', UserLogout.as_view(), name='logout'),


]
