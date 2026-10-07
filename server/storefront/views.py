from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models, transaction
from django.db.models import Count, Q, F, Case, When
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from notification.delivery import queue_email_delivery
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from core.access import IsCustomer, IsBusinessAdmin as IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
try:
    import stripe
except ImportError:  # Wallet payments remain unavailable until the optional SDK is installed.
    stripe = None
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from cart.models import Cart, CartItem
from affiliates.services import reward_referral
from core.models import Address, Refund, Review, User, Wishlist, UserWallet, UserWalletTransaction
from core.serializers import UserWalletSerializer, UserWalletTransactionSerializer
from core.services import get_or_create_user_wallet, credit_user_wallet, debit_user_wallet
from notification.views import create_notification
from payment.models import Coupon, CouponRedemption, DeliveryInfo, Order
from payment.couponing import calculate_coupon_discount
from payment.usps import calculate_usps_rates
from payment.carriers import calculate_carrier_rates, CARRIERS
from payment.shipping_quotes import issue_quote, verify_quote, cart_rates
from product.models import Product
from product.search import search_product_ids
from product.policies import is_own_store, validate_purchase
from store.views import invalidate_catalog
from store.models import Store, StoreAddress
from store.services import record_order_earnings_for_merchant
from .serializers import (
    PasswordChangeRequestSerializer, AddressSerializer, AuthRequestSerializer, CartMutationRequestSerializer,
    CartSerializer, CatalogPageSerializer, CouponAdminSerializer,
    CatalogQuerySerializer, CatalogSerializer, CheckoutRequestSerializer,
    OrderSerializer, ProductIdRequestSerializer, PublicStoreSerializer, RefundRequestSerializer, RegisterSerializer,
    ReviewSerializer, ShippingRateSerializer, UserSerializer, WalletCheckoutSerializer, unit_price,
)


def catalog():
    return Product.objects.filter(
        visibility=True,
        store__status=Store.STATUS_ACTIVE,
        store__verified_at__isnull=False,
    ).select_related('store').prefetch_related('images', 'tags').annotate(rating_count=Count('review', distinct=True))


def tokens(user):
    refresh = RefreshToken.for_user(user)
    refresh["credential_version"] = user.credential_version
    return {'access': str(refresh.access_token), 'refresh': str(refresh), 'user': UserSerializer(user).data}


class AuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'auth'

    @extend_schema(
        request=AuthRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            201: OpenApiTypes.OBJECT,
            204: OpenApiResponse(description='Logged out successfully.'),
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
        auth=[],
        description=(
            'Submit an action-specific payload. Supported actions: login, register, verify, '
            'forgot, reset, refresh, and logout. Successful login returns access and refresh '
            'JWTs plus the user; other actions return a detail message or refreshed token.'
        ),
    )
    def post(self, request, action):
        data = request.data
        if action == 'login':
            email = str(data.get('email', '')).strip().lower()
            password = data.get('password', '')
            if not isinstance(password, str) or len(password) > 128:
                raise ValidationError({'detail': 'Invalid email or password.'})
            user = authenticate(request, email=email, password=password)
            if user is None:
                return Response({'detail': 'Invalid email or password. Verify your email if you just registered.'}, status=401)
            return Response(tokens(user))
        if action == 'register':
            payload = {**data, 'email': str(data.get('email', '')).strip().lower()}
            serializer = RegisterSerializer(data=payload)
            try:
                serializer.is_valid(raise_exception=True)
            except DjangoValidationError as error:
                raise ValidationError({'password': error.messages})
            referral_code = serializer.validated_data.pop('referral_code', '').strip()
            user = User.objects.create_user(**serializer.validated_data, is_active=False)
            if referral_code:
                reward_referral(referral_code, user)
            token = signing.dumps({'user': user.pk}, salt='proace-verify')
            url = f'{settings.FRONTEND_URL}/verify-email?token={token}'
            queue_email_delivery(
                user.email,
                'Verify your ProAce account',
                f'Welcome to ProAce. Verify your email: {url}',
                recipient=user,
            )
            return Response({'detail': 'Check your email to activate your account.'}, status=201)
        if action == 'verify':
            if str(data.get('token', '')).startswith('staff:'):
                from core.onboarding import activate_staff
                activate_staff(str(data['token'])[6:])
                return Response({'detail': 'Email verified. Temporary credentials have been emailed to you.'})
            try:
                payload = signing.loads(data.get('token', ''), salt='proace-verify', max_age=86400)
                user = User.objects.get(pk=payload['user'])
            except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError):
                raise ValidationError({'detail': 'This verification link is invalid or expired.'})
            user.is_active = True
            user.save(update_fields=['is_active'])
            return Response({'detail': 'Email verified. You can now sign in.'})
        if action == 'forgot':
            email = serializers.EmailField().run_validation(data.get('email'))
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                url = f'{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}'
                queue_email_delivery(
                    user.email,
                    'Reset your ProAce password',
                    f'Reset your password: {url}',
                    recipient=user,
                )
            return Response({'detail': 'If an active account exists, a reset link has been sent.'})
        if action == 'reset':
            try:
                user = User.objects.get(pk=force_str(urlsafe_base64_decode(data.get('uid', ''))))
            except (ValueError, TypeError, UnicodeDecodeError, User.DoesNotExist):
                raise ValidationError({'detail': 'Invalid reset link.'})
            if not default_token_generator.check_token(user, data.get('token', '')):
                raise ValidationError({'detail': 'This reset link is invalid or expired.'})
            password = serializers.CharField(min_length=8, max_length=128).run_validation(data.get('password'))
            try:
                validate_password(password, user)
            except DjangoValidationError as error:
                raise ValidationError({'password': error.messages})
            user.set_password(password)
            user.must_change_password = False
            user.credential_version += 1
            user.save(update_fields=['password', 'must_change_password', 'credential_version'])
            from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
            return Response({'detail': 'Password updated. Sign in with your new password.'})
        if action == 'refresh':
            serializer = TokenRefreshSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.validated_data)
        if action == 'logout':
            try:
                RefreshToken(data.get('refresh', '')).blacklist()
            except Exception:
                pass
            return Response(status=204)
        return Response(status=404)


