from core.listing_filters import ListingQuerySerializer, filter_records, record_page
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


from affiliates.models import Marketer, Referral
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
    StaffUserOrderQuerySerializer,
    TreasuryWithdrawalSerializer,
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

    admin_only_actions = {
        "staffs",
        "staff_detail",
        "block_staff",
        "unblock_staff",
        "resend_staff_verification",
        "commission_wallet",
        "withdraw_commission",
    }

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
                "referrals": {
                    "total": Referral.objects.count(),
                    "rewarded": Referral.objects.filter(status=Referral.REWARDED).count(),
                    "pending": Referral.objects.filter(status=Referral.PENDING).count(),
                    "rewarded_amount": format(
                        Referral.objects.filter(status=Referral.REWARDED).aggregate(total=Sum("reward_amount"))["total"] or 0,
                        ".2f",
                    ),
                },
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
            staff_users = filter_records(
                staff_users, request.query_params, date_field="date_joined",
                fields={"is_active": "is_active", "staff_email_verified": "staff_email_verified"},
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
    @transaction.atomic
    def block_staff(self, request: Request, staff_pk: str | None = None) -> Response:
        staff_user = self.get_managed_staff(staff_pk)
        previous_active, previous_staff = staff_user.is_active, staff_user.is_staff
        if staff_user.is_active or staff_user.staff_invitation_secret:
            staff_user.is_active = False
            staff_user.staff_invitation_secret = ""
            staff_user.staff_blocked_at = timezone.now()
            staff_user.credential_version += 1
            staff_user.save(update_fields=["is_active", "credential_version", "staff_invitation_secret", "staff_blocked_at"])
        from notification.views import account_access_notification

        account_access_notification(staff_user, previous_active, previous_staff)
        return Response(StaffUserSerializer(staff_user).data)

    @action(detail=False, methods=["post"], url_path=r"staffs/(?P<staff_pk>\d+)/unblock")
    @transaction.atomic
    def unblock_staff(self, request: Request, staff_pk: str | None = None) -> Response:
        staff_user = self.get_managed_staff(staff_pk)
        previous_active, previous_staff = staff_user.is_active, staff_user.is_staff
        if not staff_user.staff_email_verified:
            return Response({"detail": "Email verification is required before activation."}, status=400)
        if not staff_user.is_active:
            staff_user.is_active = True
            staff_user.staff_blocked_at = None
            staff_user.save(update_fields=["is_active", "staff_blocked_at"])
        from notification.views import account_access_notification

        account_access_notification(staff_user, previous_active, previous_staff)
        return Response(StaffUserSerializer(staff_user).data)

    @action(detail=False, methods=["post"], url_path=r"staffs/(?P<staff_pk>\d+)/resend-verification")
    def resend_staff_verification(self, request, staff_pk=None):
        from core.onboarding import resend_staff_verification
        staff_user = resend_staff_verification(self.get_managed_staff(staff_pk))
        return Response({"detail": "A fresh verification email has been queued.", "staff": StaffUserSerializer(staff_user).data})

    @extend_schema(request=StaffPermissionSerializer, responses=StaffUserSerializer, methods=["PATCH"])
    @extend_schema(parameters=[StaffUserOrderQuerySerializer], responses=StaffUserDetailSerializer, methods=["GET"])
    @action(detail=False, methods=["get", "patch"], url_path=r"users/(?P<user_pk>\d+)")
    @transaction.atomic
    def user_detail(self, request: Request, user_pk: str | None = None) -> Response:
        user = get_object_or_404(User, pk=user_pk)
        if (user.is_superuser or user.is_business_admin) and not is_admin(request.user):
            return Response(
                {"detail": "Staff accounts cannot inspect administrator profile details."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if request.method == "GET":
            wallet = get_or_create_user_wallet(user)
            ledger = wallet.transactions.order_by('-created')
            ledger_search = request.query_params.get('ledger_search', '').strip()
            ledger_type = request.query_params.get('ledger_type', '').strip()
            if ledger_search:
                ledger = ledger.filter(Q(description__icontains=ledger_search) | Q(reference__icontains=ledger_search) | Q(source__icontains=ledger_search))
            if ledger_type in {'credit', 'debit'}:
                ledger = ledger.filter(transaction_type=ledger_type)
            ledger_params = {
                key.removeprefix("ledger_"): value
                for key, value in request.query_params.items() if key.startswith("ledger_")
            }
            ledger = filter_records(
                ledger, ledger_params, search_fields=("description", "reference", "source"),
                fields={"type": "transaction_type", "source": "source"}, amount_field="amount",
            )
            ledger_count, ledger = record_page(ledger, ledger_params)
            filters = StaffUserOrderQuerySerializer(data=request.query_params)
            filters.is_valid(raise_exception=True)
            criteria = filters.validated_data
            all_orders = Order.objects.filter(user=user, ordered=True)
            from django.db.models import Sum

            lifetime_spent = all_orders.exclude(status="cancelled").aggregate(value=Sum("total"))["value"] or 0
            orders = all_orders.order_by(criteria["order_ordering"], "-pk")
            if criteria["order_search"]:
                search = criteria["order_search"].strip()
                orders = orders.filter(
                    Q(orderId__icontains=search)
                    | Q(coupon_code__icontains=search)
                    | Q(carrier__icontains=search)
                    | Q(tracking_number__icontains=search)
                    | Q(fulfillments__carrier__icontains=search)
                ).distinct()
            if criteria["order_status"]:
                orders = orders.filter(status=criteria["order_status"])
            if criteria["order_payment"]:
                orders = orders.filter(payment_type=criteria["order_payment"])
            if criteria["order_carrier"]:
                orders = orders.filter(
                    Q(carrier__iexact=criteria["order_carrier"])
                    | Q(fulfillments__carrier__iexact=criteria["order_carrier"])
                ).distinct()
            offset = criteria["order_offset"]
            activities = Notification.objects.filter(recipient=user).order_by('-timestamp')[:30]

            referral_record = Referral.objects.select_related("marketer__user").filter(referred_user=user).first()
            referral_data = None
            if referral_record:
                referral_data = {
                    "id": referral_record.id,
                    "status": referral_record.status,
                    "reward_amount": format(referral_record.reward_amount, ".2f"),
                    "created": referral_record.created.isoformat(),
                    "referrer_name": referral_record.marketer.name,
                    "referrer_code": referral_record.marketer.marketer_id,
                    "referrer_email": referral_record.marketer.user.email,
                    "referrer_user_id": referral_record.marketer.user_id,
                }

            marketer_record = Marketer.objects.filter(user=user).first()
            affiliate_data = None
            if marketer_record:
                affiliate_referrals = Referral.objects.filter(marketer=marketer_record)
                rewarded_count = affiliate_referrals.filter(status=Referral.REWARDED).count()
                credit_earned = affiliate_referrals.filter(status=Referral.REWARDED).aggregate(total=Sum("reward_amount"))["total"] or 0
                affiliate_data = {
                    "id": marketer_record.id,
                    "name": marketer_record.name,
                    "referral_code": marketer_record.marketer_id,
                    "referral_count": affiliate_referrals.count(),
                    "rewarded_count": rewarded_count,
                    "credit_earned": format(credit_earned, ".2f"),
                    "created": marketer_record.created.isoformat(),
                }

            return Response(StaffUserDetailSerializer({
                'user': user,
                'wallet': {'balance': format(wallet.balance, '.2f'), 'count': ledger_count, 'transactions': [
                    {'id': tx.pk, 'type': tx.transaction_type, 'source': tx.source, 'amount': format(tx.amount, '.2f'), 'description': tx.description, 'created': tx.created}
                    for tx in ledger
                ]},
                'order_count': orders.count(),
                'total_orders': all_orders.count(),
                'lifetime_spent': lifetime_spent,
                'orders': [{'id': order.pk, 'reference': order.orderId, 'created': order.created, 'updated': order.updated, 'status': order.status, 'total': format(order.total, '.2f')} for order in orders[offset:offset + 15]],
                'activity': [{'id': item.pk, 'verb': item.verb, 'description': item.description, 'created': item.timestamp.isoformat(), 'level': item.level} for item in activities],
                'referral': referral_data,
                'affiliate': affiliate_data,
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
        stores = filter_records(
            stores, request.query_params,
            fields={"is_official": "is_official"},
        )
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
        products = filter_records(products, request.query_params, fields={"category": "category"})
        return self.paginate_response(products, StoreAuditProductSerializer)

    @action(detail=False, methods=["get"], url_path=r"products/(?P<product_pk>\d+)/digital-asset")
    def digital_asset(self, request, product_pk=None):
        product = get_object_or_404(Product, pk=product_pk, is_digital=True)
        return stream_digital_asset(product)

    @action(detail=False, methods=["post"], url_path=r"stores/(?P<store_pk>\d+)/block")
    @transaction.atomic
    def block_store(self, request: Request, store_pk: str | None = None) -> Response:
        store = get_object_or_404(Store.objects.select_for_update(), pk=store_pk)
        if store.is_official:
            return Response(
                {"detail": "Official company stores cannot be blocked."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = StoreModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if store.status == Store.STATUS_BLOCKED and store.blocked_reason == serializer.validated_data.get("reason", ""):
            return Response(BackofficeStoreSerializer(store).data)
        store = serializer.block(store, request.user)
        for product in Product.objects.filter(store=store).only("id", "store_id"):
            invalidate_product_cache(product)
        store_moderation_notification(store, actor=request.user, blocked=True)
        return Response(BackofficeStoreSerializer(store).data)

    @action(detail=False, methods=["post"], url_path=r"stores/(?P<store_pk>\d+)/unblock")
    @transaction.atomic
    def unblock_store(self, request: Request, store_pk: str | None = None) -> Response:
        store = get_object_or_404(Store.objects.select_for_update(), pk=store_pk)
        serializer = StoreModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if store.status == Store.STATUS_ACTIVE:
            return Response(BackofficeStoreSerializer(store).data)
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
        carrier = request.query_params.get("carrier") or request.query_params.get("courier")
        if carrier:
            orders = orders.filter(
                Q(carrier__iexact=carrier) | Q(fulfillments__carrier__iexact=carrier)
            ).distinct()
        search = request.query_params.get("search")
        if search:
            orders = orders.filter(
                Q(orderId__icontains=search)
                | Q(user__email__icontains=search)
                | Q(buyer_email__icontains=search)
                | Q(coupon_code__icontains=search)
                | Q(carrier__icontains=search)
                | Q(fulfillments__carrier__icontains=search)
                | Q(tracking_number__icontains=search)
            ).distinct()
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
            coupons = Coupon.objects.select_related("created_by").all().order_by(ordering, "-pk")
            active = request.query_params.get("active")
            if active in ("true", "1"):
                coupons = coupons.filter(active=True)
            elif active in ("false", "0"):
                coupons = coupons.filter(active=False)
            search = request.query_params.get("search")
            if search:
                coupons = coupons.filter(Q(code__icontains=search) | Q(created_by__email__icontains=search))
            coupons = filter_records(
                coupons, request.query_params,
                fields={"type": "type", "created_by": "created_by__email"},
            )
            validity = request.query_params.get("validity", "")
            if validity == "expired":
                coupons = coupons.filter(valid_to__lt=timezone.now())
            elif validity == "current":
                coupons = coupons.filter(valid_from__lte=timezone.now(), valid_to__gte=timezone.now())
            elif validity == "upcoming":
                coupons = coupons.filter(valid_from__gt=timezone.now())
            elif validity:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"validity": "Choose current, expired or upcoming."})
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
                {
                    "detail": "Coupons with recorded redemption history cannot be deleted to preserve order records and financial audit trails. Keep the coupon deactivated instead."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
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
    @extend_schema(parameters=[ListingQuerySerializer], responses=StorePayoutSerializer(many=True))
    def payouts(self, request: Request) -> Response:
        payouts = StorePayout.objects.select_related("store", "store__user", "wallet").order_by("-created", "-pk")
        payout_status = request.query_params.get("status")
        if payout_status:
            payouts = payouts.filter(status=payout_status)
        payouts = filter_records(
            payouts, request.query_params,
            search_fields=("reference", "store__name", "store__user__email", "wallet__user__email", "payout_method"),
            fields={"status": "status", "payout_method": "payout_method"},
            amount_field="amount",
        )
        return self.paginate_response(payouts, StorePayoutSerializer)

    @action(detail=False, methods=["get"], url_path="commission-wallet")
    @extend_schema(parameters=[ListingQuerySerializer], responses=dict)
    def commission_wallet(self, request: Request) -> Response:
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
        rows = filter_records(
            PlatformCommissionWithdrawal.objects.select_related('requested_by').order_by('-created', '-pk'),
            request.query_params,
            search_fields=("reference", "payout_method", "requested_by__email"),
            fields={"status": "status", "payout_method": "payout_method"}, amount_field="amount",
        )
        withdrawal_count, rows = record_page(rows, request.query_params)
        return Response({
            "earned": format(earned, '.2f'),
            "marketplace_commission": format(commission_earned, '.2f'),
            "official_stores_revenue": format(official_store_earned, '.2f'),
            "withdrawn_or_pending": format(withdrawn, '.2f'),
            "available": format(max(Decimal('0'), earned - withdrawn), '.2f'),
            "withdrawal_count": withdrawal_count,
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
    @extend_schema(request=TreasuryWithdrawalSerializer, responses={201: OpenApiTypes.OBJECT})
    def withdraw_commission(self, request: Request) -> Response:
        serializer = TreasuryWithdrawalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        # Serialize platform withdrawals to prevent concurrent double-withdrawals
        User.objects.select_for_update().order_by('pk').first()
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
            payout_method=serializer.validated_data['payout_method'],
            account_details=serializer.validated_data['account_details'],
            requested_by=request.user,
            reference=f'PCW-{generate(size=12)}'
        )
        from notification.events import operators
        for recipient in operators(admins_only=True):
            create_notification(
                recipient, f"Treasury withdrawal requested: {row.reference}", target=row,
                data={"event": "treasury_withdrawal_requested", "withdrawal_id": row.pk, "amount": str(row.amount)},
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
                    data={"payout_id": payout.pk, "amount": str(payout.amount), "email": False},
                )
                from utils.functions import send_mail
                bank_name = (payout.account_details or {}).get("bank_name", "")
                send_mail(
                    "payout-processed",
                    recipient_user.email,
                    {
                        "firstname": recipient_user.first_name,
                        "store_name": payout.store.name if payout.store else "",
                        "amount": str(payout.amount),
                        "reference": payout.reference,
                        "status": "Completed",
                        "bank_name": bank_name,
                        "subject": f"Merchant Payout Completed - {payout.reference}",
                    },
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
                    data={"payout_id": payout.pk, "amount": str(payout.amount), "email": False},
                )
                from utils.functions import send_mail
                bank_name = (payout.account_details or {}).get("bank_name", "")
                send_mail(
                    "payout-processed",
                    recipient_user.email,
                    {
                        "firstname": recipient_user.first_name,
                        "store_name": payout.store.name if payout.store else "",
                        "amount": str(payout.amount),
                        "reference": payout.reference,
                        "status": "Declined",
                        "bank_name": bank_name,
                        "notes": reason,
                        "subject": f"Merchant Payout Declined - {payout.reference}",
                    },
                )
            return Response({"detail": "Payout marked as rejected.", "payout": StorePayoutSerializer(payout).data})

