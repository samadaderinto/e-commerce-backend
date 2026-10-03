from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from notification.delivery import queue_email_delivery
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser
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
from core.models import Address, Review, User, Wishlist
from payment.models import Coupon, CouponRedemption, DeliveryInfo, Order
from payment.couponing import calculate_coupon_discount
from payment.usps import calculate_usps_rates
from product.models import Product
from product.search import search_product_ids
from product.policies import is_own_store, validate_purchase
from store.views import invalidate_catalog
from store.models import Store, StoreAddress
from .serializers import (
    AddressSerializer, AuthRequestSerializer, CartMutationRequestSerializer,
    CartSerializer, CatalogPageSerializer, CouponAdminSerializer,
    CatalogQuerySerializer, CatalogSerializer, CheckoutRequestSerializer,
    OrderSerializer, ProductIdRequestSerializer, RegisterSerializer,
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
            user.save(update_fields=['password'])
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
        products = catalog()
        params = request.query_params
        search = params.get('search')
        if params.get('category'):
            products = products.filter(category=params['category'])
        if params.get('store'):
            store = serializers.IntegerField(min_value=1).run_validation(params['store'])
            products = products.filter(store_id=store)
        else:
            store = None
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
        product = get_object_or_404(catalog(), pk=pk)
        return Response(CatalogSerializer(product, context={'request': request}).data)


class ReviewsView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else super().get_permissions()

    @extend_schema(responses=ReviewSerializer(many=True), auth=[])
    def get(self, request, pk):
        product = get_object_or_404(catalog(), pk=pk)
        return Response(ReviewSerializer(Review.objects.filter(product=product).select_related('user')[:50], many=True).data)

    @extend_schema(request=ReviewSerializer, responses={201: ReviewSerializer, 400: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        product = get_object_or_404(catalog(), pk=pk)
        instance = Review.objects.filter(user=request.user, product=product).first()
        serializer = ReviewSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save(user=request.user, product=product)
        review.set_avg_rating()
        invalidate_catalog(product)
        return Response(serializer.data, status=201)


class WishlistView(APIView):
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
    @extend_schema(responses=AddressSerializer(many=True))
    def get(self, request):
        return Response(AddressSerializer(Address.objects.filter(user=request.user).order_by('-is_default', '-pk'), many=True).data)

    @transaction.atomic
    @extend_schema(request=AddressSerializer, responses={201: AddressSerializer})
    def post(self, request):
        User.objects.select_for_update().get(pk=request.user.pk)
        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('is_default', True):
            Address.objects.filter(user=request.user).update(is_default=False)
        serializer.save(user=request.user)
        return Response(serializer.data, status=201)

    @extend_schema(
        parameters=[OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.QUERY, required=True)],
        responses={204: OpenApiResponse(description='Address deleted.')},
    )
    def delete(self, request):
        pk = serializers.IntegerField(min_value=1).run_validation(
            request.query_params.get('id', request.data.get('id'))
        )
        get_object_or_404(Address, pk=pk, user=request.user).delete()
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
    return Decimal(rates[0]['amount'])


def cart_data(cart, request):
    items = cart.cart_items.select_related('product__store').prefetch_related('product__images', 'product__tags')
    rows = [{'product': CatalogSerializer(item.product, context={'request': request}).data,
             'quantity': item.quantity, 'total': str(unit_price(item.product) * item.quantity),
             'purchasable': not is_own_store(item.product, request.user)
             and item.product.visibility and item.product.store.status == Store.STATUS_ACTIVE
             and item.product.store.verified_at is not None and item.quantity <= item.product.available} for item in items]
    subtotal = sum((Decimal(row['total']) for row in rows), Decimal('0'))
    has_physical_items = any(not row['product']['is_digital'] for row in rows)
    total_weight = sum(
        Decimal(str(row['product'].get('weight') or '1.00')) * row['quantity']
        for row in rows if not row['product']['is_digital']
    )
    shipping = calculate_shipping(subtotal, has_physical_items and bool(rows), total_weight=total_weight)
    return {'id': cart.pk, 'items': rows, 'subtotal': str(subtotal), 'shipping': str(shipping), 'total': str(subtotal + shipping)}


class CartView(APIView):
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
            if quantity > product.available:
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
    return {'id': order.pk, 'reference': order.orderId, 'status': order.status,
            'created': order.created, 'total': str(order.total), 'subtotal': str(order.subtotal),
            'payment_type': order.payment_type, 'items': order.items_snapshot,
            'address': order.address_snapshot}


class OrdersView(APIView):
    @extend_schema(responses=OrderSerializer(many=True))
    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-created')
        return Response([order_data(order) for order in orders[:100]])


class OrderDetailView(APIView):
    @extend_schema(responses=OrderSerializer)
    def get(self, request, pk):
        orders = Order.objects.filter(user=request.user).order_by('-created')
        return Response(order_data(get_object_or_404(orders, pk=pk)))


class ShippingRatesView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter('address', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False, description='Address ID for shipping calculation'),
        ],
        responses={200: ShippingRateSerializer(many=True)},
    )
    def get(self, request):
        cart = active_cart(request.user)
        items = list(cart.cart_items.select_related('product__store').all())
        if not items:
            return Response([])

        has_physical_items = any(not item.product.is_digital for item in items)
        total_weight = sum(
            Decimal(str(item.product.weight or '1.00')) * item.quantity
            for item in items if not item.product.is_digital
        )
        subtotal = sum((unit_price(item.product) * item.quantity for item in items), Decimal('0'))

        origin_zip = '33602'
        store_addr = StoreAddress.objects.filter(store=items[0].product.store).first()
        if store_addr and store_addr.zip:
            origin_zip = store_addr.zip

        dest_zip = '33602'
        address_id = request.query_params.get('address')
        if address_id:
            try:
                addr = Address.objects.get(pk=address_id, user=request.user)
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

        rates = calculate_usps_rates(origin_zip, dest_zip, total_weight, subtotal, has_physical_items)
        return Response(rates)


