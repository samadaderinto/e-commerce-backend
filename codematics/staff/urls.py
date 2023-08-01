from django.urls import path
from store.views import get_stores,get_store

from staff.views import (get_users, create_coupon, create_staff, delete_coupon, delete_staff_account, edit_staff_detail, get_coupons, get_staff, get_staffs, revoke_staff_permission,  give_staff_permission)


urlpatterns = [

    path("staff/create/", create_staff, name="create_staff"),
    path("staff/<int:staffId>/delete/",
         delete_staff_account, name="delete_staff"),
    path("staff/<int:staffId>/revoke_permission/",
         revoke_staff_permission, name='freeze_account'),
    path("staff/<int:staffId>/revoke_permission/",
         give_staff_permission, name='freeze_account'),
    path("staff/<int:staffId>/edit/", edit_staff_detail, name="edit_staff"),

    path("get/", get_staffs, name="get_staffs"),
    path("<int:staffId>/staffs/", get_staff, name="get_staff"),
    
    
    path("staff/stores/get/", get_stores, name="get_stores"),
    path("staff/stores/<int:storeId>/get/", get_store, name="get_store"),
    
    path("staff/<int:staffId>/addresses/", get_staff, name="get_staff_address"),
    path("staff/<int:staffId>/addresses/add/", get_staff, name="create_staff_address"),
    path("staff/<int:staffId>/addresses/<int:id>/delete/",
         get_coupons, name="products"),
    path("staff/<int:staffId>/addresses/<int:id>/edit/",
         get_staff, name="products"),
    
    path("staff/coupons/create/", create_coupon, name="products"),
    path("staff/coupons/<int:codeId>/delete/", delete_coupon, name="products"),

    
    path('staff/refunds/', get_coupons),
    path('staff/refunds/<int:orderId>/', get_coupons),
    path('staff/refund/<int:orderId>/response/', get_coupons),

   # tested
   path("staff/get_users/",get_users, name="get_users"),

    

]
