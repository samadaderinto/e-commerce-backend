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
from store.models import Schedule, Store, StoreAddress, StoreInfo
from store.serializers import (
    DashboardQuerySerializer, InventorySerializer, MerchantImageSerializer,
    MerchantProductSerializer, MerchantSpecificationSerializer, ScheduleSerializer,
    StoreAddressSerializer, StoreInfoSerializer, StoreOnboardingSerializer, StoreSerializer,
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
        serializer.save(user=self.request.user)

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
            'created': order.created, 'ordered': order.ordered,
            'items': [{'product': item.product_id, 'title': item.product.title,
                       'quantity': item.quantity} for item in order.cart.merchant_items],
        } for order in page]
        return self.get_paginated_response(data)

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
        refund_window = getattr(settings, 'REFUND_WINDOW_DAYS', 7)
        cutoff = timezone.now() - timedelta(days=refund_window)
        fee_rate = getattr(settings, 'PLATFORM_FEE_PERCENT', Decimal('4.00')) / Decimal('100.0')

        in_review_orders = sales_orders.filter(created__gt=cutoff)
        in_review_items = CartItem.objects.filter(product__store=store, cart__in=in_review_orders.values('cart_id'))
        in_review_totals = in_review_items.aggregate(value=Sum(line_value))
        in_review_gross = in_review_totals['value'] or Decimal('0.00')
        in_review_net = (in_review_gross * (Decimal('1.00') - fee_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        cleared_orders = sales_orders.filter(created__lte=cutoff)
        cleared_items = CartItem.objects.filter(product__store=store, cart__in=cleared_orders.values('cart_id'))
        cleared_totals = cleared_items.aggregate(value=Sum(line_value))
        cleared_gross = cleared_totals['value'] or Decimal('0.00')
        cleared_net = (cleared_gross * (Decimal('1.00') - fee_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        gross_value = totals['value'] or Decimal('0.00')
        platform_fee = (gross_value * fee_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        net_value = (gross_value - platform_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

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
            'wallet': {
                'gross_sales': format(gross_value, '.2f'),
                'platform_fee_percent': format(getattr(settings, 'PLATFORM_FEE_PERCENT', Decimal('4.00')), '.2f'),
                'platform_fee_deducted': format(platform_fee, '.2f'),
                'net_sales': format(net_value, '.2f'),
                'in_review': format(in_review_net, '.2f'),
                'available_balance': format(cleared_net, '.2f'),
                'refund_window_days': refund_window,
            },
            'orders_by_day': [{'date': start + timedelta(days=i), 'count': trend.get(start + timedelta(days=i), 0)} for i in range(days)],
            'top_products': list(top_products),
            'low_stock_products': list(products.filter(available__lte=threshold).order_by('available', 'pk').values('id', 'title', 'available')[:20]),
        })


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