class CheckoutView(APIView):
    @staticmethod
    def _validate_service_area(address, snapshots):
        country = ''.join(character for character in address.country.lower() if character.isalnum())
        us_names = {'us', 'usa', 'unitedstates', 'unitedstatesofamerica'}
        if any(not row['is_digital'] for row in snapshots) and country not in us_names:
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
                    or product.store.verified_at is None or product.available < item.quantity):
                raise ValidationError({'detail': f'{product.title} is unavailable in the requested quantity.'})
            price = unit_price(product)
            snapshots.append({'product': product.pk, 'store': product.store_id, 'title': product.title,
                              'image': product.image_url, 'quantity': item.quantity, 'unit_price': str(price),
                              'is_digital': product.is_digital,
                              'download_url': product.digital_file_url if product.is_digital else ''})
            coupon_lines.append({'product': product, 'quantity': item.quantity, 'unit_price': price})
        subtotal = sum((Decimal(row['unit_price']) * row['quantity'] for row in snapshots), Decimal('0'))
        if subtotal > Decimal('99999999.99'):
            raise ValidationError({'detail': 'Order value exceeds the supported maximum.'})
        return cart, snapshots, coupon_lines, subtotal

    def _complete(self, request, key, address, code, payment_type, stripe_session_id=None, shipping_service=None):
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
        dest_zip = address.zip or '33602'
        shipping = calculate_shipping(subtotal, has_physical_items, origin_zip=origin_zip, dest_zip=dest_zip, total_weight=total_weight, service_id=shipping_service)
        delivery_method = 'home delivery' if has_physical_items else 'digital'
        delivery_service = shipping_service or ('usps_ground_advantage' if has_physical_items else 'digital_delivery')
        delivery = DeliveryInfo.objects.create(
            user=request.user, address=address, method=delivery_method,
            delivery_type=delivery_service, total=int(shipping)
        )
        order = Order.objects.create(
            user=request.user, cart=cart, delivery=delivery, status='confirmed', ordered=True,
            coupon_code=code, total=subtotal - discount + shipping, subtotal=subtotal,
            payment_type=payment_type, checkout_key=key, stripe_session_id=stripe_session_id,
            items_snapshot=snapshots, address_snapshot=AddressSerializer(address).data,
        )
        if coupon:
            CouponRedemption.objects.filter(coupon=coupon, user=request.user).update(order=order)
        cart.ordered = True
        cart.save(update_fields=['ordered', 'updated'])
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
        address = get_object_or_404(Address, pk=serializers.IntegerField(min_value=1).run_validation(request.data.get('address')),
                                     user=request.user)
        payment_type = request.data.get('payment_type', 'cash_on_delivery')
        if payment_type != 'cash_on_delivery':
            raise ValidationError({'detail': 'Choose cash on delivery or use the wallet checkout.'})
        shipping_service = str(request.data.get('shipping_service', 'usps_ground_advantage')).strip()
        order = self._complete(request, key, address, str(request.data.get('coupon', '')).strip(), payment_type, shipping_service=shipping_service)
        return Response(order_data(order), status=201)


