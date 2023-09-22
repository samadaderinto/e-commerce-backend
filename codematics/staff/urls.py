from django.urls import path
from staff.views import get_stores

from staff.views import (
    get_users,
    create_coupon,
    create_staff,
    delete_coupon,
    edit_staff_detail,
    get_coupons,
    get_staff,
    get_staffs,
    revoke_staff_permission,
    give_staff_permission,
    get_refunds,
    get_refund,
    refund_response,
    get_marketers,
    GetOrders,
    get_store_addresses_by_staff,
    create_admin,
    get_marketer,
    get_store_by_staff,
    delete_marketer_account_by_staff,
    delete_staff_account_by_admin,
)


urlpatterns = [
    path("staff/create/", create_staff, name="create_staff"),
    path("admin/create/", create_admin, name="create_admin"),
    path("staff/admin/<int:staffId>/delete/",
         delete_staff_account_by_admin, name="delete_staff_by_admin"),
    path("staff/revoke_permission/",
         revoke_staff_permission, name='freeze_account'),
    path("staff/<int:staffId>/revoke_permission/",
         give_staff_permission, name='freeze_account'),
    path("staff/<int:staffId>/edit/", edit_staff_detail, name="edit_staff"),

    path("get/", get_staffs, name="get_staffs"),
    path("<int:staffId>/get/", get_staff, name="get_staff"),
    
    
    path("staff/stores/get/", get_stores, name="get_stores"),
    path("staff/stores/<int:storeId>/get/", get_store_by_staff, name="get_store_by_staff"),
    path("staff/stores/<int:storeId>/addresses/get/", get_store_addresses_by_staff, name="get_store_address"),
   
   
    path("staff/marketers/get/", get_marketers, name="get_marketers"),
    path("staff/marketers/<int:marketerId>/get/", get_marketer, name="get_marketer"),
    path("staff/marketers/<int:marketerId>/delete/", delete_marketer_account_by_staff, name="delete_marketer_by_staff"),
    
    path("staff/coupons/create/", create_coupon, name="create_coupon"),
    path("staff/coupons/<int:codeId>/delete/", delete_coupon, name="delete_coupon"),
    path("staff/coupons/get/", get_coupons, name="get_coupons"),
    
    
    path("staff/orders/get/", GetOrders.as_view(), name="get_orders"),
    
    path('staff/refunds/', get_refunds),
    path('staff/refunds/<int:refundId>/', get_refund),
    path('staff/refunds/<int:orderId>/response/<int:userId>/send/', refund_response),

 
   path("staff/get_users/",get_users, name="get_users"),]
