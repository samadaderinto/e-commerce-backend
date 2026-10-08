from zoneinfo import ZoneInfo
import logging
from datetime import timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

from django.db.models import Count, Q, Sum
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.permissions import BasePermission
from core.access import IsBackoffice as IsAdminUser, IsBusinessAdmin, is_admin
from rest_framework.response import Response
from rest_framework.request import Request
from django.shortcuts import redirect
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination


from affiliates.models import Marketer
from affiliates.serializers import MarketerSerializer
from notification.views import (
    create_notification,
    refund_requested_nofication,
    staff_created_nofication,
    store_moderation_notification,
)
from notification.models import Notification
from store.serializers import StoreAddressSerializer, StorePayoutSerializer
from store.services import process_payout_status_change, process_refund_deduction
from core.services import credit_user_wallet, get_or_create_user_wallet
from core.models import UserWalletTransaction
from payment.services import (
    execute_order_status_transition,
    process_order_refund,
    decline_order_refund,
)

from staff.serializers import (
    BackofficeCouponSerializer,
    CouponUpdateSerializer,
    OrderStatusOverrideSerializer,
    BackofficeOrderSerializer,
    BackofficeStoreSerializer,
    CommentSerializer,
    DashboardQuerySerializer,
    StaffCreateSerializer,
    StaffPermissionSerializer,
    StaffUserSerializer,
    StaffUserDetailSerializer,
    StoreModerationSerializer,
    StoreAuditProductSerializer,
)
from staff.digital_assets import stream_digital_asset

from staff.models import Comment, PlatformCommissionWithdrawal
from payment.models import Coupon, Order
from payment.serializers import CouponSerializer, OrdersSerializer


from django.contrib.sites.shortcuts import get_current_site

from rest_framework.generics import RetrieveUpdateDestroyAPIView, ListCreateAPIView
from rest_framework import viewsets
from core.serializers import UserSerializer, RefundsSerializer, StoreSerializer, StaffSerializer, AdminSerializer
from utils.functions import auth_token, send_mail, TokenGenerator
from utils.variables import methods
from core.models import User, Refund
from product.models import Product, Specification
from product.cache import invalidate_product_cache
from store.models import StoreAddress, Store, StorePayout, StoreEarningsLedger


from django.utils.http import urlsafe_base64_encode
from django.urls import reverse
from django.utils.encoding import (
    smart_str,
    force_str,
    smart_bytes,
    force_bytes,

    DjangoUnicodeDecodeError
)

# Create your views here.

class BackofficePagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


IsSuperuser = IsBusinessAdmin

class StaffViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]
    pagination_class = BackofficePagination
    serializer_class = StaffUserSerializer
    filter_backends = [SearchFilter, OrderingFilter]

    admin_only_actions = {"staffs", "staff_detail", "block_staff", "unblock_staff", "resend_staff_verification", "block_store", "unblock_store", "process_payout", "commission_wallet", "withdraw_commission"}

    def get_permissions(self):
        permission_classes = (
            [IsSuperuser] if self.action in self.admin_only_actions else self.permission_classes
        )
        return [permission() for permission in permission_classes]

    def paginate_response(self, queryset, serializer_class):
        page = self.paginate_queryset(queryset)
        serializer = serializer_class(page, many=True, context={"request": self.request})
        return self.get_paginated_response(serializer.data)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        query = DashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        with timezone.override(ZoneInfo(query.validated_data['time_zone'])):
            days = query.validated_data["days"]
            today = timezone.localdate()
            start = today - timedelta(days=days - 1)

            orders = Order.objects.filter(created__date__gte=start, created__date__lte=today)
            paid_orders = orders.filter(
                ordered=True,
                status__in=["confirmed", "shipped", "delivered", "picked up"],
            )
            order_total = paid_orders.aggregate(total=Sum("total"))["total"] or Decimal("0")
            ledger = StoreEarningsLedger.objects.exclude(status=StoreEarningsLedger.STATUS_REVERSED)
            escrow_total = ledger.filter(status=StoreEarningsLedger.STATUS_PENDING).aggregate(total=Sum("net_amount"))["total"] or Decimal("0")
            commission_total = ledger.aggregate(total=Sum("fee_amount"))["total"] or Decimal("0")

            return Response({
                "period": {"from": start, "to": today, "days": days, "time_zone": query.validated_data["time_zone"]},
                "users": {
                    "total": User.objects.count(),
                    "active": User.objects.filter(is_active=True).count(),
                    "staff": User.objects.filter(is_staff=True).count(),
                    "new": User.objects.filter(date_joined__date__gte=start).count(),
                },
                "stores": {
                    "total": Store.objects.count(),
                    "active": Store.objects.filter(status=Store.STATUS_ACTIVE).count(),
                    "blocked": Store.objects.filter(status=Store.STATUS_BLOCKED).count(),
                    "new": Store.objects.filter(created__date__gte=start).count(),
                    "new_last_30_days": Store.objects.filter(created__date__gte=today - timedelta(days=29)).count(),
                },
                "products": {
                    "total": Product.objects.count(),
                    "published": Product.objects.filter(visibility=True).count(),
                    "hidden": Product.objects.filter(visibility=False).count(),
                    "out_of_stock": Product.objects.filter(is_digital=False, available=0).count(),
                    "sponsored": Product.objects.filter(sponsored=True).count(),
                },
                "orders": {
                    "total": orders.count(),
                    "ordered": orders.filter(ordered=True).count(),
                    "by_status": list(
                        orders.order_by().values("status").annotate(count=Count("pk")).order_by("status")
                    ),
                    "gross_total": format(order_total, ".2f"),
                },
                "financials": {
                    "escrow_total": format(escrow_total, ".2f"),
                    "commission_earned": format(commission_total, ".2f"),
                },
                "pending_actions": {
                    "withdrawals": StorePayout.objects.filter(status=StorePayout.STATUS_PENDING).count(),
                    "refunds": Refund.objects.filter(status=Refund.STATUS_PENDING).count(),
                },
                "coupons": {
                    "total": Coupon.objects.count(),
                    "active": Coupon.objects.filter(active=True).count(),
                },
                "refunds": {
                    "total": Refund.objects.count(),
                    "accepted": Refund.objects.filter(status=Refund.STATUS_APPROVED).count(),
                    "declined": Refund.objects.filter(status=Refund.STATUS_DECLINED).count(),
                    "pending": Refund.objects.filter(status=Refund.STATUS_PENDING).count(),
                },
                "marketers": {"total": Marketer.objects.count()},
                "recent_orders": BackofficeOrderSerializer(
                    Order.objects.select_related("user").order_by("-created", "-pk")[:10],
                    many=True,
                ).data,
                "top_stores": list(
                    Store.objects.annotate(
                        products=Count("product", distinct=True),
                        orders=Count(
                            "product__cartitem__cart__order",
                            filter=Q(
                                product__cartitem__cart__order__ordered=True,
                                product__cartitem__cart__order__status__in=["confirmed", "shipped", "delivered", "picked up"],
                            ),
                            distinct=True,
                        ),
                    )
                    .order_by("-orders", "-products", "pk")
                    .values("id", "name", "username", "status", "products", "orders")[:10]
                ),
                "scopes": {
                    "orders": f"Last {days} days",
                    "top_stores": "All-time completed orders",
                    "recent_orders": "All-time (recent 10)",
                    "coupons": "All-time configuration",
                    "refunds": "All-time requests",
                    "products": "Current catalog inventory",
                    "users": f"Platform total (new: last {days} days)",
                    "stores": f"Platform total (new: last {days} days)",
                },
            })

    @action(detail=False, methods=["get"])
    def users(self, request):
        users = User.objects.all().order_by("-date_joined", "-pk")
        search = request.query_params.get("search")
        if search:
            users = users.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone1__icontains=search)
            )
        role = request.query_params.get("role")
        if role == "customer":
            users = users.filter(is_staff=False, is_superuser=False, is_business_admin=False)
        elif role == "staff":
            users = users.filter(is_staff=True, is_superuser=False, is_business_admin=False)
        elif role == "admin":
            users = users.filter(Q(is_superuser=True) | Q(is_business_admin=True))

        is_active = request.query_params.get("is_active")
        if is_active in {"true", "false"}:
            users = users.filter(is_active=is_active == "true")

        return self.paginate_response(users, StaffUserSerializer)

    @extend_schema(request=StaffCreateSerializer, responses={201: StaffUserSerializer}, methods=["POST"])
    @extend_schema(responses=StaffUserSerializer(many=True), methods=["GET"])
    @action(detail=False, methods=["get", "post"], url_path="staffs")
    def staffs(self, request):
        """List staff accounts or create one. Superuser/admin only."""
        if request.method == "GET":
            staff_users = User.objects.filter(
                is_staff=True,
                is_superuser=False,
                is_business_admin=False,
            ).order_by("-date_joined", "-pk")
            search = request.query_params.get("search")
            if search:
                staff_users = staff_users.filter(
                    Q(email__icontains=search)
                    | Q(first_name__icontains=search)
                    | Q(last_name__icontains=search)
                )
            return self.paginate_response(staff_users, StaffUserSerializer)

        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff_user = serializer.save()
        staff_created_nofication(staff_user, actor=request.user)
        return Response(StaffUserSerializer(staff_user).data, status=status.HTTP_201_CREATED)

    def get_managed_staff(self, staff_pk):
        return get_object_or_404(
            User,
            pk=staff_pk,
            is_staff=True,
            is_superuser=False,
                is_business_admin=False,
        )

    @action(detail=False, methods=["get"], url_path=r"staffs/(?P<staff_pk>\d+)")
    def staff_detail(self, request, staff_pk=None):
        return Response(StaffUserSerializer(self.get_managed_staff(staff_pk)).data)

    @action(detail=False, methods=["post"], url_path=r"staffs/(?P<staff_pk>\d+)/block")
    def block_staff(self, request, staff_pk=None):
        staff_user = self.get_managed_staff(staff_pk)
        if staff_user.is_active or staff_user.staff_invitation_secret:
            staff_user.is_active = False
            staff_user.staff_invitation_secret = ""
            staff_user.staff_blocked_at = timezone.now()
            staff_user.credential_version += 1
            staff_user.save(update_fields=["is_active", "credential_version", "staff_invitation_secret", "staff_blocked_at"])
        return Response(StaffUserSerializer(staff_user).data)

    @action(detail=False, methods=["post"], url_path=r"staffs/(?P<staff_pk>\d+)/unblock")
    def unblock_staff(self, request, staff_pk=None):
        staff_user = self.get_managed_staff(staff_pk)
        if not staff_user.staff_email_verified:
            return Response({"detail": "Email verification is required before activation."}, status=400)
        if not staff_user.is_active:
            staff_user.is_active = True
            staff_user.staff_blocked_at = None
            staff_user.save(update_fields=["is_active", "staff_blocked_at"])
        return Response(StaffUserSerializer(staff_user).data)

    @action(detail=False, methods=["post"], url_path=r"staffs/(?P<staff_pk>\d+)/resend-verification")
    def resend_staff_verification(self, request, staff_pk=None):
        from core.onboarding import resend_staff_verification
        staff_user = resend_staff_verification(self.get_managed_staff(staff_pk))
        return Response({"detail": "A fresh verification email has been queued.", "staff": StaffUserSerializer(staff_user).data})

    @extend_schema(request=StaffPermissionSerializer, responses=StaffUserSerializer, methods=["PATCH"])
    @extend_schema(responses=StaffUserDetailSerializer, methods=["GET"])
    @action(detail=False, methods=["get", "patch"], url_path=r"users/(?P<user_pk>\d+)")
    def user_detail(self, request: Request, user_pk: str | None = None) -> Response:
        user = get_object_or_404(User, pk=user_pk)
        if request.method == "GET":
            wallet = get_or_create_user_wallet(user)
            ledger = wallet.transactions.order_by('-created')
            ledger_search = request.query_params.get('ledger_search', '').strip()
            ledger_type = request.query_params.get('ledger_type', '').strip()
            if ledger_search:
                ledger = ledger.filter(Q(description__icontains=ledger_search) | Q(reference__icontains=ledger_search) | Q(source__icontains=ledger_search))
            if ledger_type in {'credit', 'debit'}:
                ledger = ledger.filter(transaction_type=ledger_type)
            orders = Order.objects.filter(user=user, ordered=True).order_by('-created')
            order_search = request.query_params.get('order_search', '').strip()
            order_status = request.query_params.get('order_status', '').strip()
            if order_search:
                orders = orders.filter(orderId__icontains=order_search)
            if order_status:
                orders = orders.filter(status=order_status)
            activities = Notification.objects.filter(recipient=user).order_by('-timestamp')[:30]
            return Response(StaffUserDetailSerializer({
                'user': user,
                'wallet': {'balance': format(wallet.balance, '.2f'), 'transactions': [
                    {'id': tx.pk, 'type': tx.transaction_type, 'source': tx.source, 'amount': format(tx.amount, '.2f'), 'description': tx.description, 'created': tx.created}
                    for tx in ledger[:100]
                ]},
                'orders': [{'id': order.pk, 'reference': order.orderId, 'created': order.created, 'updated': order.updated, 'status': order.status, 'total': format(order.total, '.2f')} for order in orders[:100]],
                'activity': [{'id': item.pk, 'verb': item.verb, 'description': item.description, 'created': item.timestamp.isoformat(), 'level': item.level} for item in activities],
            }).data)
        if not is_admin(request.user):
            return Response(
                {"detail": "Only an admin can change account permissions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = StaffPermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(user)
        return Response(StaffUserSerializer(user).data)

    @action(detail=False, methods=["get"])
    def stores(self, request):
        stores = Store.objects.select_related("user").order_by("-created", "-pk")
        store_status = request.query_params.get("status")
        if store_status:
            if store_status not in dict(Store.STATUS_CHOICES):
                return Response({"status": "Use active, blocked, or pending."}, status=status.HTTP_400_BAD_REQUEST)
            stores = stores.filter(status=store_status)
        search = request.query_params.get("search")
        if search:
            stores = stores.filter(
                Q(name__icontains=search)
                | Q(username__icontains=search)
                | Q(user__email__icontains=search)
            )
        ordering = request.query_params.get("ordering", "-created")
        allowed_ordering = {"created", "-created", "name", "-name", "status", "-status"}
        if ordering not in allowed_ordering:
            return Response({"ordering": "Order by created, name, or status."}, status=status.HTTP_400_BAD_REQUEST)
        stores = stores.order_by(ordering, "-pk")
        return self.paginate_response(stores, BackofficeStoreSerializer)

    @action(detail=False, methods=["get", "patch"], url_path=r"stores/(?P<store_pk>\d+)")
    def store_detail(self, request, store_pk=None):
        store = get_object_or_404(Store.objects.select_related("user", "blocked_by"), pk=store_pk)
        if request.method == "PATCH":
            if not is_admin(request.user):
                return Response({"detail": "Only administrators can edit store settings."}, status=403)
            immutable = {"name", "username"}.intersection(request.data.keys())
            if immutable:
                return Response({field: "Store identity is read-only for platform staff." for field in immutable}, status=400)
            serializer = BackofficeStoreSerializer(store, data=request.data, partial=True, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(BackofficeStoreSerializer(store, context={"request": request}).data)

    @action(detail=False, methods=["get"], url_path=r"stores/(?P<store_pk>\d+)/products")
    def store_products(self, request, store_pk=None):
        get_object_or_404(Store, pk=store_pk)
        products = Product.objects.filter(store_id=store_pk).order_by("-created", "-pk")
        search = request.query_params.get("search")
        if search:
            products = products.filter(Q(title__icontains=search) | Q(category__icontains=search))
        is_digital = request.query_params.get("is_digital")
        if is_digital in ("true", "1"):
            products = products.filter(is_digital=True)
        elif is_digital in ("false", "0"):
            products = products.filter(is_digital=False)
        product_type = request.query_params.get("product_type")
        if product_type in ("standard", "affiliate_clickbank"):
            products = products.filter(product_type=product_type)
        visibility = request.query_params.get("visibility")
        if visibility in ("true", "1"):
            products = products.filter(visibility=True)
        elif visibility in ("false", "0"):
            products = products.filter(visibility=False)
        has_asset = request.query_params.get("has_asset")
        if has_asset in ("true", "1"):
            products = products.filter(is_digital=True).exclude(digital_file_url="")
        elif has_asset in ("false", "0"):
            products = products.filter(Q(digital_file_url="") | Q(is_digital=False))
        ordering = request.query_params.get("ordering")
        if ordering in ("created", "-created", "title", "-title", "price", "-price"):
            products = products.order_by(ordering, "-pk")
        return self.paginate_response(products, StoreAuditProductSerializer)

    @action(detail=False, methods=["get"], url_path=r"products/(?P<product_pk>\d+)/digital-asset")
    def digital_asset(self, request, product_pk=None):
        product = get_object_or_404(Product, pk=product_pk, is_digital=True)
        return stream_digital_asset(product)

    @action(detail=False, methods=["post"], url_path=r"stores/(?P<store_pk>\d+)/block")
    def block_store(self, request, store_pk=None):
        store = get_object_or_404(Store, pk=store_pk)
        serializer = StoreModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.block(store, request.user)
        for product in Product.objects.filter(store=store).only("id", "store_id"):
            invalidate_product_cache(product)
        store_moderation_notification(store, actor=request.user, blocked=True)
        return Response(BackofficeStoreSerializer(store).data)

    @action(detail=False, methods=["post"], url_path=r"stores/(?P<store_pk>\d+)/unblock")
    def unblock_store(self, request, store_pk=None):
        store = get_object_or_404(Store, pk=store_pk)
        serializer = StoreModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.unblock(store)
        for product in Product.objects.filter(store=store).only("id", "store_id"):
            invalidate_product_cache(product)
        store_moderation_notification(store, actor=request.user, blocked=False)
        return Response(BackofficeStoreSerializer(store).data)

    @action(detail=False, methods=["get"])
    def orders(self, request):
        ordering = request.query_params.get("ordering", "-created")
        if ordering not in ("-created", "created", "-total", "total"):
            ordering = "-created"
        orders = Order.objects.select_related("user").order_by(ordering, "-pk")
        order_status = request.query_params.get("status")
        if order_status:
            if order_status not in dict(Order.ORDER_STATUS_CHOICE):
                return Response({"status": "Invalid order status."}, status=status.HTTP_400_BAD_REQUEST)
            orders = orders.filter(status=order_status)
        payment_type = request.query_params.get("payment_type")
        if payment_type:
            orders = orders.filter(payment_type=payment_type)
        search = request.query_params.get("search")
        if search:
            orders = orders.filter(
                Q(orderId__icontains=search)
                | Q(user__email__icontains=search)
                | Q(buyer_email__icontains=search)
                | Q(coupon_code__icontains=search)
                | Q(tracking_number__icontains=search)
            )
        return self.paginate_response(orders, BackofficeOrderSerializer)

    @action(detail=False, methods=["post"], url_path=r"orders/(?P<order_pk>\d+)/status")
    def override_order_status(self, request, order_pk=None):
        serializer = OrderStatusOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = get_object_or_404(Order.objects.select_related("user"), pk=order_pk)
        next_status = serializer.validated_data["status"]
        reason = serializer.validated_data["reason"]
        order = execute_order_status_transition(order, next_status, request.user, reason)
        return Response(BackofficeOrderSerializer(order).data)

    @action(detail=False, methods=["get", "post"])
    def coupons(self, request):
        if request.method == "GET":
            ordering = request.query_params.get("ordering", "-created")
            if ordering not in ("-created", "created", "-discount", "discount", "-num_used", "num_used"):
                ordering = "-created"
            coupons = Coupon.objects.all().order_by(ordering, "-pk")
            active = request.query_params.get("active")
            if active in ("true", "1"):
                coupons = coupons.filter(active=True)
            elif active in ("false", "0"):
                coupons = coupons.filter(active=False)
            search = request.query_params.get("search")
            if search:
                coupons = coupons.filter(code__icontains=search)
            return self.paginate_response(coupons, BackofficeCouponSerializer)
        serializer = BackofficeCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user if request.user.is_authenticated else None)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["patch", "delete"], url_path=r"coupons/(?P<coupon_pk>\d+)")
    def coupon_detail(self, request, coupon_pk=None):
        coupon = get_object_or_404(Coupon, pk=coupon_pk)
        if request.method == "PATCH":
            serializer = CouponUpdateSerializer(coupon, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info("Coupon %s mutated by %s: %s", coupon.code, request.user, request.data)
            return Response(BackofficeCouponSerializer(coupon).data)
        if coupon.num_used or coupon.redemptions.exists():
            return Response(
                {"detail": "Used coupons must be deactivated to preserve redemption history."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if coupon.active:
            return Response({"detail": "Deactivate this coupon before deleting it."}, status=status.HTTP_400_BAD_REQUEST)
        coupon.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="refunds")
    def refunds(self, request):
        ordering = request.query_params.get("ordering", "-created")
        if ordering not in ("-created", "created"):
            ordering = "-created"
        refunds = Refund.objects.select_related("order", "order__user").order_by(ordering, "-pk")
        refund_status = request.query_params.get("status")
        if refund_status:
            refunds = refunds.filter(status=refund_status)
        refund_type = request.query_params.get("refund_type")
        if refund_type:
            refunds = refunds.filter(refund_type=refund_type)
        search = request.query_params.get("search")
        if search:
            refunds = refunds.filter(
                Q(email__icontains=search)
                | Q(order__orderId__icontains=search)
                | Q(reason__icontains=search)
                | Q(provider_reference__icontains=search)
            )
        return self.paginate_response(refunds, RefundsSerializer)

    @action(detail=False, methods=["post"], url_path=r"refunds/(?P<refund_pk>\d+)/process")
    def process_refund(self, request, refund_pk=None):
        action_type = request.data.get("action", "approve")
        if action_type not in {"approve", "decline"}:
            return Response({"action": "Use approve or decline."}, status=400)
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response({"reason": "A reason is required to process a refund."}, status=400)
        refund = get_object_or_404(
            Refund.objects.select_related("order", "order__user"),
            pk=refund_pk,
        )
        if action_type == "approve":
            refund = process_order_refund(refund, request.user, reason=reason)
            return Response({"detail": "Refund approved and processed.", "refund": RefundsSerializer(refund).data})
        else:
            refund = decline_order_refund(refund, request.user, reason=reason)
            return Response({"detail": "Refund request declined.", "refund": RefundsSerializer(refund).data})

    @action(detail=False, methods=["get"], url_path="payouts")
    def payouts(self, request):
        payouts = StorePayout.objects.select_related("store", "store__user", "wallet").order_by("-created", "-pk")
        payout_status = request.query_params.get("status")
        if payout_status:
            payouts = payouts.filter(status=payout_status)
        return self.paginate_response(payouts, StorePayoutSerializer)

    @action(detail=False, methods=["get"], url_path="commission-wallet")
    def commission_wallet(self, request):
        commission_earned = StoreEarningsLedger.objects.filter(
            status__in=[StoreEarningsLedger.STATUS_AVAILABLE, StoreEarningsLedger.STATUS_COMPLETED],
            store__is_official=False,
        ).aggregate(total=Sum("fee_amount"))["total"] or Decimal("0")
        official_store_earned = StoreEarningsLedger.objects.filter(
            status__in=[StoreEarningsLedger.STATUS_AVAILABLE, StoreEarningsLedger.STATUS_COMPLETED],
            store__is_official=True,
        ).aggregate(total=Sum("net_amount"))["total"] or Decimal("0")
        earned = commission_earned + official_store_earned
        withdrawn = PlatformCommissionWithdrawal.objects.exclude(status=PlatformCommissionWithdrawal.STATUS_FAILED).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        rows = PlatformCommissionWithdrawal.objects.select_related('requested_by').order_by('-created')[:50]
        return Response({
            "earned": format(earned, '.2f'),
            "marketplace_commission": format(commission_earned, '.2f'),
            "official_stores_revenue": format(official_store_earned, '.2f'),
            "withdrawn_or_pending": format(withdrawn, '.2f'),
            "available": format(max(Decimal('0'), earned - withdrawn), '.2f'),
            "withdrawals": [
                {
                    "id": row.pk,
                    "amount": format(row.amount, '.2f'),
                    "payout_method": row.payout_method,
                    "status": row.status,
                    "reference": row.reference,
                    "created": row.created,
                }
                for row in rows
            ],
        })

    @action(detail=False, methods=["post"], url_path="commission-wallet/withdraw")
    @transaction.atomic
    def withdraw_commission(self, request):
        amount = Decimal(str(request.data.get('amount', '0')))
        if amount <= 0:
            return Response({'amount': 'Enter an amount greater than zero.'}, status=400)
        commission_earned = StoreEarningsLedger.objects.filter(
            status__in=[StoreEarningsLedger.STATUS_AVAILABLE, StoreEarningsLedger.STATUS_COMPLETED],
            store__is_official=False,
        ).aggregate(total=Sum("fee_amount"))["total"] or Decimal("0")
        official_store_earned = StoreEarningsLedger.objects.filter(
            status__in=[StoreEarningsLedger.STATUS_AVAILABLE, StoreEarningsLedger.STATUS_COMPLETED],
            store__is_official=True,
        ).aggregate(total=Sum("net_amount"))["total"] or Decimal("0")
        earned = commission_earned + official_store_earned
        reserved = PlatformCommissionWithdrawal.objects.exclude(status=PlatformCommissionWithdrawal.STATUS_FAILED).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        if amount > earned - reserved:
            return Response({'amount': 'Amount exceeds available platform treasury funds.'}, status=400)
        from nanoid import generate
        row = PlatformCommissionWithdrawal.objects.create(
            amount=amount,
            payout_method=str(request.data.get('payout_method', 'stripe')),
            account_details=request.data.get('account_details') or {},
            requested_by=request.user,
            reference=f'PCW-{generate(size=12)}'
        )
        return Response({'id': row.pk, 'reference': row.reference, 'status': row.status}, status=201)

    @action(detail=False, methods=["post"], url_path=r"payouts/(?P<payout_pk>\d+)/process")
    def process_payout(self, request, payout_pk=None):
        payout = get_object_or_404(StorePayout.objects.select_related("store", "store__user", "wallet"), pk=payout_pk)
        action_type = request.data.get("action", "approve")
        recipient_user = (payout.store and payout.store.user) or (payout.wallet and payout.wallet.user)

        if action_type == "approve":
            payout = process_payout_status_change(payout, action="approve", processed_by=request.user)

            if recipient_user:
                create_notification(
                    recipient=recipient_user,
                    verb=f"Payout Completed: ${payout.amount}",
                    description=f"Your payout request of ${payout.amount} (Ref: {payout.reference}) has been disbursed.",
                    data={"payout_id": payout.pk, "amount": str(payout.amount)},
                )
            return Response({"detail": "Payout marked as completed.", "payout": StorePayoutSerializer(payout).data})
        else:
            reason = request.data.get("reason", "Payout declined by compliance.")
            payout = process_payout_status_change(payout, action="reject", processed_by=request.user, notes=reason)

            if recipient_user:
                create_notification(
                    recipient=recipient_user,
                    verb=f"Payout Declined: ${payout.amount}",
                    description=f"Your payout request of ${payout.amount} (Ref: {payout.reference}) was declined. Reason: {reason}",
                    data={"payout_id": payout.pk, "amount": str(payout.amount)},
                )
            return Response({"detail": "Payout marked as rejected.", "payout": StorePayoutSerializer(payout).data})



def create_staff(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        if User.objects.filter(email=data["email"]).exists():
            return Response(
                {"error": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User.objects.create_staffuser(**data)
            serializer = StaffSerializer(user)

            uidb64 = urlsafe_base64_encode(force_bytes(user.id))
            token = TokenGenerator().make_token(user)
            current_site = get_current_site(request).domain
            relativeLink = reverse(
                "activate", kwargs={"uidb64": uidb64, "token": token}
            )
            absolute_url = f"http://{current_site}{relativeLink}"

            token = auth_token(user)
            send_mail("onboarding-user", user.email,
                      data={"firstname": user.first_name, "absolute_url": absolute_url})

            return Response(
                serializer.data,
                headers={"Authorization": token},
                status=status.HTTP_201_CREATED,
            )



def create_admin(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        if User.objects.filter(email=data["email"]).exists():
            return Response(
                {"error": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User.objects.create_superuser(**data)
            serializer = AdminSerializer(user)

            uidb64 = urlsafe_base64_encode(force_bytes(user.id))
            token = TokenGenerator().make_token(user)
            current_site = get_current_site(request).domain
            relativeLink = reverse(
                "activate", kwargs={"uidb64": uidb64, "token": token}
            )
            absolute_url = f"http://{current_site}{relativeLink}"

            token = auth_token(user)
            # send_mail("onboarding-user", user.email,
            #           data={"firstname": user.first_name, "absolute_url": absolute_url})

            return Response(
                serializer.data,
                headers={"Authorization": token},
                status=status.HTTP_201_CREATED,
            )



def give_staff_permission(request):
    data = JSONParser().parse(request)
    serializer = UserSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email, is_staff=True)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    # user.has_perm = True
    user.save()
    return Response({"success": "Permission granted for this staff member"}, status=status.HTTP_200_OK)



def edit_staff_detail(request, userId):
    data = JSONParser().parse(request)

    try:
        user = User.objects.get(
            pk=userId, email=data.get("email"), is_staff=True)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["post"]:
        serializer = UserSerializer(user, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        




def delete_staff_account_by_admin(request):
    if request.method == methods["delete"]:
        data = JSONParser().parse(request)
        serializer = UserSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.delete()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        



def revoke_staff_permission(request):
    data = JSONParser().parse(request)
        
    try:
        staff = User.objects.get(email=data.get("email"),is_staff=True)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    staff.is_active = False
    staff.save()
    return Response({"success": "Permission revoked for this staff member"}, status=status.HTTP_200_OK)



def get_staffs(request):
    
    staffs = User.objects.filter(is_staff=True).order_by("created").reverse()
    serializer = StaffSerializer(staffs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)



def get_staff(request, staffId):
    
    try:
        staff = User.objects.get(id=staffId, is_staff=True)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        
        serializer = UserSerializer(staff)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)



def get_coupons(request):
    try:
        coupons = Coupon.objects.all()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = CouponSerializer(coupons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def delete_coupon(request, codeId):
    try:
        coupons = Coupon.objects.get(pk=codeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        coupons.delete()
    return Response(status=status.HTTP_202_ACCEPTED)



def create_coupon(request):
    
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = CouponSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        

def edit_coupon(request, couponId):
    if request.method == methods["put"]:
        coupon = Coupon.objects.get(code=couponId)
        serializer = CouponSerializer(coupon )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
       



def get_users(request):
    try:
        users = User.objects.all().order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



def get_refunds(request):
    try:
        refunds = Refund.objects.all().order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RefundsSerializer(refunds, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



def get_refund(request, refundId):
    try:
        refunds = Refund.objects.get(id=refundId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RefundsSerializer(refunds)
        return Response(serializer.data, status=status.HTTP_200_OK)



def refund_response(request,orderId, userId):
    if request.method == methods["post"]:
        user = User.objects.get(id=userId)
     
        data = {
            "firstname": user.first_name,
            "orderId": orderId,
            "message": "",
        }
        send_mail("refund-response", user.email, data=data)
        return Response(status=status.HTTP_200_OK)



def get_marketers(request):
    try:
        marketer = Marketer.objects.all().order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = MarketerSerializer(marketer, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



def get_marketer(request, marketerId):
    try:
       marketer = Marketer.objects.get(id=marketerId)
    except:   
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["get"]:
        
        serializer = MarketerSerializer(marketer)
       
        return Response(serializer.data, status=status.HTTP_201_CREATED)



def suspend_marketer(request, marketerId):
    try:
       marketer = Marketer.objects.get(id=marketerId)
    except:   
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["get"]:
        
        serializer = MarketerSerializer(marketer)
       
        return Response(serializer.data, status=status.HTTP_201_CREATED)

def delete_marketer_account_by_staff(request,marketerId):
    try:
       marketer = Marketer.objects.get(id=marketerId)
    except:   
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["delete"]:

        marketer.delete()
        return Response(status=status.HTTP_202_ACCEPTED)
           

class GetOrders(ListAPIView):
   

    serializer_class = OrdersSerializer
           

    search_field = (
        "id",
        "status",
        "orderId",
        "ordered",
        "payment_type",
        "ordered_date",
    )

    filter_backends = [SearchFilter, OrderingFilter]
    ordering_fields = ["orderId","ordered_date"]


    def get_queryset(self):
        return Order.objects.all()

    def get_serializer_context(self):
        return {"request": self.request}


class CommentList(ListCreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class CommentDetail(RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer



def get_stores(request):
    try:
        store = Store.objects.all().order_by("user").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == methods["get"]:
        serializer = StoreSerializer(store, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



def get_store_by_staff(request, storeId):
    try:
        store = Store.objects.filter(id=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == methods["get"]:
        serializer_context = {"request": request}
        serializer = StoreSerializer(store, context=serializer_context, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)
    
    

def get_store_addresses_by_staff(request, storeId):
    try:
        store = StoreAddress.objects.filter(store=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["get"]:
     
        serializer = StoreAddressSerializer(store, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)
