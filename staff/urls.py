from django.urls import path
from staff.views import create_coupon, create_staff, delete_coupon, delete_staff_account, edit_staff_detail, get_coupons, get_staff, get_staffs, revoke_staff_permission,  give_staff_permission


urlpatterns = [

    path("staff/create/", create_staff, name="create_staff"),
    path("staffs/<int:staffId>/delete/",
         delete_staff_account, name="delete_staff"),
    path("staffs/<int:staffId>/revoke_permission/",
         revoke_staff_permission, name='freeze_account'),
    path("staffs/<int:staffId>/revoke_permission/",
         give_staff_permission, name='freeze_account'),
    path("staffs/<int:staffId>/edit/", edit_staff_detail, name="edit_staff"),

    path("staffs/", get_staffs, name="get_staffs"),
    path("/<int:staffId>/", get_staff, name="get_staff"),

    path("staffs/<int:staffId>/addresses/", get_staff, name="products"),
    path("/<int:staffId>/addresses/add/", get_staff, name="products"),
    path("/<int:staffId>/addresses/<int:id>/delete/",
         get_coupons, name="products"),
    path("/<int:staffId>/addresses/<int:id>/edit/",
         get_staff, name="products"),




    path("coupons/create/", create_coupon, name="products"),
    path("coupons/<int:codeId>/delete/", delete_coupon, name="products"),


    path('refunds/', get_coupons),
    path('refunds/<int:orderId>/', get_coupons),
    path('refund/<int:orderId>/<str:email>/request/', get_coupons),
    path('refund/<int:orderId>/<str:email>/request/response/', get_coupons),

]