class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=UserSerializer, responses=UserSerializer)
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProductsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='storefront_products_list',
        parameters=[CatalogQuerySerializer],
        responses=CatalogPageSerializer,
        auth=[],
        description='Returns a page of active-store products. Each page contains at most 24 results.',
    )
    def get(self, request):
        params = request.query_params
        is_store_preview = False

        if params.get('store'):
            store = serializers.IntegerField(min_value=1).run_validation(params['store'])
            store_obj = Store.objects.filter(pk=store).first()
            if store_obj and (store_obj.status != Store.STATUS_ACTIVE or not store_obj.verified_at):
                user = request.user
                is_authorized = bool(user and user.is_authenticated and (user == store_obj.user or user.is_staff or user.is_superuser))
                if is_authorized:
                    is_store_preview = True
                    products = Product.objects.filter(
                        store=store_obj,
                        visibility=True,
                    ).select_related('store').prefetch_related('images', 'tags').annotate(rating_count=Count('review', distinct=True))
                else:
                    products = Product.objects.none()
            else:
                products = catalog().filter(store_id=store)
        else:
            store = None
            products = catalog()

        search = params.get('search')
        if params.get('category'):
            products = products.filter(category=params['category'])
        if params.get('deals') == 'true':
            products = products.filter(discount__gt=0)
        for field, lookup in [('min_price', 'price__gte'), ('max_price', 'price__lte')]:
            if params.get(field):
                value = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0).run_validation(params[field])
                products = products.filter(**{lookup: value})
            else:
                value = None
            if field == 'min_price':
                min_price = value
            else:
                max_price = value
        ordering = params.get('ordering', '-created')
        if ordering not in ['-created', 'price', '-price', '-average_rating', '-sales', '-discount']:
            ordering = '-created'
        page = serializers.IntegerField(min_value=1, default=1).run_validation(params.get('page', 1))
        page_size = 24
        offset = (page - 1) * page_size
        if search:
            if not is_store_preview:
                search_results = search_product_ids(
                    search,
                    filters={
                        'category': params.get('category') or None,
                        'store_id': store,
                        'deals': params.get('deals') == 'true',
                        'min_price': min_price,
                        'max_price': max_price,
                    },
                    ordering=ordering,
                    offset=offset,
                    limit=page_size,
                )
                if search_results is not None:
                    ids = search_results['ids']
                    count = search_results['count']
                    products_by_id = products.filter(pk__in=ids).in_bulk(ids)
                    products = [products_by_id[pk] for pk in ids if pk in products_by_id]
                    return Response({'count': count, 'page': page, 'pages': max(1, (count + page_size - 1) // page_size), 'results': CatalogSerializer(products, many=True, context={'request': request}).data})
            products = products.filter(Q(title__icontains=search) | Q(brand__icontains=search) | Q(description__icontains=search))
        count = products.count()
        products = products.order_by(ordering, '-pk')[offset:page * page_size]
        return Response({'count': count, 'page': page, 'pages': max(1, (count + page_size - 1) // page_size), 'results': CatalogSerializer(products, many=True, context={'request': request}).data})


class ProductDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id='storefront_product_retrieve', responses=CatalogSerializer, auth=[])
    def get(self, request, pk):
        product = catalog().filter(pk=pk).first()
        if not product:
            raw_product = Product.objects.filter(pk=pk).select_related('store').prefetch_related('images', 'tags').annotate(rating_count=Count('review', distinct=True)).first()
            if not raw_product:
                raise Http404('No Product matches the given query.')
            user = request.user
            is_authorized = bool(user and user.is_authenticated and (user == raw_product.store.user or user.is_staff or user.is_superuser))
            if not is_authorized:
                raise Http404('No Product matches the given query.')
            product = raw_product
        return Response(CatalogSerializer(product, context={'request': request}).data)


class PublicStoreView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id='storefront_public_store_retrieve', responses=PublicStoreSerializer, auth=[])
    def get(self, request, pk):
        store = get_object_or_404(Store, pk=pk)
        is_verified = bool(store.status == Store.STATUS_ACTIVE and store.verified_at)
        user = request.user
        is_authorized = bool(user and user.is_authenticated and (user == store.user or user.is_staff or user.is_superuser))
        if not is_verified and not is_authorized:
            raise Http404('No Store matches the given query.')
        return Response(PublicStoreSerializer(store, context={'request': request, 'is_preview': not is_verified}).data)


def check_is_verified_buyer(user, product) -> bool:
    if not user or not user.is_authenticated:
        return False
    from payment.models import Order
    from cart.models import CartItem

    orders = Order.objects.filter(
        user=user,
        ordered=True,
    ).exclude(status__in=['cancelled', 'refunded'])

    prod_id = product.pk if hasattr(product, 'pk') else int(product)
    for order in orders:
        if order.items_snapshot:
            for item in order.items_snapshot:
                if item.get('product') == prod_id or str(item.get('product')) == str(prod_id):
                    return True
        if order.cart_id and CartItem.objects.filter(cart_id=order.cart_id, product_id=prod_id).exists():
            return True
    return False


class ReviewsView(APIView):
    permission_classes = [IsCustomer]
    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else super().get_permissions()

    @extend_schema(responses=ReviewSerializer(many=True), auth=[])
    def get(self, request, pk):
        product = get_object_or_404(catalog(), pk=pk)
        reviews = Review.objects.filter(product=product).select_related('user').order_by('-created')[:50]
        return Response(ReviewSerializer(reviews, many=True, context={'request': request}).data)

    @extend_schema(request=ReviewSerializer, responses={201: ReviewSerializer, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        product = get_object_or_404(catalog(), pk=pk)
        
        # Verify user is a verified buyer or staff
        if not check_is_verified_buyer(request.user, product) and not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {'detail': 'Only verified buyers who have purchased this product can leave a review.'},
                status=403,
            )

        instance = Review.objects.filter(user=request.user, product=product).first()
        serializer = ReviewSerializer(instance, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        review = serializer.save(user=request.user, product=product)
        review.set_avg_rating()
        invalidate_catalog(product)
        return Response(serializer.data, status=200 if instance else 201)

    @extend_schema(responses={204: None, 403: OpenApiTypes.OBJECT})
    def delete(self, request, pk):
        product = get_object_or_404(catalog(), pk=pk)
        review_id = request.query_params.get('review_id')
        if review_id:
            review = get_object_or_404(Review, product=product, pk=review_id)
            is_moderator = (
                request.user.is_staff
                or request.user.is_superuser
                or getattr(request.user, 'is_business_admin', False)
                or (product.store and product.store.user_id == request.user.id)
                or review.user_id == request.user.id
            )
            if not is_moderator:
                return Response({'detail': 'You do not have permission to moderate this review.'}, status=403)
        else:
            review = get_object_or_404(Review, product=product, user=request.user)
        review.delete()
        review.set_avg_rating()
        invalidate_catalog(product)
        return Response(status=204)


class WishlistView(APIView):
    permission_classes = [IsCustomer]
    @extend_schema(responses=CatalogSerializer(many=True))
    def get(self, request):
        products = catalog().filter(wishlist__user=request.user, wishlist__liked=True)
        return Response(CatalogSerializer(products, many=True, context={'request': request}).data)

    @extend_schema(request=ProductIdRequestSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        product_id = serializers.IntegerField(min_value=1).run_validation(request.data.get('product'))
        product = get_object_or_404(catalog(), pk=product_id)
        Wishlist.objects.update_or_create(user=request.user, product=product, defaults={'liked': True})
        return Response({'saved': True})

    @extend_schema(
        parameters=[OpenApiParameter('product', OpenApiTypes.INT, OpenApiParameter.QUERY, required=True)],
        responses={204: OpenApiResponse(description='Item removed.')},
    )
    def delete(self, request):
        product_id = serializers.IntegerField(min_value=1).run_validation(
            request.query_params.get('product', request.data.get('product'))
        )
        Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
        return Response(status=204)


class AddressesView(APIView):
    permission_classes = [IsCustomer]
    @extend_schema(responses=AddressSerializer(many=True))
    def get(self, request, pk=None):
        if pk:
            address = get_object_or_404(Address, pk=pk, user=request.user, is_deleted=False)
            return Response(AddressSerializer(address).data)
        return Response(AddressSerializer(Address.objects.filter(user=request.user, is_deleted=False).order_by('-is_default', '-pk'), many=True).data)

    @transaction.atomic
    @extend_schema(request=AddressSerializer, responses={201: AddressSerializer})
    def post(self, request):
        User.objects.select_for_update().get(pk=request.user.pk)
        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('is_default', True):
            Address.objects.filter(user=request.user, is_deleted=False).update(is_default=False)
        serializer.save(user=request.user)
        return Response(serializer.data, status=201)

    @transaction.atomic
    @extend_schema(request=AddressSerializer, responses={200: AddressSerializer})
    def patch(self, request, pk=None):
        User.objects.select_for_update().get(pk=request.user.pk)
        address_id = pk or request.query_params.get('id') or request.data.get('id')
        validated_id = serializers.IntegerField(min_value=1).run_validation(address_id)
        address = get_object_or_404(Address, pk=validated_id, user=request.user, is_deleted=False)
        serializer = AddressSerializer(address, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('is_default'):
            Address.objects.filter(user=request.user, is_deleted=False).exclude(pk=address.pk).update(is_default=False)
        serializer.save()
        return Response(serializer.data, status=200)

    @transaction.atomic
    @extend_schema(request=AddressSerializer, responses={200: AddressSerializer})
    def put(self, request, pk=None):
        return self.patch(request, pk)

    @extend_schema(
        parameters=[OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False)],
        responses={204: OpenApiResponse(description='Address deleted.')},
    )
    def delete(self, request, pk=None):
        address_id = pk or request.query_params.get('id') or request.data.get('id')
        validated_id = serializers.IntegerField(min_value=1).run_validation(address_id)
        address = get_object_or_404(Address, pk=validated_id, user=request.user, is_deleted=False)
        if DeliveryInfo.objects.filter(address=address).exists():
            address.is_deleted = True
            address.is_default = False
            address.save(update_fields=['is_deleted', 'is_default'])
        else:
            address.delete()
        return Response(status=204)


def active_cart(user):
    cart = Cart.objects.filter(user=user, ordered=False).order_by('pk').first()
    return cart if cart else Cart.objects.create(user=user)


def calculate_shipping(subtotal, has_physical_items, origin_zip='33602', dest_zip='33602', total_weight=Decimal('1.00'), service_id=None):
    if not has_physical_items:
        return Decimal('0.00')
    rates = calculate_usps_rates(origin_zip, dest_zip, total_weight, subtotal, has_physical_items)
    if not rates:
        return Decimal('0.00')
    if service_id:
        for r in rates:
            if r['service_id'] == service_id:
                return Decimal(r['amount'])
    if service_id:
        raise ValidationError({'shipping_service': 'Unknown shipping service.'})
    return Decimal(rates[0]['amount'])


def cart_data(cart, request):
    items = cart.cart_items.select_related('product__store').prefetch_related('product__images', 'product__tags')
    rows = [{'product': CatalogSerializer(item.product, context={'request': request}).data,
             'quantity': item.quantity, 'total': str(unit_price(item.product) * item.quantity),
             'purchasable': not is_own_store(item.product, request.user)
             and item.product.visibility and item.product.store.status == Store.STATUS_ACTIVE
             and item.product.store.verified_at is not None
             and (item.product.is_digital or item.quantity <= item.product.available)} for item in items]
    subtotal = sum((Decimal(row['total']) for row in rows), Decimal('0'))
    has_physical_items = any(not row['product']['is_digital'] for row in rows)
    total_weight = sum(
        Decimal(str(row['product'].get('weight') or '1.00')) * row['quantity']
        for row in rows if not row['product']['is_digital']
    )
    shipping = calculate_shipping(subtotal, has_physical_items and bool(rows), total_weight=total_weight)
    return {'id': cart.pk, 'items': rows, 'subtotal': str(subtotal), 'shipping': str(shipping), 'total': str(subtotal + shipping)}


class CartView(APIView):
    permission_classes = [IsCustomer]
    @extend_schema(responses=CartSerializer)
    @transaction.atomic
    def get(self, request):
        User.objects.select_for_update().get(pk=request.user.pk)
        return Response(cart_data(active_cart(request.user), request))

    @extend_schema(
        request=CartMutationRequestSerializer,
        responses={200: CartSerializer, 400: OpenApiTypes.OBJECT},
    )
    @transaction.atomic
    def mutate(self, request):
        User.objects.select_for_update().get(pk=request.user.pk)
        cart = active_cart(request.user)
        product_id = request.query_params.get('product', request.data.get('product')) \
            if request.method == 'DELETE' else request.data.get('product')
        pk = serializers.IntegerField(min_value=1).run_validation(product_id)
        if request.method == 'DELETE':
            cart.cart_items.filter(product_id=pk).delete()
        else:
            quantity = serializers.IntegerField(min_value=1, max_value=1000).run_validation(request.data.get('quantity', 1))
            product = get_object_or_404(catalog(), pk=pk)
            validate_purchase(product, request.user)
            item = cart.cart_items.filter(product=product).first()
            if request.method == 'POST' and item:
                quantity += item.quantity
            if not product.is_digital and quantity > product.available:
                raise ValidationError({'detail': f'Only {product.available} units of {product.title} are available.'})
            if item:
                item.quantity = quantity
                item.save(update_fields=['quantity', 'updated'])
            else:
                CartItem.objects.create(cart=cart, product=product, quantity=quantity)
        from cart.cache import invalidate_cart_cache
        transaction.on_commit(lambda: invalidate_cart_cache(cart))
        return Response(cart_data(cart, request))

    post = mutate
    patch = mutate

    @extend_schema(
        parameters=[OpenApiParameter('product', OpenApiTypes.INT, OpenApiParameter.QUERY, required=True)],
        responses={200: CartSerializer, 400: OpenApiTypes.OBJECT},
    )
    def delete(self, request):
        return self.mutate(request)


def order_data(order):
    items = []
    for source in order.items_snapshot:
        item = dict(source)
        if item.get('is_digital') and item.get('product'):
            item['download_url'] = f"/api/orders/{order.pk}/downloads/{item['product']}"
        items.append(item)
    return {
        'id': order.pk,
        'reference': order.orderId,
        'status': order.status,
        'created': order.created,
        'total': str(order.total),
        'subtotal': str(order.subtotal),
        'payment_type': order.payment_type,
        'carrier': getattr(order, 'carrier', 'USPS') or 'USPS',
        'tracking_number': getattr(order, 'tracking_number', '') or '',
        'tracking_url': getattr(order, 'tracking_url', '') or '',
        'shipped_at': getattr(order, 'shipped_at', None),
        'delivered_at': getattr(order, 'delivered_at', None),
        'tracking_events': getattr(order, 'tracking_events', []) or [],
        'shipping': order.shipping_snapshot,
        'tax': str(order.tax),
        'items': items,
        'address': order.address_snapshot,
        'buyer_email': getattr(order, 'buyer_email', '') or (order.user.email if order.user else ''),
        'buyer_phone': getattr(order, 'buyer_phone', '') or (str(getattr(order.user, 'phone1', '')) if order.user else ''),
    }


class OrdersView(APIView):
    permission_classes = [IsCustomer]
    @extend_schema(responses=OrderSerializer(many=True))
    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-created')
        return Response([order_data(order) for order in orders[:100]])


class OrderDetailView(APIView):
    @extend_schema(responses=OrderSerializer)
    def get(self, request, pk):
        if request.user.is_staff or request.user.is_superuser:
            orders = Order.objects.all().order_by('-created')
        else:
            orders = Order.objects.filter(user=request.user).order_by('-created')
        return Response(order_data(get_object_or_404(orders, pk=pk)))


class DigitalDownloadView(APIView):
    """Issue a short-lived object-storage URL only to the buyer or backoffice."""
    def get(self, request, pk, product_pk):
        orders = Order.objects.all() if (request.user.is_staff or request.user.is_superuser or request.user.is_business_admin) else Order.objects.filter(user=request.user)
        order = get_object_or_404(orders, pk=pk, ordered=True)
        item = next((row for row in order.items_snapshot if row.get('product') == product_pk and row.get('is_digital')), None)
        if not item:
            raise Http404
        product = get_object_or_404(Product, pk=product_pk, is_digital=True)
        from django.core.files.storage import default_storage
        from urllib.parse import urlparse
        raw_url = (product.digital_file_url or item.get('download_url') or '').strip()
        path = urlparse(raw_url).path.lstrip('/')
        bucket = getattr(settings, 'MINIO_BUCKET_NAME', 'commerce-images')
        for prefix in (f'{bucket}/media/', f'{bucket}/', 'media/'):
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        if not path or not default_storage.exists(path):
            return Response({'detail': 'The digital asset is unavailable. Contact support for a replacement.'}, status=404)
        response = HttpResponseRedirect(default_storage.url(path))
        response['Cache-Control'] = 'private, no-store'
        return response


class OrderTrackingView(APIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT}, description="Get recorded fulfillment milestones and official carrier tracking links.")
    def get(self, request, pk):
        if request.user.is_staff or request.user.is_superuser:
            orders = Order.objects.all()
        else:
            orders = Order.objects.filter(user=request.user)
        order = get_object_or_404(orders, pk=pk)
        from payment.usps import track_usps_shipment
        tracking_info = track_usps_shipment(order.tracking_number) if order.carrier.upper() == 'USPS' else {'events': [], 'status': 'unknown', 'tracking_url': order.tracking_url, 'summary': 'View the carrier website for current scans.'}
        return Response({
            'order_id': order.pk,
            'reference': order.orderId,
            'status': order.status,
            'carrier': order.carrier or 'USPS',
            'tracking_number': order.tracking_number or '',
            'tracking_url': order.tracking_url or '',
            'shipped_at': order.shipped_at,
            'delivered_at': order.delivered_at,
            'tracking_events': order.tracking_events or [],
            'live_tracking': tracking_info,
        })



class UserWalletView(APIView):
    permission_classes = [IsCustomer]
    @extend_schema(responses={200: OpenApiTypes.OBJECT}, description="Get current user's wallet balance and transactions.")
    def get(self, request):
        wallet = get_or_create_user_wallet(request.user)
        return Response({
            "balance": format(wallet.balance, ".2f"),
            "transactions": UserWalletTransactionSerializer(wallet.transactions.all()[:30], many=True).data,
        })


class WalletTopupSessionView(APIView):
    permission_classes = [IsCustomer]
    MAX_TOPUP = Decimal('25000.00')
    DAILY_TOPUP = Decimal('50000.00')
    MONTHLY_TOPUP = Decimal('100000.00')

    def post(self, request):
        if stripe is None or not getattr(settings, 'STRIPE_SECRET', ''):
            raise ValidationError({'detail': 'Wallet funding is not configured.'})
        try:
            amount = Decimal(str(request.data.get('amount', '0'))).quantize(Decimal('.01'))
        except Exception:
            raise ValidationError({'amount': 'Enter a valid amount.'})
        if amount < Decimal('5.00') or amount > self.MAX_TOPUP:
            raise ValidationError({'amount': 'Choose an amount between $5.00 and $25,000.00.'})
        from django.utils.timezone import now
        from django.db.models import Sum
        deposits = UserWalletTransaction.objects.filter(wallet__user=request.user, source=UserWalletTransaction.SOURCE_DEPOSIT, transaction_type=UserWalletTransaction.CREDIT)
        today_total = deposits.filter(created__date=now().date()).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        month_total = deposits.filter(created__year=now().year, created__month=now().month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        if today_total + amount > self.DAILY_TOPUP or month_total + amount > self.MONTHLY_TOPUP:
            raise ValidationError({'amount': 'This deposit exceeds your current daily or monthly wallet limit.'})
        stripe.api_key = settings.STRIPE_SECRET
        session = stripe.checkout.Session.create(
            mode='payment', payment_method_types=['card'],
            line_items=[{'price_data': {'currency': getattr(settings, 'STRIPE_CURRENCY', 'usd'), 'product_data': {'name': 'ProAce Wallet funds'}, 'unit_amount': int(amount * 100)}, 'quantity': 1}],
            client_reference_id=str(request.user.pk), metadata={'wallet_topup': 'true', 'amount': str(amount)},
            success_url=f"{settings.FRONTEND_URL}/account/wallet?topup_session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/account/wallet?topup_cancelled=1",
        )
        return Response({'url': session.url, 'id': session.id})


class WalletTopupConfirmView(APIView):
    permission_classes = [IsCustomer]

    @transaction.atomic
    def post(self, request):
        session_id = str(request.data.get('session_id', '')).strip()
        if stripe is None or not session_id or not getattr(settings, 'STRIPE_SECRET', ''):
            raise ValidationError({'detail': 'Invalid wallet top-up session.'})
        stripe.api_key = settings.STRIPE_SECRET
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception:
            raise ValidationError({'detail': 'Unable to verify wallet top-up.'})
        if session.get('payment_status') != 'paid' or session.get('client_reference_id') != str(request.user.pk) or session.get('metadata', {}).get('wallet_topup') != 'true':
            raise ValidationError({'detail': 'Wallet payment has not been completed.'})
        reference = f"stripe_topup:{session_id}"
        if UserWalletTransaction.objects.filter(reference=reference).exists():
            return Response({'detail': 'Wallet already funded.', 'balance': str(get_or_create_user_wallet(request.user).balance)})
        amount = Decimal(str(session.get('amount_total', 0))) / Decimal('100')
        if amount < Decimal('5.00') or amount > WalletTopupSessionView.MAX_TOPUP:
            raise ValidationError({'detail': 'Wallet top-up amount is outside the allowed range.'})
        credit_user_wallet(request.user, amount, 'Stripe wallet top-up', source=UserWalletTransaction.SOURCE_DEPOSIT, reference=reference)
        wallet = get_or_create_user_wallet(request.user)
        from utils.functions import send_mail
        send_mail('wallet-funded', request.user.email, {'amount': format(amount, '.2f'), 'balance': format(wallet.balance, '.2f')})
        from notification.views import create_notification
        create_notification(recipient=request.user, verb=f'Wallet funded: ${amount:.2f}', description='Your ProAce Wallet has been credited and is ready to use.', data={'category': 'wallet', 'event': 'wallet_topup', 'amount': str(amount)})
        if amount >= Decimal('10000.00'):
            create_notification(recipient=request.user, verb='Large wallet deposit recorded', description='This deposit may receive an additional fraud and compliance review.', data={'category': 'wallet', 'event': 'wallet_topup_review', 'amount': str(amount)}, level='warning')
        return Response({'detail': 'Wallet funded successfully.', 'balance': format(wallet.balance, '.2f')})


class OrderRefundView(APIView):
    permission_classes = [IsCustomer]
    @extend_schema(
        request=RefundRequestSerializer,
        responses={201: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        description="Request a refund for an order within the 7-day return window."
    )
    @transaction.atomic
    def post(self, request, pk):
        orders = Order.objects.filter(user=request.user)
        order = get_object_or_404(orders, pk=pk)

        if order.status in ('refunded', 'cancelled'):
            raise ValidationError({'detail': 'This order can no longer be refunded.'})

        snapshots = order.items_snapshot or []
        is_all_digital = bool(snapshots) and all(item.get('is_digital', False) for item in snapshots)
        if is_all_digital:
            raise ValidationError({
                'detail': 'Digital products (e-books, software downloads) are non-refundable once delivered. '
                          'If you are experiencing a technical issue with your file, please contact customer support at support@proace.com.'
            })

        refund_window = getattr(settings, 'REFUND_WINDOW_DAYS', 7)
        from datetime import timedelta
        deadline = order.created + timedelta(days=refund_window)
        if timezone.now() > deadline:
            raise ValidationError({
                'detail': f'The {refund_window}-day return window for this order has expired.'
            })

        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason_code = serializer.validated_data['reason']
        reason_labels = {'item_damaged': 'Item damaged', 'wrong_item_received': 'Wrong item received', 'item_missing': 'Item missing', 'other': serializer.validated_data.get('other_reason', '').strip()}
        reason = reason_labels[reason_code]
        refund_type = serializer.validated_data.get('refund_type', 'store_credit')
        selected_ids = set(serializer.validated_data['product_ids'])
        selected = [item for item in snapshots if item.get('product') in selected_ids]
        if len({item.get('product') for item in selected}) != len(selected_ids):
            raise ValidationError({'product_ids': 'Choose products from this order only.'})
        if any(item.get('is_digital', False) for item in selected):
            raise ValidationError({'product_ids': 'Digital products are non-refundable. If you are experiencing issues, please contact support via email.'})
        claimed = set()
        for previous in Refund.objects.filter(order=order, status__in=[Refund.STATUS_PENDING, Refund.STATUS_APPROVED]):
            claimed.update(item.get('product') for item in previous.selected_items)
        if selected_ids & claimed:
            raise ValidationError({'product_ids': 'A refund already exists for one or more selected products.'})
        refund_amount = sum((Decimal(str(item.get('unit_price', '0'))) * int(item.get('quantity', 1)) for item in selected), Decimal('0')).quantize(Decimal('.01'))

        refund = Refund.objects.create(
            email=request.user.email,
            order=order,
            reason=reason,
            refund_type=refund_type,
            selected_items=selected,
            refund_amount=refund_amount,
            accepted=False,
        )

        stores = {item.get('store') for item in snapshots if item.get('store')}
        for store_id in stores:
            store = Store.objects.filter(pk=store_id).first()
            if store and store.user:
                create_notification(
                    recipient=store.user,
                    verb=f'Refund Requested for Order #{order.orderId}',
                    description=f'Customer requested a refund ({refund.get_refund_type_display()}) for Order #{order.orderId}. Reason: {reason}',
                    data={'order_id': order.pk, 'refund_id': refund.pk, 'store_id': store.pk, 'event': 'refund_requested'}
                )

        return Response({
            'detail': 'Your refund request has been received. Physical returns are reviewed and processed within 1–2 business days.',
            'status': order.status,
            'refund_id': refund.pk,
            'refund_type': refund_type,
            'refund_amount': format(refund_amount, '.2f'),
        }, status=201)


class OrderCancelView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        description="Cancel a pending or confirmed order before fulfillment, restoring stock and refunding store credit."
    )
    @transaction.atomic
    def post(self, request, pk):
        orders = Order.objects.filter(user=request.user)
        order = get_object_or_404(orders, pk=pk)

        if order.status in ('refunded', 'cancelled'):
            raise ValidationError({'detail': 'This order has already been cancelled or refunded.'})

        if order.status in ('shipped', 'delivered'):
            raise ValidationError({
                'detail': 'This order has already shipped and cannot be cancelled. You can request a return after delivery.'
            })

        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated'])

        # Restock inventory
        for item in order.items_snapshot or []:
            prod_id = item.get('product')
            qty = int(item.get('quantity', 1))
            if prod_id and not item.get('is_digital'):
                Product.objects.filter(pk=prod_id).update(
                    available=models.F('available') + qty,
                    sales=models.Case(
                        models.When(sales__gte=qty, then=models.F('sales') - qty),
                        default=0,
                    ),
                )
                prod = Product.objects.filter(pk=prod_id).first()
                if prod:
                    transaction.on_commit(lambda p=prod: invalidate_catalog(p))

        # Refund order total to user's wallet
        if order.ordered:
            credit_user_wallet(
                request.user,
                order.total,
                f"Refund for cancelled Order #{order.orderId}",
                source=UserWalletTransaction.SOURCE_REFUND,
                reference=f"cancel:{order.orderId}",
            )

        create_notification(
            recipient=request.user,
            verb=f'Order #{order.orderId} cancelled',
            description=f'Order #{order.orderId} was cancelled. ${order.total} was credited to your ProAce Wallet.',
            data={'category': 'orders', 'order_id': order.pk, 'reference': order.orderId},
        )

        return Response({
            'detail': f'Order #{order.orderId} has been successfully cancelled.',
            'order': order_data(order),
        })


class CouponValidateView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT})
    def post(self, request):
        code = str(request.data.get('code', '')).strip()
        if not code:
            raise ValidationError({'code': 'Enter a coupon code.'})

        coupon = Coupon.objects.filter(
            code__iexact=code,
            active=True,
            valid_from__lte=timezone.now(),
            valid_to__gte=timezone.now(),
        ).first()

        if not coupon:
            raise ValidationError({'code': 'This coupon code is invalid or has expired.'})

        if coupon.num_available and coupon.num_used >= coupon.num_available:
            raise ValidationError({'code': 'This coupon has reached its maximum usage limit.'})

        cart = active_cart(request.user)
        items = list(cart.cart_items.select_related('product').all())
        if not items:
            raise ValidationError({'code': 'Add items to your bag before applying a coupon.'})

        coupon_lines = []
        subtotal = Decimal('0')
        for item in items:
            price = unit_price(item.product)
            subtotal += price * item.quantity
            coupon_lines.append({'product': item.product, 'quantity': item.quantity, 'unit_price': price})

        try:
            discount = calculate_coupon_discount(coupon, request.user, coupon_lines, subtotal, reserve=False)
        except Exception as exc:
            raise ValidationError({'code': str(exc)})

        return Response({
            'code': coupon.code,
            'discount': coupon.discount,
            'discount_amount': format(discount, '.2f'),
            'valid': True,
            'message': f'Coupon {coupon.code.upper()} applied! Saved ${discount:.2f}',
        })


class ShippingRatesView(APIView):
    permission_classes = [IsCustomer]
    @extend_schema(
        parameters=[
            OpenApiParameter('address', OpenApiTypes.INT, OpenApiParameter.QUERY, required=True, description='Owned delivery address ID'),
            OpenApiParameter('carrier', OpenApiTypes.STR, OpenApiParameter.QUERY, enum=['USPS', 'UPS', 'FEDEX', 'DHL']),
        ],
        responses={200: ShippingRateSerializer(many=True)},
    )
    def get(self, request):
        cart = active_cart(request.user)
        items = list(cart.cart_items.select_related('product__store').all())
        if not items:
            return Response([])

        has_physical_items = any(not item.product.is_digital for item in items)
        subtotal = sum((unit_price(item.product) * item.quantity for item in items), Decimal('0'))

        if not has_physical_items:
            tax = str((subtotal * Decimal(str(getattr(settings, 'CHECKOUT_TAX_RATE', '0')))).quantize(Decimal('.01')))
            digital_rate = {
                'carrier': 'DIGITAL',
                'service_id': 'digital_delivery',
                'service_name': 'Instant Digital Delivery',
                'name': 'Instant Digital Delivery',
                'rate': '0.00',
                'amount': '0.00',
                'delivery_days': 0,
                'estimated_delivery': 'Immediate access upon confirmation',
                'description': 'Worldwide digital delivery',
                'tax': tax,
                'is_default': True,
            }
            digital_rate['quote_token'] = issue_quote(digital_rate, request.user, cart, None)
            return Response([digital_rate])

        total_weight = sum(
            Decimal(str(item.product.weight or '1.00')) * item.quantity
            for item in items if not item.product.is_digital
        )

        origin_zip = '33602'
        store_addr = StoreAddress.objects.filter(store=items[0].product.store).first()
        if store_addr and store_addr.zip:
            origin_zip = store_addr.zip

        dest_zip = '33602'
        address_id = request.query_params.get('address')
        if address_id:
            try:
                addr = Address.objects.get(pk=serializers.IntegerField(min_value=1).run_validation(address_id), user=request.user, is_deleted=False)
                if has_physical_items:
                    country = ''.join(c for c in addr.country.lower() if c.isalnum())
                    us_names = {'us', 'usa', 'unitedstates', 'unitedstatesofamerica'}
                    if country not in us_names:
                        raise ValidationError({
                            'address': 'Physical products are currently delivered only within the United States. '
                                       'Digital products remain available worldwide.'
                        })
                dest_zip = addr.zip or '33602'
            except Address.DoesNotExist:
                raise ValidationError({'address': 'Address not found.'})

        carrier = str(request.query_params.get('carrier', 'USPS')).upper()
        if carrier not in CARRIERS:
            raise ValidationError({'carrier': 'Choose USPS, UPS, FEDEX, or DHL.'})
        if not address_id:
            raise ValidationError({'address': 'Select a delivery address to issue shipping quotes.'})
        rates = cart_rates(carrier, cart, addr)
        for rate in rates:
            rate['tax'] = str((subtotal * Decimal(str(getattr(settings, 'CHECKOUT_TAX_RATE', '0')))).quantize(Decimal('.01')))
            rate['quote_token'] = issue_quote(rate, request.user, cart, addr)
        return Response(rates)


class CheckoutView(APIView):
    permission_classes = [IsCustomer]
    @staticmethod
    def _validate_service_area(address, snapshots):
        if not any(not row['is_digital'] for row in snapshots):
            return
        if not address:
            raise ValidationError({
                'address': 'A delivery address is required for physical items.'
            })
        country = ''.join(character for character in address.country.lower() if character.isalnum())
        us_names = {'us', 'usa', 'unitedstates', 'unitedstatesofamerica'}
        if country not in us_names:
            raise ValidationError({
                'address': 'Physical products are currently delivered only within the United States. '
                           'Digital products remain available worldwide.',
            })

    def _lines(self, request, lock=False):
        cart = active_cart(request.user)
        items = list(cart.cart_items.order_by('product_id'))
        if not items:
            raise ValidationError({'detail': 'Your cart is empty.'})
        snapshots, coupon_lines = [], []
        for item in items:
            query = Product.objects.select_for_update() if lock else Product.objects
            product = query.get(pk=item.product_id)
            validate_purchase(product, request.user)
            if (not product.visibility or product.store.status != Store.STATUS_ACTIVE
                    or product.store.verified_at is None
                    or (not product.is_digital and product.available < item.quantity)):
                raise ValidationError({'detail': f'{product.title} is unavailable in the requested quantity.'})
            price = unit_price(product)
            snapshots.append({'product': product.pk, 'store': product.store_id, 'title': product.title,
                              'image': product.image_url, 'quantity': item.quantity, 'unit_price': str(price),
                              'is_digital': product.is_digital,
                              'digital_preview_watermark': bool(getattr(product, 'digital_preview_watermark', False)),
                              'download_url': product.digital_file_url if product.is_digital else ''})
            coupon_lines.append({'product': product, 'quantity': item.quantity, 'unit_price': price})
        subtotal = sum((Decimal(row['unit_price']) * row['quantity'] for row in snapshots), Decimal('0'))
        if subtotal > Decimal('99999999.99'):
            raise ValidationError({'detail': 'Order value exceeds the supported maximum.'})
        return cart, snapshots, coupon_lines, subtotal

    def _complete(self, request, key, address, code, payment_type, stripe_session_id=None, shipping_service=None, shipping_quote=None, paid_amount=None):
        User.objects.select_for_update().get(pk=request.user.pk)
        existing = Order.objects.filter(checkout_key=key).first()
        if existing:
            if existing.user_id != request.user.pk:
                raise ValidationError({'detail': 'Invalid checkout reference.'})
            return existing
        cart, snapshots, coupon_lines, subtotal = self._lines(request, lock=True)
        self._validate_service_area(address, snapshots)
        coupon = None
        discount = Decimal('0')
        if code:
            coupon = Coupon.objects.select_for_update().filter(
                code__iexact=code, active=True, valid_from__lte=timezone.now(), valid_to__gte=timezone.now()
            ).first()
            discount = calculate_coupon_discount(coupon, request.user, coupon_lines, subtotal)
            coupon.used()
        for item in cart.cart_items.order_by('product_id'):
            product = Product.objects.select_for_update().get(pk=item.product_id)
            if not product.is_digital:
                product.available -= item.quantity
            product.sales += item.quantity
            product.save(update_fields=['available', 'sales', 'updated'])
            transaction.on_commit(lambda product=product: invalidate_catalog(product))
        has_physical_items = any(not row['is_digital'] for row in snapshots)
        total_weight = sum(
            Decimal(str(item.product.weight or '1.00')) * item.quantity
            for item in cart.cart_items.select_related('product').all() if not item.product.is_digital
        )
        origin_zip = '33602'
        first_item = cart.cart_items.select_related('product__store').first()
        if first_item:
            store_addr = StoreAddress.objects.filter(store=first_item.product.store).first()
            if store_addr and store_addr.zip:
                origin_zip = store_addr.zip
        dest_zip = address.zip if address else '33602'
        if shipping_quote:
            rate = verify_quote(shipping_quote, request.user, cart, address, shipping_service, paid=paid_amount is not None)
        else:
            if not has_physical_items:
                rate = {'carrier': 'DIGITAL', 'service_id': 'digital_delivery', 'amount': '0.00'}
            else:
                # Backwards compatible direct API clients still receive a server-validated carrier rate.
                carrier = (shipping_service or 'usps_ground_advantage').split('_', 1)[0].upper()
                rates = cart_rates(carrier, cart, address)
                rate = next((row for row in rates if row['service_id'] == shipping_service), None)
                if rate is None:
                    raise ValidationError({'shipping_service': 'Select an available shipping service.'})
        if not has_physical_items:
            shipping_service = 'digital_delivery'
        shipping = Decimal(rate['amount'])
        tax = ((subtotal - discount) * Decimal(str(getattr(settings, 'CHECKOUT_TAX_RATE', '0')))).quantize(Decimal('.01'))
        if paid_amount is not None and int((subtotal - discount + shipping + tax) * 100) != paid_amount:
            raise ValidationError({'detail': 'Paid amount does not match this cart. Contact support.'})
        delivery_method = 'home delivery' if has_physical_items else 'digital'
        delivery_service = shipping_service or ('usps_ground_advantage' if has_physical_items else 'digital_delivery')
        delivery = DeliveryInfo.objects.create(
            user=request.user, address=address, method=delivery_method,
            delivery_type=delivery_service, total=shipping
        )
        buyer_email = getattr(request.user, 'email', '') or ''
        buyer_phone = str(getattr(request.user, 'phone1', '') or '')
        order = Order.objects.create(
            user=request.user, cart=cart, delivery=delivery, status='confirmed', ordered=True,
            coupon_code=code, total=subtotal - discount + shipping + tax, subtotal=subtotal, tax=tax,
            carrier=rate.get('carrier', 'DIGITAL'), shipping_snapshot=rate,
            buyer_email=buyer_email, buyer_phone=buyer_phone,
            payment_type=payment_type, checkout_key=key, stripe_session_id=stripe_session_id,
            items_snapshot=snapshots, address_snapshot=AddressSerializer(address).data if address else {'country': 'Worldwide', 'digital': True},
        )
        if payment_type == 'user_wallet':
            debit_user_wallet(
                request.user,
                order.total,
                f'ProAce Wallet payment for Order #{order.orderId}',
                source=UserWalletTransaction.SOURCE_PURCHASE,
                reference=order.orderId,
            )
        if coupon:
            CouponRedemption.objects.filter(coupon=coupon, user=request.user).update(order=order)
        cart.ordered = True
        cart.save(update_fields=['ordered', 'updated'])

        # Record granular store ledger entries and update unified merchant wallet
        record_order_earnings_for_merchant(order)

        store_ids = {item.get('store') for item in snapshots if item.get('store')}
        for store_id in store_ids:
            store = Store.objects.filter(pk=store_id).first()
            if store and store.user:
                create_notification(
                    recipient=store.user,
                    verb=f'New order #{order.orderId}',
                    description=f'New order #{order.orderId} placed with items from your store. Net earnings held in 7-day review escrow.',
                    data={'order_id': order.pk, 'store_id': store.pk, 'event': 'new_order'}
                )

        return order

    @extend_schema(request=CheckoutRequestSerializer, responses={201: OrderSerializer, 200: OrderSerializer})
    @transaction.atomic
    def post(self, request):
        key = serializers.UUIDField().run_validation(request.data.get('checkout_key'))
        existing = Order.objects.filter(checkout_key=key).first()
        if existing:
            if existing.user_id != request.user.pk:
                raise ValidationError({'detail': 'Invalid checkout reference.'})
            return Response(order_data(existing), status=200)
        cart = active_cart(request.user)
        has_physical_items = any(not item.product.is_digital for item in cart.cart_items.select_related('product').all())
        raw_address = request.data.get('address')
        if has_physical_items and not raw_address:
            raise ValidationError({'address': 'Choose a delivery address first.'})
        address = None
        if raw_address:
            address = get_object_or_404(Address, pk=serializers.IntegerField(min_value=1).run_validation(raw_address),
                                         user=request.user, is_deleted=False)
        payment_type = request.data.get('payment_type', 'cash_on_delivery')
        if payment_type not in ('cash_on_delivery', 'user_wallet'):
            raise ValidationError({'detail': 'Choose cash on delivery, ProAce user wallet, or use Stripe wallet checkout.'})
        shipping_service = str(request.data.get('shipping_service', 'usps_ground_advantage' if has_physical_items else 'digital_delivery')).strip()
        order = self._complete(request, key, address, str(request.data.get('coupon', '')).strip(), payment_type, shipping_service=shipping_service, shipping_quote=request.data.get('shipping_quote'))
        return Response(order_data(order), status=201)


class WalletCheckoutSessionView(CheckoutView):
    @extend_schema(request=WalletCheckoutSerializer, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request):
        if stripe is None or not getattr(settings, 'STRIPE_SECRET', ''):
            raise ValidationError({'detail': 'Wallet payments are not configured.'})
        if getattr(settings, 'STRIPE_CURRENCY', 'usd').lower() != 'usd':
            raise ValidationError({'detail': 'Carrier checkout requires USD payments.'})
        stripe.api_key = settings.STRIPE_SECRET
        key = serializers.UUIDField().run_validation(request.data.get('checkout_key'))
        code = str(request.data.get('coupon', '')).strip()
        cart, snapshots, coupon_lines, subtotal = self._lines(request)
        has_physical_items = any(not row['is_digital'] for row in snapshots)
        raw_address = request.data.get('address')
        if has_physical_items and not raw_address:
            raise ValidationError({'address': 'Choose a delivery address first.'})
        address = None
        if raw_address:
            address = get_object_or_404(Address, pk=serializers.IntegerField(min_value=1).run_validation(raw_address),
                                         user=request.user, is_deleted=False)
        self._validate_service_area(address, snapshots)
        coupon = None
        discount = Decimal('0')
        if code:
            coupon = Coupon.objects.filter(code__iexact=code, active=True, valid_from__lte=timezone.now(), valid_to__gte=timezone.now()).first()
            discount = calculate_coupon_discount(coupon, request.user, coupon_lines, subtotal, reserve=False)
        total_weight = sum(
            Decimal(str(item.product.weight or '1.00')) * item.quantity
            for item in cart.cart_items.select_related('product').all() if not item.product.is_digital
        )
        origin_zip = '33602'
        first_item = cart.cart_items.select_related('product__store').first()
        if first_item:
            store_addr = StoreAddress.objects.filter(store=first_item.product.store).first()
            if store_addr and store_addr.zip:
                origin_zip = store_addr.zip
        dest_zip = address.zip if address else '33602'
        shipping_service = str(request.data.get('shipping_service', 'usps_ground_advantage' if has_physical_items else 'digital_delivery')).strip()
        shipping_quote = request.data.get('shipping_quote')
        paid_amount = None
        if shipping_quote:
            rate = verify_quote(shipping_quote, request.user, cart, address, shipping_service, paid=paid_amount is not None)
        else:
            if not has_physical_items:
                rate = {'carrier': 'DIGITAL', 'service_id': 'digital_delivery', 'amount': '0.00'}
            else:
                carrier = (shipping_service or 'usps_ground_advantage').split('_', 1)[0].upper()
                rates = cart_rates(carrier, cart, address)
                rate = next((row for row in rates if row['service_id'] == shipping_service), None)
                if rate is None:
                    raise ValidationError({'shipping_service': 'Select an available shipping service.'})
        if not has_physical_items:
            shipping_service = 'digital_delivery'
        shipping = Decimal(rate['amount'])
        tax = ((subtotal - discount) * Decimal(str(getattr(settings, 'CHECKOUT_TAX_RATE', '0')))).quantize(Decimal('.01'))
        if paid_amount is not None and int((subtotal - discount + shipping + tax) * 100) != paid_amount:
            raise ValidationError({'detail': 'Paid amount does not match this cart. Contact support.'})
        total = subtotal - discount + shipping + tax
        wallet_amount_raw = request.data.get('wallet_amount')
        wallet_deduction = Decimal('0')
        if wallet_amount_raw is not None and str(wallet_amount_raw).strip():
            try:
                wallet_deduction = Decimal(str(wallet_amount_raw)).quantize(Decimal('.01'))
            except Exception:
                raise ValidationError({'wallet_amount': 'Invalid wallet deduction amount.'})
            if wallet_deduction < Decimal('0'):
                raise ValidationError({'wallet_amount': 'Wallet deduction cannot be negative.'})
            if wallet_deduction > Decimal('0'):
                user_wallet = get_or_create_user_wallet(request.user)
                if user_wallet.balance < wallet_deduction:
                    raise ValidationError({'wallet_amount': 'Insufficient wallet balance.'})
                max_deduction = max(Decimal('0'), total - Decimal('0.50'))
                wallet_deduction = min(wallet_deduction, max_deduction)

        charge_total = total - wallet_deduction
        methods = [
            configured_method.strip()
            for configured_method in getattr(settings, 'STRIPE_WALLET_PAYMENT_METHODS', 'cashapp').split(',')
            if configured_method.strip() and configured_method.strip().lower() != 'paypal'
        ]
        if not methods:
            raise ValidationError({'detail': 'No Stripe wallet payment methods are configured.'})
        shipping_quote = shipping_quote or issue_quote(rate, request.user, cart, address)
        payment_metadata = {
            'checkout_key': str(key),
            'address': str(address.pk) if address else '',
            'coupon': code,
            'shipping_service': shipping_service,
            'shipping_quote': shipping_quote,
            'carrier': rate.get('carrier', 'DIGITAL'),
            'wallet_deduction': str(wallet_deduction),
        }
        session = stripe.checkout.Session.create(
            mode='payment', payment_method_types=methods,
            line_items=[{'price_data': {'currency': getattr(settings, 'STRIPE_CURRENCY', 'usd'),
                                        'product_data': {'name': 'ProAce order'},
                                        'unit_amount': int(charge_total * 100)}, 'quantity': 1}],
            client_reference_id=str(request.user.pk),
            metadata=payment_metadata, payment_intent_data={'metadata': payment_metadata},
            success_url=f"{settings.FRONTEND_URL}/checkout?wallet_session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/checkout?wallet_cancelled=1",
        )
        return Response({'id': session.id, 'url': session.url, 'payment_methods': methods, 'wallet_deduction': str(wallet_deduction)})


class WalletCheckoutConfirmView(CheckoutView):
    @extend_schema(request=serializers.Serializer, responses=OrderSerializer)
    @transaction.atomic
    def post(self, request):
        User.objects.select_for_update().get(pk=request.user.pk)
        session_id = str(request.data.get('session_id', '')).strip()
        if stripe is None or not session_id or not getattr(settings, 'STRIPE_SECRET', ''):
            raise ValidationError({'detail': 'Invalid wallet session.'})
        stripe.api_key = settings.STRIPE_SECRET
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception:
            raise ValidationError({'detail': 'Unable to verify wallet payment.'})
        if session.get('payment_status') != 'paid' or session.get('client_reference_id') != str(request.user.pk):
            raise ValidationError({'detail': 'Wallet payment has not been completed.'})
        key = serializers.UUIDField().run_validation(session.get('metadata', {}).get('checkout_key'))
        existing = Order.objects.filter(checkout_key=key).first()
        if existing:
            if existing.user_id != request.user.pk:
                raise ValidationError({'detail': 'Invalid checkout reference.'})
            return Response(order_data(existing), status=200)
        address_raw = session.get('metadata', {}).get('address')
        address = None
        if address_raw:
            address = get_object_or_404(Address, pk=serializers.IntegerField(min_value=1).run_validation(address_raw),
                                         user=request.user, is_deleted=False)
        paid_amount = serializers.IntegerField(min_value=0).run_validation(session.get('amount_total'))
        if session.get('currency') != 'usd':
            raise ValidationError({'detail': 'Unsupported payment currency.'})
        shipping_service = session.get('metadata', {}).get('shipping_service', 'digital_delivery' if not address else 'usps_ground_advantage')
        wallet_deduction_val = Decimal(str(session.get('metadata', {}).get('wallet_deduction', '0')))
        order = self._complete(
            request, key, address, session.get('metadata', {}).get('coupon', ''),
            'split_tender' if wallet_deduction_val > Decimal('0') else 'stripe_wallet',
            session_id, shipping_service=shipping_service,
            shipping_quote=session.get('metadata', {}).get('shipping_quote'),
            paid_amount=paid_amount + int(wallet_deduction_val * 100),
        )
        if wallet_deduction_val > Decimal('0'):
            debit_user_wallet(
                request.user,
                wallet_deduction_val,
                f'ProAce Wallet split payment for Order #{order.orderId}',
                source=UserWalletTransaction.SOURCE_PURCHASE,
                reference=order.orderId,
            )
        return Response(order_data(order), status=201)



class CouponAdminView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(responses=CouponAdminSerializer(many=True))
    def get(self, request):
        coupons = Coupon.objects.select_related('product').order_by('-created', '-pk')
        return Response(CouponAdminSerializer(coupons, many=True).data)

    @extend_schema(request=CouponAdminSerializer, responses=CouponAdminSerializer)
    def post(self, request):
        serializer = CouponAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(CouponAdminSerializer(serializer.save()).data, status=201)


class PasswordChangeView(APIView):
    @extend_schema(request=PasswordChangeRequestSerializer, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request):
        user = User.objects.select_for_update().get(pk=request.user.pk)
        current = serializers.CharField(trim_whitespace=False).run_validation(request.data.get('current_password'))
        password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False).run_validation(request.data.get('password'))
        if not user.check_password(current):
            raise ValidationError({'current_password': 'Incorrect password.'})
        if user.check_password(password):
            raise ValidationError({'password': 'Choose a different password.'})
        try:
            validate_password(password, user)
        except DjangoValidationError as error:
            raise ValidationError({'password': error.messages})
        user.set_password(password)
        user.must_change_password = False
        user.credential_version += 1
        user.save(update_fields=['password', 'must_change_password', 'credential_version'])
        return Response(tokens(user))