class WalletCheckoutSessionView(CheckoutView):
    @extend_schema(request=WalletCheckoutSerializer, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request):
        if stripe is None or not getattr(settings, 'STRIPE_SECRET', ''):
            raise ValidationError({'detail': 'Wallet payments are not configured.'})
        stripe.api_key = settings.STRIPE_SECRET
        key = serializers.UUIDField().run_validation(request.data.get('checkout_key'))
        address = get_object_or_404(Address, pk=serializers.IntegerField(min_value=1).run_validation(request.data.get('address')),
                                     user=request.user)
        code = str(request.data.get('coupon', '')).strip()
        shipping_service = str(request.data.get('shipping_service', 'usps_ground_advantage')).strip()
        cart, snapshots, coupon_lines, subtotal = self._lines(request)
        self._validate_service_area(address, snapshots)
        coupon = None
        discount = Decimal('0')
        if code:
            coupon = Coupon.objects.filter(code__iexact=code, active=True, valid_from__lte=timezone.now(), valid_to__gte=timezone.now()).first()
            discount = calculate_coupon_discount(coupon, request.user, coupon_lines, subtotal, reserve=False)
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
        dest_zip = address.zip or '33602'
        shipping = calculate_shipping(subtotal, has_physical_items, origin_zip=origin_zip, dest_zip=dest_zip, total_weight=total_weight, service_id=shipping_service)
        total = subtotal - discount + shipping
        methods = [
            configured_method.strip()
            for configured_method in getattr(settings, 'STRIPE_WALLET_PAYMENT_METHODS', 'cashapp').split(',')
            if configured_method.strip() and configured_method.strip().lower() != 'paypal'
        ]
        if not methods:
            raise ValidationError({'detail': 'No Stripe wallet payment methods are configured.'})
        session = stripe.checkout.Session.create(
            mode='payment', payment_method_types=methods,
            line_items=[{'price_data': {'currency': getattr(settings, 'STRIPE_CURRENCY', 'usd'),
                                        'product_data': {'name': 'ProAce order'},
                                        'unit_amount': int(total * 100)}, 'quantity': 1}],
            client_reference_id=str(request.user.pk),
            metadata={'checkout_key': str(key), 'address': str(address.pk), 'coupon': code, 'shipping_service': shipping_service},
            success_url=f"{settings.FRONTEND_URL}/checkout?wallet_session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/checkout?wallet_cancelled=1",
        )
        return Response({'id': session.id, 'url': session.url, 'payment_methods': methods})


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
        address = get_object_or_404(Address, pk=serializers.IntegerField(min_value=1).run_validation(session.get('metadata', {}).get('address')),
                                     user=request.user)
        shipping_service = session.get('metadata', {}).get('shipping_service', 'usps_ground_advantage')
        order = self._complete(request, key, address, session.get('metadata', {}).get('coupon', ''), 'stripe_wallet', session_id, shipping_service=shipping_service)
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
