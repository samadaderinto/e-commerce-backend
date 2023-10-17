from rest_access_policy import AccessPolicy
from affiliates.models import Marketer

from store.models import Store

# all views with permitted users in json


class EcommerceAccessPolicy(AccessPolicy):
    statements = [
        {
            "action": [
                "create_user",
                "ResetPassword",
                "PasswordTokenCheckAPI",
                "SetNewPassword",
                "redirect_url",
                "get_store",
                "create_staff",
                "create_marketer",
                "store_products",
                "get_product_reviews",
                "get_specifications",
                "view_product",
                "product_images_by_product_id",
                "product_image_by_id",
                "product_image_list",
                "SearchProduct",
                "get_specifications",
                "create_admin",
                "EmailTokenObtainPairView",
            ],
            "principal": "*",
            "effect": "allow",
        },
        {
            "action": [
                "get_users",
                "get_staff",
                "get_staffs",
                "get_coupons",
                "get_stores",
                "create_coupon",
                "delete_coupon",
                "edit_coupon",
                "revoke_staff_permission",
                "delete_staff_account",
                "give_staff_permission",
                "get_marketers",
                "create_shipment",
                "get_refunds",
                "store_products",
                "get_refund",
                "refund_response",
                "IsOwnerSearchProduct",
                "GetOrders",
                "get_store_by_staff",
                "get_store_addresses_by_staff",
                "delete_marketer_account_by_staff",
            ],
            "principal": ["admin"],
            "effect": "allow",
        },
        {
            "action": [
                "get_users",
                "get_staff",
                "get_coupons",
                "create_shipment",
                "get_stores",
                "edit_staff_detail",
                "delete_staff_account",
                "get_marketers",
                "store_products",
                "delete_marketer_account_by_staff",
                "get_refunds",
                "get_refund",
                "IsOwnerSearchProduct",
                "refund_response",
                "GetOrders",
                "get_store_by_staff",
                "track_order",
                "get_store_addresses_by_staff",
            ],
            "principal": ["staff"],
            "effect": "allow",
        },
        {
            "action": [
                "delete_file",
                "create_specifications",
                "delete_specifications",
                "store_products",
                "schedule_product_visibility",
                "schedules",
                "get_store",
                "IsOwnerSearchProduct",
                "create_product",
                "delete_store",
                "edit_store_info",
                "create_schedule",
                "schedules",
                "delete_product",
                "ProductCreateView"

            ],
            "principal": ["authenticated"],
            "effect": "allow",
            "condition": "is_store_owner:owner",
        },
        {
            "action": [
                "create_marketer",
                "edit_marketer_detail",
                "get_product_link",
                "get_marketer",
                "delete_marketer_account",
            ],
            "principal": ["authenticated"],
            "effect": "allow",
            "condition": "is_marketer:owner",
        },
        {
            "action": [
                "edit_user_detail",
                "delete_user_account",
                "get_user",
                "create_wishlist",
                "get_wishlist",
                "get_reviews",
                "create_review",
                "delete_review",
                "get_recents",
                "create_recent",
                "create_address",
                "get_address",
                "delete_address",
                "edit_address",
                "Orders",
                "get_stores",
                "edit_store_info",
                "recents",
                "request_refund",
                "delete_store",
                "create_store",
                "CartViewSet",
                "CartItemViewSet",
                "capture_checkout_session",
                "create_checkout_session",
                "UserLogout",
                "ActivateEmailTokenCheckAPI"
            ],
            "principal": "authenticated",
            "effect": "allow",
        },


    ]

    def is_marketer(self, request, view, action, field) -> bool:
        try:
            Marketer.objects.get(pk=request.data["marketer"])
        except:
            return False
        return True

    def is_store_owner(self, request, view, action, field) -> bool:
        try:
            Store.objects.get(pk=request.data["store"])
        except:
            return False
        return True
