from core.listing_filters import ListingQuerySerializer, filter_records, record_page
from zoneinfo import ZoneInfo
from core.access import IsBusinessAdmin, is_admin, is_backoffice
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils.dateparse import parse_date, parse_datetime
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Prefetch, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from cart.models import CartItem
from payment.models import Order
from product.models import Product, ProductImg, Specification
from store.models import (
    MerchantWallet, Schedule, Store, StoreAddress, StoreEarningsLedger,
    StoreInfo, StorePayout,
)
from store.serializers import (
    MerchantTrackingSerializer, DashboardQuerySerializer, InventorySerializer, MerchantImageSerializer,
    MerchantPayoutCreateSerializer, MerchantProductSerializer, MerchantSpecificationSerializer,
    MerchantWalletSerializer, PayoutCreateSerializer, ScheduleSerializer,
    StoreAddressSerializer, StoreEarningsLedgerSerializer, StoreInfoSerializer,
    StoreBrandingImageSerializer, StoreOnboardingSerializer, StorePayoutSerializer, StoreSerializer,
)
from store.services import (
    calculate_merchant_financials, calculate_store_financials,
    get_or_create_merchant_wallet, request_merchant_payout,
)
from utils.functions import normalize_media_url


class MerchantPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


def invalidate_store_products(store):
    for product in Product.objects.filter(store=store):
        invalidate_catalog(product)


class StoreReviewViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Store.objects.none()
    serializer_class = StoreSerializer
    pagination_class = MerchantPagination

    def get_permissions(self):
        if self.action in ("approve",):
            return [IsBusinessAdmin()]
        return [IsAdminUser()]

    def get_queryset(self):
        stores = Store.objects.select_related('user', 'verified_by', 'blocked_by')
        status_filter = self.request.query_params.get('status', Store.STATUS_PENDING)
        if status_filter not in dict(Store.STATUS_CHOICES):
            raise ValidationError({'status': 'Choose pending, active or blocked.'})
        return stores.filter(status=status_filter).order_by('created', 'pk')

    @transaction.atomic
    def approve(self, request: Request, pk: str | None = None) -> Response:
        store = get_object_or_404(Store.objects.select_for_update(), pk=pk)
        if store.status == Store.STATUS_ACTIVE and store.verified_at:
            return Response(StoreSerializer(store).data)
        store.status = Store.STATUS_ACTIVE
        store.verified_at = timezone.now()
        store.verified_by = request.user
        store.blocked_reason = ''
        store.blocked_at = None
        store.blocked_by = None
        store.save(update_fields=[
            'status', 'verified_at', 'verified_by', 'blocked_reason',
            'blocked_at', 'blocked_by', 'updated',
        ])

        from notification.views import create_notification

        create_notification(
            recipient=store.user,
            actor=request.user,
            target=store,
            verb='store verified',
            description=f'{store.name} has been verified and is now public.',
            level='success',
            data={'event': 'store_verified', 'store_id': store.pk},
        )
        transaction.on_commit(lambda: invalidate_store_products(store))
        return Response(StoreSerializer(store).data)

    @transaction.atomic
    def block(self, request: Request, pk: str | None = None) -> Response:
        store = get_object_or_404(Store.objects.select_for_update(), pk=pk)
        if store.is_official:
            return Response(
                {"detail": "Official company stores cannot be blocked."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = serializers.CharField(allow_blank=False, trim_whitespace=True).run_validation(
            request.data.get('reason')
        )
        if store.status == Store.STATUS_BLOCKED and store.blocked_reason == reason:
            return Response(StoreSerializer(store).data)
        store.status = Store.STATUS_BLOCKED
        store.blocked_reason = reason
        store.blocked_at = timezone.now()
        store.blocked_by = request.user
        store.save(update_fields=['status', 'blocked_reason', 'blocked_at', 'blocked_by', 'updated'])

        from notification.views import create_notification

        create_notification(
            recipient=store.user,
            actor=request.user,
            target=store,
            verb='store blocked',
            description=f'{store.name} is unavailable. Reason: {reason}',
            level='warning',
            data={'event': 'store_blocked', 'store_id': store.pk},
        )
        transaction.on_commit(lambda: invalidate_store_products(store))
        return Response(StoreSerializer(store).data)


def invalidate_catalog(product):
    from cart.cache import invalidate_cart_cache
    from cart.models import Cart
    from product.cache import invalidate_product_cache

    invalidate_product_cache(product)
    for cart in Cart.objects.filter(cart_items__product=product, ordered=False).distinct():
        invalidate_cart_cache(cart)


class StoreViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                   mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                   viewsets.GenericViewSet):
    queryset = Store.objects.none()
    permission_classes = [IsAuthenticated]
    pagination_class = MerchantPagination
    serializer_class = StoreSerializer

    def get_object(self) -> Store:
        store = super().get_object()
        from core.activity import record_store_activity
        record_store_activity(store)
        return store

    def get_queryset(self):
        user = self.request.user
        if is_backoffice(user):
            # Strict separation: Admins and Staff never have access to a third-party seller's internal dashboard.
            # Proace Official Stores exception: all staff members and admins automatically have access to official stores.
            return Store.objects.filter(is_official=True).order_by('-created', '-pk')
        return Store.objects.filter(user=user, is_official=False).order_by('-created', '-pk')

    @extend_schema(responses={204: None})
    @action(detail=True, methods=['delete'], url_path='delete')
    def delete_store(self, request, pk=None):
        if not is_admin(request.user):
            raise PermissionDenied('Only administrators can delete official stores.')
        self.get_object().delete()
        return Response(status=204)

    @action(detail=True, methods=['put'], url_path='staff')
    def assign_staff(self, request, pk=None):
        if not is_admin(request.user):
            raise PermissionDenied('Only administrators can manage staff assignments.')
        # Staff-to-store assignment logic is deprecated: all authenticated staff members
        # have global backoffice access and automatic access to all official stores.
        return Response({
            'detail': 'Staff-to-store assignment is deprecated. All authenticated staff have global backoffice access and automatic access to all official stores.',
            'staff_ids': [],
        })

    def get_serializer_class(self):
        return StoreOnboardingSerializer if self.action in {'create', 'create_store'} else StoreSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if is_backoffice(user) and not is_admin(user):
            raise PermissionDenied('Only administrators can create official stores.')
        if is_admin(user):
            serializer.save(
                user=user,
                is_official=True,
                status=Store.STATUS_ACTIVE,
                verified_at=timezone.now(),
                verified_by=user,
            )
        else:
            # Serialize creation for this owner so simultaneous requests cannot exceed the limit.
            with transaction.atomic():
                type(user).objects.select_for_update().get(pk=user.pk)
                if Store.objects.filter(user=user).count() >= 10:
                    raise ValidationError({'detail': 'You can create a maximum of 10 stores.'})
                serializer.save(user=user)

    @action(detail=False, methods=['post'], url_path='create')
    def create_store(self, request):
        return self.create(request)

    @action(detail=True, methods=['get', 'patch'])
    def profile(self, request, pk=None):
        with transaction.atomic():
            store = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            profile = StoreInfo.objects.filter(store=store).order_by('pk').first()
            if request.method == 'GET':
                return Response(StoreInfoSerializer(profile).data if profile else {})
            serializer = StoreInfoSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save(store=store)
        return Response(serializer.data)

    @extend_schema(methods=['POST'], request=StoreBrandingImageSerializer, responses=StoreInfoSerializer)
    @extend_schema(methods=['DELETE'], request=None, responses=StoreInfoSerializer)
    @action(
        detail=True,
        methods=['post', 'delete'],
        url_path=r'profile-images/(?P<kind>avatar|banner)',
        parser_classes=[MultiPartParser, FormParser],
    )
    def profile_images(
        self,
        request: Request,
        pk: str | None = None,
        kind: str | None = None,
    ) -> Response:
        store = self.get_object()
        if kind not in {'avatar', 'banner'}:
            raise ValidationError({'detail': 'Choose an avatar or banner image.'})
        image = None
        if request.method == 'POST':
            serializer = StoreBrandingImageSerializer(data=request.data, context={'kind': kind})
            serializer.is_valid(raise_exception=True)
            image = serializer.validated_data['image']
        with transaction.atomic():
            self.get_queryset().select_for_update().get(pk=store.pk)
            profile = StoreInfo.objects.filter(store=store).order_by('pk').first()
            if profile is None:
                profile = StoreInfo(store=store)
            setattr(profile, f'{kind}_image', image or '')
            setattr(profile, f'{kind}_url', '')
            profile.save()
        return Response(StoreInfoSerializer(profile, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='connect-stripe')
    def connect_stripe(self, request, pk=None):
        """Create/reuse a Stripe Express account and return its onboarding URL."""
        store = self.get_object()
        if store.user_id != request.user.id:
            raise PermissionDenied('Only the store owner can connect Stripe.')
        secret = getattr(settings, 'STRIPE_SECRET', '')
        if not secret:
            raise ValidationError({'detail': 'Stripe Connect is not configured yet.'})
        try:
            import stripe
            stripe.api_key = secret
            wallet, _ = MerchantWallet.objects.get_or_create(user=request.user)
            if not wallet.stripe_account_id:
                account = stripe.Account.create(type='express', email=request.user.email, metadata={'store_id': str(store.pk), 'user_id': str(request.user.pk)})
                wallet.stripe_account_id = account.id
                wallet.save(update_fields=['stripe_account_id', 'updated'])
            # Stripe must return to the customer-facing Next.js app, not the API
            # process (which has no /merchant/settings route).
            base = f"{settings.FRONTEND_URL.rstrip('/')}/merchant/settings"
            link = stripe.AccountLink.create(account=wallet.stripe_account_id, refresh_url=base, return_url=base, type='account_onboarding')
            return Response({'url': link.url, 'stripe_account_id': wallet.stripe_account_id})
        except Exception as exc:
            raise ValidationError({'detail': f'Unable to start Stripe onboarding: {exc}'})

    @action(detail=True, methods=['get', 'put'], url_path='pickup-address')
    def pickup_address(self, request, pk=None):
        with transaction.atomic():
            store = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            address = StoreAddress.objects.filter(store=store, is_default=True).order_by('pk').first()
            if request.method == 'GET':
                return Response(StoreAddressSerializer(address).data if address else {})
            serializer = StoreAddressSerializer(address, data=request.data)
            serializer.is_valid(raise_exception=True)
            StoreAddress.objects.filter(store=store, is_default=True).update(is_default=False)
            serializer.save(store=store, is_default=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def onboarding(self, request, pk=None):
        store = self.get_object()
        from store.services import has_store_address
        checks = {
            'store_created': True,
            'contact_added': StoreInfo.objects.filter(store=store).exclude(email__isnull=True).exclude(email='').exists(),
            'pickup_address_added': has_store_address(store),
            'product_added': Product.objects.filter(store=store).exists(),
            'product_published': Product.objects.filter(store=store, visibility=True).exists(),
        }
        return Response({'steps': checks, 'complete': all(checks.values())})

    @staticmethod
    def fulfillment_value(order: Order, store: Store, field: str, fallback: object) -> object:
        fulfillment = order.fulfillments.filter(store=store).first()
        if order.status in {'cancelled', 'refunded'}:
            return order.status if field == 'status' else fallback
        return getattr(fulfillment, field) if fulfillment else fallback

    def store_orders(self, store):
        return Order.objects.filter(
            cart__cart_items__product__store=store,
        ).distinct().order_by('-created', '-pk')

    @action(detail=True, methods=['get'])
    def orders(self, request, pk=None):
        store = self.get_object()
        orders = self.store_orders(store)
        order_status = request.query_params.get('status')
        if order_status:
            if order_status not in dict(Order.ORDER_STATUS_CHOICE):
                raise ValidationError({'status': 'Invalid order status.'})
            if order_status in {'cancelled', 'refunded'}:
                orders = orders.filter(status=order_status)
            else:
                orders = orders.filter(
                    Q(fulfillments__store=store, fulfillments__status=order_status)
                    | Q(fulfillments__isnull=True, status=order_status)
                ).exclude(status__in=['cancelled', 'refunded'])

        search = str(request.query_params.get('search') or '').strip()
        if search:
            orders = orders.filter(
                Q(orderId__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(buyer_email__icontains=search)
                | Q(buyer_phone__icontains=search)
                | Q(tracking_number__icontains=search)
                | Q(fulfillments__tracking_number__icontains=search)
                | Q(cart__cart_items__product__title__icontains=search)
            )

        carrier = str(request.query_params.get('carrier') or '').strip()
        if carrier:
            orders = orders.filter(
                Q(fulfillments__store=store, fulfillments__carrier__iexact=carrier)
                | Q(fulfillments__isnull=True, carrier__iexact=carrier)
            )

        delivery_method = str(request.query_params.get('delivery_method') or '').strip()
        if delivery_method:
            orders = orders.filter(delivery__method__iexact=delivery_method)

        days = request.query_params.get('days')
        if days:
            try:
                num_days = int(days)
                if num_days > 0:
                    orders = orders.filter(created__gte=timezone.now() - timedelta(days=num_days))
            except (ValueError, TypeError):
                pass

        date_from = str(request.query_params.get('date_from') or '').strip()
        if date_from:
            dt_from = parse_datetime(date_from)
            if not dt_from:
                d_from = parse_date(date_from)
                if d_from:
                    dt_from = timezone.make_aware(datetime.combine(d_from, datetime.min.time()))
            if dt_from:
                orders = orders.filter(created__gte=dt_from)

        date_to = str(request.query_params.get('date_to') or '').strip()
        if date_to:
            dt_to = parse_datetime(date_to)
            if not dt_to:
                d_to = parse_date(date_to)
                if d_to:
                    dt_to = timezone.make_aware(datetime.combine(d_to, datetime.max.time()))
            if dt_to:
                orders = orders.filter(created__lte=dt_to)

        ordering = str(request.query_params.get('ordering') or '-created').strip()
        allowed_orderings = {
            '-created': ('-created', '-pk'),
            'created': ('created', 'pk'),
            '-updated': ('-updated', '-pk'),
            'updated': ('updated', 'pk'),
        }
        order_by_fields = allowed_orderings.get(ordering, ('-created', '-pk'))
        orders = orders.distinct().order_by(*order_by_fields)

        orders = orders.select_related('user', 'delivery').prefetch_related(Prefetch(
            'cart__cart_items', queryset=CartItem.objects.filter(product__store=store)
            .select_related('product'), to_attr='merchant_items',
        ))
        page = self.paginate_queryset(orders)
        data = [
            {
                "id": order.pk,
                "reference": order.orderId,
                "status": self.fulfillment_value(order, store, "status", order.status),
                "order_status": order.status,
                "carrier": self.fulfillment_value(
                    order, store, "carrier", order.carrier
                )
                or "USPS",
                "tracking_number": self.fulfillment_value(
                    order, store, "tracking_number", order.tracking_number
                )
                or "",
                "tracking_url": order.tracking_url
                if order.fulfillments.count() <= 1
                else "",
                "shipped_at": self.fulfillment_value(
                    order, store, "shipped_at", order.shipped_at
                ),
                "delivered_at": self.fulfillment_value(
                    order, store, "delivered_at", order.delivered_at
                ),
                "tracking_events": order.tracking_events or [],
                "shipping_address": order.address_snapshot or {},
                "customer": {
                    "name": f"{order.user.first_name} {order.user.last_name}".strip()
                    if order.user
                    else "",
                    "email": (order.user.email if order.user else "")
                    or getattr(order, "buyer_email", "")
                    or "",
                    "phone": str(
                        getattr(order.user, "phone1", "")
                        or getattr(order, "buyer_phone", "")
                        or ""
                    )
                    if order.user
                    else str(getattr(order, "buyer_phone", "") or ""),
                },
                "created": order.created,
                "ordered": order.ordered,
                "has_physical_items": (
                    any(
                        not bool(it.get("is_digital"))
                        for it in (order.items_snapshot or [])
                        if not it.get("store") or str(it.get("store")) == str(store.pk)
                    )
                    if order.items_snapshot
                    else any(
                        not getattr(item.product, "is_digital", False)
                        for item in getattr(order.cart, "merchant_items", [])
                    )
                ),
                "items": [
                    {
                        "product": item.product_id,
                        "title": item.product.title,
                        "quantity": item.quantity,
                        "is_digital": getattr(item.product, "is_digital", False),
                    }
                    for item in getattr(order.cart, "merchant_items", [])
                ]
                or [
                    {
                        "product": it.get("product", 0),
                        "title": it.get("title", "Item"),
                        "quantity": it.get("quantity", 1),
                        "is_digital": bool(it.get("is_digital")),
                    }
                    for it in (order.items_snapshot or [])
                    if not it.get("store") or str(it.get("store")) == str(store.pk)
                ],
            }
            for order in page
        ]
        return self.get_paginated_response(data)

    @action(
        detail=True,
        methods=["patch", "post"],
        url_path=r"orders/(?P<order_pk>[^/.]+)/tracking",
    )
    @extend_schema(request=MerchantTrackingSerializer, responses=dict)
    @transaction.atomic
    def update_order_tracking(
        self, request: Request, pk: str | None = None, order_pk: str | None = None
    ) -> Response:
        store = self.get_object()
        order_filter = (
            Q(pk=int(order_pk)) if str(order_pk).isdigit() else Q(orderId=order_pk)
        )
        order = Order.objects.filter(order_filter).select_for_update().first()
        if not order:
            raise Http404("Order not found.")
        from payment.fulfillment import update_fulfillment

        belongs_to_store = any(
            row.get("store") == store.pk for row in order.items_snapshot or []
        )
        if not belongs_to_store and order.cart_id:
            belongs_to_store = order.cart.cart_items.filter(
                product__store=store
            ).exists()
        if not belongs_to_store:
            raise Http404("Order does not belong to this store.")
        serializer = MerchantTrackingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from payment.fulfillment import ensure_fulfillments
        ensure_fulfillments(order)
        current = order.fulfillments.get(store=store)
        previous = (current.status, current.carrier, current.tracking_number)
        fulfillment = update_fulfillment(
            order,
            store,
            data.get("status"),
            data["carrier"],
            data["tracking_number"],
        )
        last_event = (order.tracking_events or [{}])[-1]
        if previous == (fulfillment.status, fulfillment.carrier, fulfillment.tracking_number) and (
            not data["event_description"] or last_event.get("description") == data["event_description"]
        ):
            return Response({"id": order.pk, "reference": order.orderId, "status": order.status})
        event_description = data["event_description"]
        if event_description or data["tracking_number"] or data.get("status"):
            events = list(order.tracking_events or [])
            events.append(
                {
                    "status": fulfillment.status,
                    "store_id": store.pk,
                    "description": event_description
                    or f"Store shipment marked {fulfillment.status}.",
                    "timestamp": timezone.now().isoformat(),
                }
            )
            order.tracking_events = events

        order.save(
            update_fields=[
                "status",
                "carrier",
                "tracking_number",
                "shipped_at",
                "delivered_at",
                "tracking_events",
                "updated",
            ]
        )

        from notification.views import create_notification

        create_notification(
            recipient=order.user,
            actor=store.user,
            target=order,
            verb=f"Order #{order.orderId} — {store.name} {fulfillment.status.title()}",
            description=(
                f"Your {store.name} shipment is {fulfillment.status}. Carrier: {fulfillment.carrier}, Tracking #{fulfillment.tracking_number}"
                if fulfillment.carrier and fulfillment.tracking_number
                else f"Your {store.name} shipment is {fulfillment.status}. Tracking #{fulfillment.tracking_number}"
                if fulfillment.tracking_number
                else f"Your {store.name} shipment is {fulfillment.status}."
            ),
            data={
                "event": "order_tracking_update",
                "email": fulfillment.status not in {"shipped", "delivered", "picked up", "confirmed"},
                "order_id": order.pk,
                "store_id": store.pk,
                "tracking_number": fulfillment.tracking_number,
                "status": fulfillment.status,
            },
        )

        recipient_email = str(order.buyer_email or (order.user.email if order.user else "") or "").strip()
        if recipient_email and fulfillment.status == "shipped":
            from utils.functions import send_mail
            send_mail(
                "order-shipped",
                recipient_email,
                {
                    "firstname": (order.user.first_name if order.user else ""),
                    "orderId": order.orderId,
                    "carrier": fulfillment.carrier,
                    "tracking_number": fulfillment.tracking_number or "",
                    "tracking_url": order.tracking_url or "",
                    "store_name": store.name,
                    "subject": f"Order #{order.orderId} Has Shipped",
                },
            )
        elif recipient_email and fulfillment.status == "delivered":
            from utils.functions import send_mail
            send_mail(
                "delivery-confirmation",
                recipient_email,
                {
                    "firstname": (order.user.first_name if order.user else ""),
                    "orderId": order.orderId,
                    "carrier": fulfillment.carrier,
                    "tracking_number": fulfillment.tracking_number,
                    "store_name": store.name,
                    "subject": f"Order #{order.orderId} Delivered",
                },
            )
        elif recipient_email and fulfillment.status == "picked up":
            from utils.functions import send_mail
            send_mail(
                "order-picked-up",
                recipient_email,
                {
                    "firstname": (order.user.first_name if order.user else ""),
                    "orderId": order.orderId,
                    "store_name": store.name,
                    "subject": f"Order #{order.orderId} Picked Up",
                },
            )
        elif recipient_email and fulfillment.status == "confirmed":
            from utils.functions import send_mail
            send_mail(
                "order-confirm",
                recipient_email,
                {
                    "firstname": (order.user.first_name if order.user else ""),
                    "orderId": order.orderId,
                    "store_name": store.name,
                    "subject": f"Order #{order.orderId} Confirmed",
                },
            )

        return Response(
            {
                "id": order.pk,
                "reference": order.orderId,
                "order_status": order.status,
                "status": fulfillment.status,
                "carrier": fulfillment.carrier,
                "tracking_number": fulfillment.tracking_number,
                "tracking_url": order.tracking_url,
                "shipped_at": fulfillment.shipped_at.isoformat()
                if fulfillment.shipped_at
                else None,
                "delivered_at": fulfillment.delivered_at.isoformat()
                if fulfillment.delivered_at
                else None,
                "tracking_events": order.tracking_events,
            }
        )

    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        store = self.get_object()
        query = DashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        with timezone.override(ZoneInfo(query.validated_data["time_zone"])):
            days = query.validated_data["days"]
            threshold = query.validated_data["low_stock_threshold"]
            today = timezone.localdate()
            start = today - timedelta(days=days - 1)
            products = Product.objects.filter(store=store)
            orders = self.store_orders(store).filter(
                created__date__gte=start, created__date__lte=today
            )
            sales_orders = orders.filter(
                ordered=True,
                status__in=["confirmed", "shipped", "delivered", "picked up"],
            )
            items = CartItem.objects.filter(
                product__store=store, cart__in=sales_orders.values("cart_id")
            )
            line_value = ExpressionWrapper(
                F("quantity")
                * F("product__price")
                * (100 - F("product__discount"))
                / Decimal("100.0"),
                output_field=DecimalField(max_digits=24, decimal_places=2),
            )
            totals = items.aggregate(units=Sum("quantity"), value=Sum(line_value))
            financials = calculate_store_financials(store)

            inventory = products.aggregate(
                total=Count("id"),
                published=Count("id", filter=Q(visibility=True)),
                drafts=Count("id", filter=Q(visibility=False)),
                out_of_stock=Count("id", filter=Q(is_digital=False, available=0)),
                low_stock=Count(
                    "id", filter=Q(available__gt=0, available__lte=threshold)
                ),
                units=Sum("available"),
            )
            inventory['units'] = inventory['units'] or 0
            trend = {row['day']: row['count'] for row in orders.order_by().annotate(
                day=TruncDate('created')).values('day').annotate(count=Count('pk', distinct=True))}
            top_products = items.values('product_id', 'product__title').annotate(
                units=Sum('quantity')).order_by('-units', 'product_id')[:10]
            return Response({
                'period': {'from': start, 'to': today, 'days': days, 'time_zone': query.validated_data['time_zone']},
                'inventory': inventory,
                'orders': {'total': orders.count(), 'by_status': list(orders.order_by().values('status').annotate(count=Count('pk', distinct=True)))},
                'sales': {'units': totals['units'] or 0,
                          'estimated_item_value': format(totals['value'] or Decimal('0'), '.2f'),
                          'basis': 'Current item prices for confirmed, shipped, delivered and picked-up orders. Excludes coupons, tax, shipping and fees; not payout revenue.'},
                'wallet': financials,
                'orders_by_day': [{'date': start + timedelta(days=i), 'count': trend.get(start + timedelta(days=i), 0)} for i in range(days)],
                'top_products': list(top_products),
                'low_stock_products': list(products.filter(available__lte=threshold).order_by('available', 'pk').values('id', 'title', 'available')[:20]),
            })

    @action(detail=False, methods=['get'], url_path='wallet')
    def merchant_wallet(self, request):
        """
        Consolidated financial wallet for the authenticated vendor across all their stores.
        """
        data = calculate_merchant_financials(request.user)
        return Response(MerchantWalletSerializer(data).data)

    @action(detail=False, methods=['get'], url_path='wallet/ledger')
    @extend_schema(parameters=[ListingQuerySerializer], responses=StoreEarningsLedgerSerializer(many=True))
    def merchant_ledger(self, request: Request) -> Response:
        """
        Granular ledger entries for all stores owned by the merchant.
        Supports query params: ?store_id=X, ?status=pending|available|completed|reversed, ?entry_type=sale|payout|fee|refund
        """
        user_stores = Store.objects.filter(user=request.user)
        entries = StoreEarningsLedger.objects.filter(store__in=user_stores).select_related('store', 'wallet')

        store_id = request.query_params.get('store_id')
        if store_id:
            entries = entries.filter(store_id=store_id)

        status_filter = request.query_params.get('status')
        if status_filter:
            entries = entries.filter(status=status_filter)

        entry_type_filter = request.query_params.get('entry_type')
        if entry_type_filter:
            entries = entries.filter(entry_type=entry_type_filter)

        entries = filter_records(
            entries.order_by("-created", "-pk"), request.query_params,
            search_fields=("reference", "description", "store__name"),
            fields={"status": "status", "entry_type": "entry_type"}, amount_field="net_amount",
        )
        page = self.paginate_queryset(entries)
        serializer = StoreEarningsLedgerSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get', 'post'], url_path='wallet/payouts')
    @transaction.atomic
    def merchant_payouts(self, request):
        """
        Unified payout requests and listing across all stores for the merchant.
        """
        user_stores = Store.objects.filter(user=request.user)
        wallet = get_or_create_merchant_wallet(request.user)

        if request.method == 'GET':
            payouts = StorePayout.objects.filter(
                Q(wallet=wallet) | Q(store__in=user_stores)
            ).select_related('store').distinct().order_by('-created')
            page = self.paginate_queryset(payouts)
            serializer = StorePayoutSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        if is_backoffice(request.user) and not is_admin(request.user):
            raise PermissionDenied('Only administrators or store owners can request payouts.')
        serializer = MerchantPayoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        payout_method = serializer.validated_data['payout_method']
        account_details = serializer.validated_data.get('account_details', {})
        notes = serializer.validated_data.get('notes', '')

        store = None
        store_id = serializer.validated_data.get('store_id')
        if store_id:
            store = get_object_or_404(user_stores, pk=store_id)
        else:
            store = user_stores.first()

        if store and store.is_official:
            raise ValidationError({
                'detail': 'Official company store earnings are consolidated into the Platform Treasury and cannot be withdrawn via merchant payouts. Withdrawals are managed by administrators at /admin/commission.'
            })

        # Synchronize merchant financials to ensure fresh balances
        calculate_merchant_financials(request.user)

        payout = request_merchant_payout(
            user=request.user,
            amount=amount,
            payout_method=payout_method,
            account_details=account_details,
            store=store,
            notes=notes,
        )

        from notification.views import create_notification, notify_staff
        notify_staff(
            verb=f"New Merchant Payout Request: ${amount}",
            description=f"Merchant '{request.user.email}' requested a payout of ${amount} (Ref: {payout.reference}).",
            data={"payout_id": payout.pk, "amount": str(amount), "user_id": request.user.pk},
        )
        create_notification(
            recipient=request.user,
            verb=f"Payout Request Submitted: ${amount}",
            description=f"Your payout request of ${amount} (Ref: {payout.reference}) has been submitted and is under review.",
            data={"payout_id": payout.pk, "amount": str(amount)},
        )

        return Response(StorePayoutSerializer(payout).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='payouts')
    @transaction.atomic
    @extend_schema(methods=["GET"], parameters=[ListingQuerySerializer], responses=StorePayoutSerializer(many=True))
    def payouts(self, request: Request, pk: str | None = None) -> Response:
        store = self.get_object()
        if request.method == 'GET':
            payouts = filter_records(
                store.payouts.order_by("-created", "-pk"), request.query_params,
                search_fields=("reference", "notes", "payout_method"),
                fields={"status": "status", "payout_method": "payout_method"}, amount_field="amount",
            )
            if request.query_params.get("paginated") == "1":
                count, page = record_page(payouts, request.query_params)
                serializer = StorePayoutSerializer(page, many=True)
                return Response({"count": count, "results": serializer.data})
            return Response(StorePayoutSerializer(payouts, many=True).data)

        if store.is_official:
            raise ValidationError({
                'detail': 'Official company store earnings are consolidated into the Platform Treasury and cannot be withdrawn via merchant payouts. Withdrawals are managed by administrators at /admin/commission.'
            })

        if store.user_id != request.user.pk:
            raise PermissionDenied('Only the store owner can initiate a withdrawal.')
        serializer = PayoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        payout_method = serializer.validated_data['payout_method']
        account_details = serializer.validated_data.get('account_details', {})
        notes = serializer.validated_data.get('notes', '')

        # Validate store-specific balance
        store_fin = calculate_store_financials(store)
        store_available = Decimal(store_fin['available_balance'])
        if amount > store_available:
            raise ValidationError({
                'detail': f'Requested payout amount (${amount}) exceeds available cleared balance (${store_available}).'
            })

        payout = request_merchant_payout(
            user=request.user,
            amount=amount,
            payout_method=payout_method,
            account_details=account_details,
            store=store,
            notes=notes,
        )

        from notification.views import create_notification, notify_staff
        notify_staff(
            verb=f"New Merchant Payout Request: ${amount}",
            description=f"Store '{store.name}' requested a payout of ${amount} (Ref: {payout.reference}).",
            data={"payout_id": payout.pk, "store_id": store.pk, "amount": str(amount)},
        )
        create_notification(
            recipient=store.user,
            verb=f"Payout Request Submitted: ${amount}",
            description=f"Your payout request of ${amount} (Ref: {payout.reference}) has been submitted and is under review.",
            data={"payout_id": payout.pk, "amount": str(amount)},
        )

        return Response(StorePayoutSerializer(payout).data, status=status.HTTP_201_CREATED)



@extend_schema_view(
    list=extend_schema(operation_id='merchant_products_list'),
    retrieve=extend_schema(operation_id='merchant_product_retrieve'),
)
class MerchantProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.none()
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantProductSerializer
    pagination_class = MerchantPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['title', 'description', 'tags__name']
    ordering_fields = ['created', 'updated', 'price', 'available', 'title', 'sales']
    ordering = ['-created', '-pk']

    def get_store(self) -> Store:
        store = get_object_or_404(
            StoreViewSet.get_queryset(self),
            pk=self.kwargs['store_pk'],
        )
        from core.activity import record_store_activity
        record_store_activity(store)
        return store

    def validate_store_publication(self, serializer: MerchantProductSerializer) -> None:
        from store.services import has_store_address
        visible = serializer.validated_data.get('visibility', getattr(serializer.instance, 'visibility', False))
        if visible and not has_store_address(self.get_store()):
            raise ValidationError({'visibility': 'Add a complete default store address before publishing physical or digital products.'})

    def get_queryset(self):
        products = Product.objects.filter(store=self.get_store()).prefetch_related('tags', 'images').select_related('specification')
        products = filter_records(
            products, self.request.query_params,
            fields={"is_digital": "is_digital", "product_type": "product_type"},
        )
        if self.action in {'update', 'partial_update'}:
            # Lock only the product: the optional specification uses an outer join.
            products = products.select_for_update(of=('self',))
        if self.action == 'list':
            visibility = self.request.query_params.get('visibility')
            if visibility is not None:
                if visibility not in {'true', 'false'}:
                    raise ValidationError({'visibility': 'Use true or false.'})
                products = products.filter(visibility=visibility == 'true')
            category = self.request.query_params.get('category')
            if category:
                products = products.filter(category=category)
            stock = self.request.query_params.get('stock')
            filters = {'out': Q(is_digital=False, available=0), 'low': Q(is_digital=False, available__gt=0, available__lte=5), 'in': Q(is_digital=True) | Q(available__gt=0)}
            if stock is not None:
                if stock not in filters:
                    raise ValidationError({'stock': 'Use in, low or out.'})
                products = products.filter(filters[stock])
        return products

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        store = self.get_store()
        if serializer.validated_data.get('product_type') == Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK and not store.is_official:
            raise ValidationError({'product_type': 'ClickBank partner offers can only be configured for official platform catalog stores.'})
        self.validate_store_publication(serializer)
        product = serializer.save(store=store)
        if product.is_digital or product.product_type == Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK:
            Specification.objects.filter(product=product).delete()
        transaction.on_commit(lambda: invalidate_catalog(product))

    @transaction.atomic
    def perform_update(self, serializer):
        store = self.get_store()
        if serializer.validated_data.get('product_type') == Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK and not store.is_official:
            raise ValidationError({'product_type': 'ClickBank partner offers can only be configured for official platform catalog stores.'})
        self.validate_store_publication(serializer)
        product = serializer.save()
        if product.is_digital or product.product_type == Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK:
            Specification.objects.filter(product=product).delete()
        transaction.on_commit(lambda: invalidate_catalog(product))

    def perform_destroy(self, instance):
        raise ValidationError({'detail': 'Unpublish products with visibility=false to preserve carts and order history.'})

    @action(detail=True, methods=['patch'])
    def inventory(self, request, store_pk=None, pk=None):
        serializer = InventorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=pk, store=self.get_store())
            if product.is_digital:
                raise ValidationError({'available': 'Digital products have unlimited inventory.'})
            product.available = serializer.validated_data['available']
            product.save(update_fields=['available', 'updated'])
            transaction.on_commit(lambda: invalidate_catalog(product))
        return Response(self.get_serializer(product).data)

    @action(detail=True, methods=['get', 'post'])
    def images(self, request, store_pk=None, pk=None):
        product = self.get_object()
        if request.method == 'GET':
            return Response(MerchantImageSerializer(product.images.all(), many=True, context={'request': request}).data)
        serializer = MerchantImageSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        img_obj = serializer.save(product=product)
        is_cover = request.data.get('is_cover') in {'true', '1', True} or not product.image_url
        if is_cover and img_obj.image:
            image_url = normalize_media_url(request.build_absolute_uri(img_obj.image.url) if request else img_obj.image.url)
            product.image_url = image_url
            product.save(update_fields=['image_url', 'updated'])
        invalidate_catalog(product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path=r'images/(?P<image_pk>\d+)/cover')
    def set_cover_image(self, request, store_pk=None, pk=None, image_pk=None):
        product = self.get_object()
        img = get_object_or_404(ProductImg, pk=image_pk, product=product)
        if img.image:
            image_url = normalize_media_url(request.build_absolute_uri(img.image.url) if request else img.image.url)
            product.image_url = image_url
            product.save(update_fields=['image_url', 'updated'])
            invalidate_catalog(product)
        return Response(self.get_serializer(product).data)

    @action(detail=True, methods=['get', 'post'], url_path='digital-file', parser_classes=[MultiPartParser, FormParser])
    def digital_file(self, request, store_pk=None, pk=None):
        product = self.get_object()
        if request.method == 'GET':
            from django.core.files.storage import default_storage
            from django.http import HttpResponseRedirect
            from urllib.parse import urlparse
            raw = (product.digital_file_url or '').strip()
            path = urlparse(raw).path.lstrip('/')
            bucket = getattr(settings, 'MINIO_BUCKET_NAME', 'commerce-images')
            known_prefixes = (
                f'{bucket}/media/',
                f'{bucket}/',
                'commerce-images/media/',
                'commerce-images/',
                'commerce-media/media/',
                'commerce-media/',
                'media/',
            )
            for prefix in known_prefixes:
                if path.startswith(prefix):
                    path = path[len(prefix):]
                    break

            variants = [path]
            if path.startswith('media/'):
                variants.append(path[len('media/'):])
            else:
                variants.append(f'media/{path}')

            resolved_path = None
            for candidate in variants:
                if candidate and default_storage.exists(candidate):
                    resolved_path = candidate
                    break

            if not resolved_path:
                return Response({'detail': 'This product has no uploaded digital file.'}, status=404)
            response = HttpResponseRedirect(default_storage.url(resolved_path))
            response['Cache-Control'] = 'private, no-store'
            return response
        file_obj = request.FILES.get('file')
        if not file_obj:
            raise ValidationError({'file': 'Please select a digital file to upload.'})

        # Max file size 50 MB
        if file_obj.size > 50 * 1024 * 1024:
            raise ValidationError({'file': 'Digital files must be 50 MB or smaller.'})

        from django.core.files.storage import default_storage
        import os
        from uuid import uuid4

        safe_name = f"digital_products/{product.store_id}/{product.id}/{uuid4().hex[:12]}_{file_obj.name}"
        saved_path = default_storage.save(safe_name, file_obj)
        # Store the stable object key. Signed URLs are generated only after an
        # authenticated purchase or a backoffice audit request.
        file_url = saved_path

        product.is_digital = True
        product.digital_file_url = file_url
        product.weight = Decimal('0.00')
        image_exts = ('.jpg', '.jpeg', '.png', '.webp', '.svg', '.gif', '.avif', '.bmp', '.tiff')
        clean_name = file_obj.name.lower()
        update_fields = ['is_digital', 'digital_file_url', 'weight', 'updated']
        if clean_name.endswith(image_exts):
            raw_url = default_storage.url(saved_path)
            public_image_url = normalize_media_url(request.build_absolute_uri(raw_url) if request else raw_url)
            if not product.image_url:
                product.image_url = public_image_url
                update_fields.append('image_url')
            product.digital_preview_watermark = True
            update_fields.append('digital_preview_watermark')
        else:
            product.digital_preview_watermark = False
            update_fields.append('digital_preview_watermark')
        product.save(update_fields=update_fields)
        invalidate_catalog(product)

        return Response({
            'digital_file_url': file_url,
            'image_url': product.image_url,
            'digital_preview_watermark': product.digital_preview_watermark,
            'file_name': file_obj.name,
            'file_size': file_obj.size,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path=r'images/(?P<image_pk>\d+)')
    def delete_image(self, request, store_pk=None, pk=None, image_pk=None):
        product = self.get_object()
        get_object_or_404(ProductImg, pk=image_pk, product=product).delete()
        invalidate_catalog(product)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get', 'put'])
    def specifications(self, request, store_pk=None, pk=None):
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=pk, store=self.get_store())
            if product.is_digital or product.product_type == Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK:
                return Response(
                    {'error': 'Digital and affiliate partner products cannot have physical specifications.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            specification = Specification.objects.filter(product=product).first()
            if request.method == 'GET':
                return Response(MerchantSpecificationSerializer(specification).data if specification else {})
            serializer = MerchantSpecificationSerializer(specification, data=request.data, context={'product': product})
            serializer.is_valid(raise_exception=True)
            serializer.save(product=product)
            transaction.on_commit(lambda: invalidate_catalog(product))
        return Response(serializer.data)


class VisibilityScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.none()
    permission_classes = [IsAuthenticated]
    serializer_class = ScheduleSerializer
    pagination_class = MerchantPagination
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return Schedule.objects.filter(store__in=StoreViewSet.get_queryset(self)).order_by('make_visible_at', 'pk')

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        if not StoreViewSet.get_queryset(self).filter(pk=product.store_id).exists():
            raise ValidationError({'product': 'Choose a product from your store.'})
        if serializer.validated_data['make_visible_at'] <= timezone.now():
            raise ValidationError({'make_visible_at': 'Choose a future time.'})
        serializer.save(store=product.store)
