from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Prefetch, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
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
    DashboardQuerySerializer, InventorySerializer, MerchantImageSerializer,
    MerchantPayoutCreateSerializer, MerchantProductSerializer, MerchantSpecificationSerializer,
    MerchantWalletSerializer, PayoutCreateSerializer, ScheduleSerializer,
    StoreAddressSerializer, StoreEarningsLedgerSerializer, StoreInfoSerializer,
    StoreOnboardingSerializer, StorePayoutSerializer, StoreSerializer,
)
from store.services import (
    calculate_merchant_financials, calculate_store_financials,
    get_or_create_merchant_wallet, request_merchant_payout,
)


class MerchantPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


def invalidate_store_products(store):
    for product in Product.objects.filter(store=store):
        invalidate_catalog(product)


class StoreReviewViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Store.objects.none()
    serializer_class = StoreSerializer
    permission_classes = [IsAdminUser]
    pagination_class = MerchantPagination

    def get_queryset(self):
        stores = Store.objects.select_related('user', 'verified_by', 'blocked_by')
        status_filter = self.request.query_params.get('status', Store.STATUS_PENDING)
        if status_filter not in dict(Store.STATUS_CHOICES):
            raise ValidationError({'status': 'Choose pending, active or blocked.'})
        return stores.filter(status=status_filter).order_by('created', 'pk')

    @transaction.atomic
    def approve(self, request, pk=None):
        store = get_object_or_404(Store.objects.select_for_update(), pk=pk)
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
    def block(self, request, pk=None):
        reason = serializers.CharField(allow_blank=False, trim_whitespace=True).run_validation(
            request.data.get('reason')
        )
        store = get_object_or_404(Store.objects.select_for_update(), pk=pk)
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

    def get_queryset(self):
        return Store.objects.filter(user=self.request.user).order_by('-created', '-pk')

    def get_serializer_class(self):
        return StoreOnboardingSerializer if self.action in {'create', 'create_store'} else StoreSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, 'is_superuser', False):
            serializer.save(
                user=user,
                is_official=True,
                status=Store.STATUS_ACTIVE,
                verified_at=timezone.now(),
                verified_by=user,
            )
        else:
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
        checks = {
            'store_created': True,
            'contact_added': StoreInfo.objects.filter(store=store).exclude(email__isnull=True).exclude(email='').exists(),
            'pickup_address_added': StoreAddress.objects.filter(store=store, is_default=True).exists(),
            'product_added': Product.objects.filter(store=store).exists(),
            'product_published': Product.objects.filter(store=store, visibility=True).exists(),
        }
        return Response({'steps': checks, 'complete': all(checks.values())})

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
            orders = orders.filter(status=order_status)
        orders = orders.prefetch_related(Prefetch(
            'cart__cart_items', queryset=CartItem.objects.filter(product__store=store)
            .select_related('product'), to_attr='merchant_items',
        ))
        page = self.paginate_queryset(orders)
        data = [{
            'id': order.pk, 'reference': order.orderId, 'status': order.status,
            'carrier': order.carrier or 'USPS',
            'tracking_number': order.tracking_number or '',
            'tracking_url': order.tracking_url or '',
            'shipped_at': order.shipped_at,
            'delivered_at': order.delivered_at,
            'tracking_events': order.tracking_events or [],
            'created': order.created, 'ordered': order.ordered,
            'items': [{'product': item.product_id, 'title': item.product.title,
                       'quantity': item.quantity} for item in order.cart.merchant_items],
        } for order in page]
        return self.get_paginated_response(data)

    @action(detail=True, methods=['patch', 'post'], url_path=r'orders/(?P<order_pk>\d+)/tracking')
    @transaction.atomic
    def update_order_tracking(self, request, pk=None, order_pk=None):
        store = self.get_object()
        order = get_object_or_404(self.store_orders(store).select_for_update(), pk=order_pk)
        tracking_number = str(request.data.get('tracking_number', '')).strip()
        carrier = str(request.data.get('carrier', 'USPS')).strip() or 'USPS'
        new_status = request.data.get('status')

        if tracking_number:
            order.tracking_number = tracking_number
            order.carrier = carrier
            if not order.shipped_at:
                order.shipped_at = timezone.now()
            if order.status in ('pending', 'confirmed'):
                order.status = 'shipped'

        if new_status and new_status in dict(Order.ORDER_STATUS_CHOICE):
            order.status = new_status
            if new_status == 'shipped' and not order.shipped_at:
                order.shipped_at = timezone.now()
            elif new_status == 'delivered' and not order.delivered_at:
                order.delivered_at = timezone.now()

        event_description = request.data.get('event_description')
        if event_description or tracking_number:
            events = list(order.tracking_events or [])
            events.append({
                'status': order.status,
                'description': event_description or f"Package marked {order.status.upper()} via {carrier} (Tracking #{tracking_number or 'N/A'})",
                'timestamp': timezone.now().isoformat(),
            })
            order.tracking_events = events

        order.save(update_fields=['status', 'carrier', 'tracking_number', 'shipped_at', 'delivered_at', 'tracking_events', 'updated'])

        from notification.views import create_notification
        create_notification(
            recipient=order.user,
            actor=store.user,
            target=order,
            verb=f"Order #{order.orderId} {order.status.title()}",
            description=f"Your order status has been updated to {order.status}. Carrier: {order.carrier}, Tracking #{order.tracking_number or 'N/A'}",
            data={"event": "order_tracking_update", "order_id": order.pk, "tracking_number": order.tracking_number, "status": order.status},
        )

        return Response({
            'id': order.pk,
            'reference': order.orderId,
            'status': order.status,
            'carrier': order.carrier,
            'tracking_number': order.tracking_number,
            'tracking_url': order.tracking_url,
            'shipped_at': order.shipped_at,
            'delivered_at': order.delivered_at,
            'tracking_events': order.tracking_events,
        })


    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        store = self.get_object()
        query = DashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        days = query.validated_data['days']
        threshold = query.validated_data['low_stock_threshold']
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)
        products = Product.objects.filter(store=store)
        orders = self.store_orders(store).filter(created__date__gte=start, created__date__lte=today)
        sales_orders = orders.filter(ordered=True, status__in=['confirmed', 'shipped', 'delivered', 'picked up'])
        items = CartItem.objects.filter(product__store=store, cart__in=sales_orders.values('cart_id'))
        line_value = ExpressionWrapper(
            F('quantity') * F('product__price') * (100 - F('product__discount')) / Decimal('100.0'),
            output_field=DecimalField(max_digits=24, decimal_places=2),
        )
        totals = items.aggregate(units=Sum('quantity'), value=Sum(line_value))
        financials = calculate_store_financials(store)

        inventory = products.aggregate(
            total=Count('id'), published=Count('id', filter=Q(visibility=True)),
            drafts=Count('id', filter=Q(visibility=False)),
            out_of_stock=Count('id', filter=Q(available=0)),
            low_stock=Count('id', filter=Q(available__gt=0, available__lte=threshold)),
            units=Sum('available'),
        )
        inventory['units'] = inventory['units'] or 0
        trend = {row['day']: row['count'] for row in orders.order_by().annotate(
            day=TruncDate('created')).values('day').annotate(count=Count('pk', distinct=True))}
        top_products = items.values('product_id', 'product__title').annotate(
            units=Sum('quantity')).order_by('-units', 'product_id')[:10]
        return Response({
            'period': {'from': start, 'to': today, 'days': days},
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
    def merchant_ledger(self, request):
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
    def payouts(self, request, pk=None):
        store = self.get_object()
        if request.method == 'GET':
            payouts = store.payouts.all()
            serializer = StorePayoutSerializer(payouts, many=True)
            return Response(serializer.data)

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

    def get_store(self):
        return get_object_or_404(
            Store,
            pk=self.kwargs['store_pk'],
            user=self.request.user,
        )

    def validate_store_publication(self, serializer):
        if serializer.validated_data.get('visibility') is True:
            store = serializer.instance.store if serializer.instance else self.get_store()
            if store.status != Store.STATUS_ACTIVE or not store.verified_at:
                raise ValidationError({
                    'visibility': 'A staff-verified store is required before publishing products.'
                })

    def get_queryset(self):
        products = Product.objects.filter(store=self.get_store()).prefetch_related('tags', 'images').select_related('specification')
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
            filters = {'out': Q(available=0), 'low': Q(available__gt=0, available__lte=5), 'in': Q(available__gt=0)}
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
        self.validate_store_publication(serializer)
        product = serializer.save(store=self.get_store())
        transaction.on_commit(lambda: invalidate_catalog(product))

    @transaction.atomic
    def perform_update(self, serializer):
        self.validate_store_publication(serializer)
        product = serializer.save()
        transaction.on_commit(lambda: invalidate_catalog(product))

    def perform_destroy(self, instance):
        raise ValidationError({'detail': 'Unpublish products with visibility=false to preserve carts and order history.'})

    @action(detail=True, methods=['patch'])
    def inventory(self, request, store_pk=None, pk=None):
        serializer = InventorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=pk, store=self.get_store())
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
        serializer.save(product=product)
        invalidate_catalog(product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
            specification = Specification.objects.filter(product=product).first()
            if request.method == 'GET':
                return Response(MerchantSpecificationSerializer(specification).data if specification else {})
            serializer = MerchantSpecificationSerializer(specification, data=request.data)
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
        return Schedule.objects.filter(store__user=self.request.user).order_by('make_visible_at', 'pk')

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        if product.store.user_id != self.request.user.pk:
            raise ValidationError({'product': 'Choose a product from your store.'})
        if serializer.validated_data['make_visible_at'] <= timezone.now():
            raise ValidationError({'make_visible_at': 'Choose a future time.'})
        serializer.save(store=product.store)
