from rest_access_policy import AccessPolicy

# all views with permitted users in json 
class EcommerceAccessPolicy(AccessPolicy):
    statements = [
        {
            "action": [
                "create_user",
                "Reset_password",
              
                "ResetPassword",
                "PasswordTokenCheckAPI",
                "SetNewPassword",
                "redirect_url",
                "get_store",
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
            ],
            "principal": "*",
            "effect": "allow",
        },
        {
            "action": [
                "edit_user_detail",
                "delete_user_account",
                "get_user",
                
                
                
                "create_staff",
                
                
                
                "create_wishlist",
                "get_wishlist",
                
                
                
                
                "get_reviews",
                "create_review",
                "delete_review",
                
                
                
                
                "get_recents",
                "create_recent",
                
                
                
                
                "create_address",
                "delete_address",
                "edit_address",
                
                
                
                "Orders",
                
                
                
                
                "recents",
                "request_refund",
                
                
                
                "create_store",
                
                
                "get_cart",
                "CartItemViewSet",
                "cart_by_user",
                "CartViewSet",
                "cart_item_by_id",
                "cart_item_by_cartId",
                "cart_items_by_cart_id",
                "cart_item_detect_same_item",
                
                
                
                "redeem_coupon",
                "capture_checkout_session",
                "create_checkout_session",
                
                
                
                "UserLogout",
                
                
                
               
            ],
            "principal": "authenticated",
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
                "CartViewSet",
                "get_marketers",
                "create_shipment",
                "get_refunds",
                "store_products",
                "get_refund",
                "refund_response",
                "IsOwnerSearchProduct",
                "GetOrders",
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
                "CartViewSet",
                "get_marketers",
                "store_products",
                "delete_marketer_account",
                "get_refunds",
                "get_refund",
                "IsOwnerSearchProduct",
                "refund_response",
                "GetOrders",
                "track_order",
                "get_notification",
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
    ]

    def is_marketer(self, request, view, action, field) -> bool:
        marketers = view.Marketer()
        return getattr(marketers, field)

    def is_store_owner(self, request, view, action, field) -> bool:
        stores = view.Marketer()
        return getattr(stores, field)
