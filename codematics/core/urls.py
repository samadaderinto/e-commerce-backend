from django.urls import path
from store.views import create_store,get_stores

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
    ActivateEmailTokenCheckAPI,
    create_wishlist,
    create_review,
    create_address,
    redirect_url,
    product_images,
    product_image,
    get_address

)


from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [

    path('<str:marketerId>/<int:product>/<str:identifier>/ ', redirect_url, name='redirect_on_affiliate_link_click'),
    
    path('auth/user/signup/', create_user, name="user_signup"),
    path('auth/activate_mail/<uidb64>/<token>/', ActivateEmailTokenCheckAPI.as_view(), name='activate'),
    path('auth/user/login/', EmailTokenObtainPairView.as_view(),
         name='token_obtain_pair'),
    
    path('auth/user/login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
   
    path('auth/password_reset/<uidb64>/<token>/', PasswordTokenCheckAPI.as_view(), name="password_reset_confirmation"),
    path ('auth/password-reset-complete/', SetNewPassword.as_view(), name='password_reset_complete'),

    path("products/<int:productId>/images/get/", product_images, name="products"),
    path("products/<int:productId>/images/<int:imageId>/get/", product_image, name="products"),
    path("users/stores/create/", create_store, name="create_store"),
    path("users/<int:userId>/stores/get/", get_stores, name="get_store"),
      # tested
     path('users/address/add/',create_address,name="create_address"),
     path('users/<int:userId>/address/<int:AddressId>/delete/',delete_address,name="delete_address"),
     path("users/<int:userId>/address/get/",get_address,name="get_address"),
     path('users/<int:userId>/recents/add/<int:productId>/',create_recent,name='add_recent'),
     path('users/<int:userId>/recents/get',get_recents,name="get_recent"),
     path('users/reviews/create/',create_review,name='create_review'),
     path('users/<int:userId>/reviews/get',get_reviews,name='get_reviews'),
     path("users/<int:userId>/reviews/<int:productId>/delete/", delete_review, name="products"),
     path('users/<int:userId>/wishlist/create/<int:productId>/',create_wishlist,name='create_wishlist'),
     path('users/<int:userId>/wishlist/get/',get_wishlist,name='get_wishlist'),
     path("users/<int:userId>/edit/",edit_user_detail,name="edit_user_info"),
     path("users/<int:userId>/delete/",delete_user_account,name="edit_user_info"),
     path("users/<int:userId>/",get_user,name="edit_user_info"),
     path('users/refunds/request/', request_refund,name="request_refund"),
     path('auth/password_reset/', ResetPassword.as_view(), name='password_reset'),
     path('auth/logout/', UserLogout.as_view(), name='logout'),


]
  