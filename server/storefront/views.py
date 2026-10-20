from __future__ import annotations

from core.throttles import AccountAuthThrottle
from core.listing_filters import ListingQuerySerializer, filter_records, record_page

import logging
from decimal import Decimal
from datetime import timedelta
from typing import Any
from uuid import UUID
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q, F, Case, When, QuerySet, OuterRef, Subquery, IntegerField, Value, Prefetch
from django.db.models.functions import Coalesce
from django.http import Http404, FileResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from core.auth_tokens import credential_version_token_generator
from notification.delivery import queue_email_delivery
from utils.functions import send_mail
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from core.access import IsCustomer, IsBackoffice, IsBusinessAdmin as IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError
try:
    import stripe
except ImportError:  # Wallet payments remain unavailable until the optional SDK is installed.
    stripe = None
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from cart.models import Cart, CartItem
from affiliates.services import record_referral, reward_referral, process_referral_reward_for_order
from core.models import Address, Refund, Review, User, Wishlist, UserWallet, UserWalletTransaction
from core.serializers import UserWalletSerializer, UserWalletTransactionSerializer
from core.services import get_or_create_user_wallet, credit_user_wallet, debit_user_wallet
from notification.views import create_notification
from payment.models import Coupon, CouponRedemption, DeliveryInfo, Order, OrderFulfillment, TaxJurisdiction
from payment.serializers import TaxJurisdictionSerializer
from payment.accounting import allocate_amount, allocate_checkout_lines, allocate_line_taxes, order_paid_lines
from payment.refund_messages import refund_failure_reason
from payment.services import execute_order_status_transition
from payment.couponing import calculate_coupon_discount
from payment.tax import calculate_tax
from payment.carriers import calculate_carrier_rates, CARRIERS
from payment.shipping_quotes import issue_quote, verify_quote, cart_rates
from product.models import Product
from product.search import search_product_ids
from observability.stages import stage
from product.policies import is_own_store, validate_purchase
from store.views import invalidate_catalog
from store.models import Store, StoreAddress, StoreInfo
from store.services import record_order_earnings_for_merchant
from .serializers import (
    WalletTopupRequestSerializer, PaymentSessionRequestSerializer,
    PasswordChangeRequestSerializer, AddressSerializer, AuthRequestSerializer, CartMutationRequestSerializer,
    CartSerializer, CatalogPageSerializer, CouponAdminSerializer,
    CatalogQuerySerializer, CatalogSerializer, CartProductSerializer, CheckoutRequestSerializer,
    OrderSerializer, OrderTrackingSerializer, ProductIdRequestSerializer, PublicStoreSerializer, RefundRequestSerializer, RegisterSerializer,
    ReviewSerializer, ShippingRateSerializer, UserSerializer, UserAvatarImageSerializer, WalletCheckoutSerializer, unit_price,
    VisualSearchResponseSerializer, VisualSearchPresetLookSerializer, VisualSearchRequestSerializer,
)


def with_catalog_details(products: QuerySet[Product]) -> QuerySet[Product]:
    reviews = (
        Review.objects.filter(product_id=OuterRef('pk'))
        .order_by()
        .values('product_id')
        .annotate(total=Count('pk'))
        .values('total')[:1]
    )
    # A scalar review count avoids grouping the entire catalog for pagination totals.
    return (
        products.select_related('store', 'specification')
        .prefetch_related('images', 'tags')
        .annotate(
            rating_count=Coalesce(
                Subquery(reviews, output_field=IntegerField()),
                Value(0),
            ),
        )
    )


def catalog() -> QuerySet[Product]:
    return with_catalog_details(
        Product.objects.filter(
            visibility=True, is_blocked=False,
            store__status=Store.STATUS_ACTIVE,
            store__verified_at__isnull=False,
        )
    )


def filter_catalog_text(products: QuerySet[Product], search: str) -> QuerySet[Product]:
    """Match every search term across product copy, classification and tags."""
    for term in search.split():
        products = products.filter(
            Q(title__icontains=term)
            | Q(brand__icontains=term)
            | Q(description__icontains=term)
            | Q(category__icontains=term)
            | Q(tags__name__icontains=term)
        )
    return products.distinct()


def tokens(user):
    refresh = RefreshToken.for_user(user)
    refresh["credential_version"] = user.credential_version
    access = refresh.access_token
    access["credential_version"] = user.credential_version
    return {'access': str(access), 'refresh': str(refresh), 'user': UserSerializer(user).data}


class AuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AccountAuthThrottle]
    throttle_scope = 'auth'

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        from collections.abc import Mapping

        if not isinstance(request.data, Mapping):
            raise ValidationError({'detail': 'Submit a JSON object with authentication fields.'})
        super().initial(request, *args, **kwargs)

    def get_throttles(self) -> list[AccountAuthThrottle]:
        from core.throttles import ClientAuthThrottle

        return [AccountAuthThrottle(), ClientAuthThrottle()]

    @extend_schema(
        request=AuthRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            201: OpenApiTypes.OBJECT,
            204: OpenApiResponse(description='Logged out successfully.'),
            409: OpenApiResponse(description='Already signed in; sign out before authenticating again.'),
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
        auth=[],
        description=(
            'Submit an action-specific payload. Supported actions: login, register, verify, '
            'forgot, reset, refresh, logout, google, apple, and social. Successful authentication returns access and refresh '
            'JWTs plus the user; other actions return a detail message or refreshed token.'
        ),
    )
    def post(self, request: Request, action: str) -> Response:
        if action in ('login', 'register', 'google', 'apple', 'social'):
            from rest_framework.exceptions import AuthenticationFailed
            from rest_framework_simplejwt.authentication import JWTAuthentication
            authenticated = request.user if request.user.is_authenticated else None
            if authenticated is None:
                try:
                    result = JWTAuthentication().authenticate(request)
                except AuthenticationFailed:
                    result = None
                if result and result[1].get('credential_version', 0) == result[0].credential_version:
                    authenticated = result[0]
            if authenticated is not None:
                return Response(
                    {'detail': 'You are already signed in. Sign out before signing in or creating another account.'},
                    status=409,
                )
        data = request.data
        if action in ('google', 'apple', 'social'):
            from core.social_auth import authenticate_social_user
            provider = action if action in ('google', 'apple') else str(data.get('provider', '')).strip().lower()
            return Response(authenticate_social_user(provider, data, request), status=200)
        if action == 'login':
            email = str(data.get('email', '')).strip().lower()
            password = data.get('password', '')
            if not isinstance(password, str) or len(password) > 128:
                raise ValidationError({'detail': 'Invalid email or password.'})
            user = authenticate(request, email=email, password=password)
            if user is None:
                # Older invited accounts may have been stored with mixed-case
                # local parts. Preserve case-insensitive login during migration.
                candidate = User.objects.filter(email__iexact=email).first()
                if candidate and candidate.email != email:
                    user = authenticate(request, email=candidate.email, password=password)
            if user is None:
                inactive_user = User.objects.filter(email__iexact=email, is_active=False).first()
                if inactive_user and inactive_user.check_password(password):
                    return Response({'detail': 'Your account is inactive. Please verify your email before signing in.'}, status=401)
                return Response({'detail': 'Invalid email or password.'}, status=401)
            from django.contrib.auth.models import update_last_login
            from core.activity import record_activity
            update_last_login(None, user)
            from core.models import Device
            Device.objects.filter(user=user, device_ip=request.META.get('REMOTE_ADDR')).update(last_login=user.last_login)
            record_activity(user)
            from store.services import link_pending_store_team_invitations
            link_pending_store_team_invitations(user)
            return Response(tokens(user))
        if action == 'register':
            payload = {**data, 'email': str(data.get('email', '')).strip().lower()}
            serializer = RegisterSerializer(data=payload)
            try:
                serializer.is_valid(raise_exception=True)
            except DjangoValidationError as error:
                raise ValidationError({'password': error.messages})
            referral_code = serializer.validated_data.pop('referral_code', '').strip()
            try:
                with transaction.atomic():
                    user = User.objects.create_user(**serializer.validated_data, is_active=False)
                    from store.services import link_pending_store_team_invitations
                    link_pending_store_team_invitations(user)
                    token_payload = {'user': user.pk, 'version': user.credential_version}
                    if referral_code:
                        token_payload['ref'] = referral_code
                    token = signing.dumps(token_payload, salt='proace-verify')
                    url = f'{settings.FRONTEND_URL}/verify-email?token={token}'
                    send_mail(
                        'onboarding-user',
                        user.email,
                        {
                            'firstname': user.first_name,
                            'absolute_url': url,
                            'subject': 'Verify your ProAce account',
                        },
                    )
            except IntegrityError:
                raise ValidationError({'email': 'An account with this email already exists.'}) from None
            return Response({'detail': 'Check your email to activate your account.'}, status=201)
        if action == 'verify':
            raw_token = str(data.get('token', '')).strip().split('"')[0].split("'")[0].split('<')[0].split('&')[0].split(' ')[0]
            raw_token = raw_token.removeprefix('=3D')
            if raw_token.startswith('staff:'):
                from core.onboarding import activate_staff
                activate_staff(raw_token[6:])
                return Response({'detail': 'Email verified. Please check your email to set your password.'})
            try:
                payload = signing.loads(raw_token, salt='proace-verify', max_age=86400)
                with transaction.atomic():
                    user = User.objects.select_for_update().get(pk=payload['user'])
                    if user.is_active or payload['version'] != user.credential_version:
                        raise ValueError()
                    user.is_active = True
                    user.credential_version += 1
                    user.save(update_fields=['is_active', 'credential_version'])
                    from store.services import link_pending_store_team_invitations
                    link_pending_store_team_invitations(user)
                    ref = str(payload.get('ref') or '').strip()
                    if ref:
                        record_referral(ref, user)
            except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError, ValueError):
                raise ValidationError({'detail': 'This verification link is invalid or expired.'})
            return Response({'detail': 'Email verified. You can now sign in.'})
        if action == 'forgot':
            email = serializers.EmailField().run_validation(data.get('email'))
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = credential_version_token_generator.make_token(user)
                url = f'{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}'
                send_mail(
                    'password-reset',
                    user.email,
                    {
                        'firstname': user.first_name,
                        'email': user.email,
                        'absolute_url': url,
                        'subject': 'Reset your ProAce password',
                    },
                )
            return Response({'detail': 'If an active account exists, a reset link has been sent.'})
        if action == 'reset':
            for field in ('uid', 'token'):
                value = data.get(field)
                if not isinstance(value, str) or not value.strip() or len(value) > 256:
                    raise ValidationError({'detail': 'Invalid reset link.'})
            try:
                decoded_uid = force_str(urlsafe_base64_decode(data.get('uid', '')))
                if not decoded_uid.isascii() or not decoded_uid.isdecimal() or len(decoded_uid) > 19:
                    raise ValueError()
                user_pk = int(decoded_uid)
                if user_pk < 1 or user_pk > 9223372036854775807:
                    raise ValueError()
            except (ValueError, TypeError, UnicodeDecodeError, User.DoesNotExist):
                raise ValidationError({'detail': 'Invalid reset link.'})
            with transaction.atomic():
                try:
                    user = User.objects.select_for_update().get(pk=user_pk)
                except User.DoesNotExist:
                    raise ValidationError({'detail': 'Invalid reset link.'}) from None
                if (
                    not user.is_active
                    or not credential_version_token_generator.check_token(user, data.get('token', ''))
                ):
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
                from notification.views import password_changed_notification

                password_changed_notification(user)
                from core.auth_sync import sync_technical_admin_credentials, is_technical_super_admin
                if is_technical_super_admin(user):
                    sync_technical_admin_credentials(user, password)
                from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
                for token in OutstandingToken.objects.filter(user=user):
                    BlacklistedToken.objects.get_or_create(token=token)
                return Response({'detail': 'Password updated. Sign in with your new password.'})
        if action == 'refresh':
            from core.access import VersionedTokenRefreshSerializer

            serializer = VersionedTokenRefreshSerializer(data=data)
            try:
                serializer.is_valid(raise_exception=True)
            except TokenError as error:
                return Response(
                    {'detail': str(error), 'code': 'token_not_valid'},
                    status=401,
                )
            return Response(serializer.validated_data)
        if action == 'logout':
            try:
                refresh = str(data.get('refresh') or '')
                if refresh:
                    RefreshToken(refresh).blacklist()
            except TokenError:
                # Expired or malformed logout tokens are already unusable.
                return Response(status=204)
            except Exception:
                logger.exception('Failed to revoke refresh token during logout')
                return Response(
                    {'detail': 'Unable to confirm session revocation. Please try again.'},
                    status=503,
                )
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

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @transaction.atomic
    def delete(self, request: Request) -> Response:
        user = User.objects.select_for_update().get(pk=request.user.pk)
        email = str(user.email)
        first_name = str(user.first_name)
        user.is_active = False
        user.credential_version += 1
        user.save(update_fields=["is_active", "credential_version"])
        send_mail(
            "account-delete-confirmation",
            email,
            {
                "firstname": first_name,
                "email": email,
                "subject": "ProAce Account Closure Confirmation",
            },
        )
        return Response({"detail": "Your account has been deactivated. Contact support for data deletion requests."})


class MeAvatarView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        methods=['POST'],
        request=UserAvatarImageSerializer,
        responses=UserSerializer,
        description='Upload a 512x512 profile avatar image for the authenticated user.',
    )
    def post(self, request: Request) -> Response:
        serializer = UserAvatarImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.avatar_image = serializer.validated_data['image']
        user.avatar_url = ''
        user.save(update_fields=['avatar_image', 'avatar_url', 'updated'])
        return Response(UserSerializer(user, context={'request': request}).data)

    @extend_schema(
        methods=['DELETE'],
        responses=UserSerializer,
        description='Remove the profile avatar image for the authenticated user.',
    )
    def delete(self, request: Request) -> Response:
        user = request.user
        user.avatar_image = ''
        user.avatar_url = ''
        user.save(update_fields=['avatar_image', 'avatar_url', 'updated'])
        return Response(UserSerializer(user, context={'request': request}).data)


class ProductsView(APIView):
    permission_classes = [AllowAny]

    def _page_response(
        self, products: QuerySet[Product], request: Request, page: int
    ) -> Response:
        # Sort/offset narrow IDs, not the full model graph and review subqueries.
        with stage("hydrate"):
            count = products.count()
            if (page - 1) * 24 >= count:
                rows = []
            elif page == 1:
                # The ordering index can fetch the first 24 rows directly; retain
                # the existing five-query budget on the common first page.
                rows = list(products[:24])
            else:
                ids = list(products.values_list('pk', flat=True)[(page - 1) * 24:page * 24])
                by_id = products.order_by().filter(pk__in=ids).in_bulk(ids)
                rows = [by_id[pk] for pk in ids if pk in by_id]
        with stage("serialize"):
            results = CatalogSerializer(rows, many=True, context={'request': request}).data
        return Response({
            'count': count, 'page': page,
            'pages': max(1, (count + 23) // 24), 'results': results,
        })

    @extend_schema(
        operation_id='storefront_products_list',
        parameters=[CatalogQuerySerializer, ListingQuerySerializer],
        responses=CatalogPageSerializer,
        auth=[],
        description='Returns a page of active-store products. Each page contains at most 24 results.',
    )
    def get(self, request: Request) -> Response:
        from .catalog_cache import coalesced_snapshot, snapshot_key, read_snapshot, write_snapshot

        with stage("catalog_cache"):
            key = snapshot_key(request)
            cached = read_snapshot(key)
            if cached is None:
                cached = coalesced_snapshot(key)
        if cached is not None:
            response = Response(cached)
            response['X-Catalog-Cache'] = 'HIT'
            return response
        response = self._get_uncached(request)
        if response.status_code == 200:
            write_snapshot(
                key,
                response.data,
                request.build_absolute_uri() if not request.query_params else None,
            )
        response['X-Catalog-Cache'] = 'MISS' if key else 'BYPASS'
        return response

    def _get_uncached(self, request: Request) -> Response:
        params = request.query_params
        is_store_preview = False
        store_obj = None

        if params.get('store'):
            store = serializers.IntegerField(min_value=1).run_validation(params['store'])
            store_obj = Store.objects.filter(pk=store).first()
            if store_obj and (store_obj.status != Store.STATUS_ACTIVE or not store_obj.verified_at):
                user = request.user
                is_authorized = bool(user and user.is_authenticated and (user == store_obj.user or user.is_staff or user.is_superuser))
                if is_authorized:
                    is_store_preview = True
                    products = with_catalog_details(
                        Product.objects.filter(store=store_obj, visibility=True)
                    )
                else:
                    products = Product.objects.none()
            else:
                products = catalog().filter(store_id=store)
                if store_obj and not store_obj.is_official:
                    products = products.filter(product_type=Product.PRODUCT_TYPE_STANDARD)
        else:
            store = None
            products = catalog()

        products = filter_records(
            products, params, fields={"is_digital": "is_digital", "product_type": "product_type"},
        )
        search = str(params.get('search') or '').strip()
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
        valid_orderings = ['-created', 'price', '-price', '-average_rating', '-sales', '-discount']
        if ordering not in valid_orderings:
            ordering = '-created'
        search_ordering = ordering if params.get('ordering') in valid_orderings else None
        page = CatalogQuerySerializer().fields['page'].run_validation(params.get('page', 1))
        page_size = 24
        offset = (page - 1) * page_size
        if search:
            if (
                not is_store_preview
                and not params.get("is_digital")
                and not params.get("product_type")
                and not params.get("start_date")
                and not params.get("end_date")
            ):
                from django.db import connection

                with stage("search"):
                    search_results = search_product_ids(
                        search,
                        filters={
                            'category': params.get('category') or None,
                            'store_id': store,
                            'deals': params.get('deals') == 'true',
                            'min_price': min_price,
                            'max_price': max_price,
                        },
                        ordering=search_ordering,
                        offset=offset,
                        limit=page_size,
                        use_request_cache=(
                            not request.user.is_authenticated
                            and not connection.in_atomic_block
                        ),
                    )
                if search_results is not None:
                    ids = search_results['ids']
                    count = search_results['count']
                    with stage("hydrate"):
                        products_by_id = products.filter(pk__in=ids).in_bulk(ids)
                    expected = max(0, min(page_size, count - offset))
                    if len(products_by_id) == len(ids) == expected:
                        indexed_products = [products_by_id[pk] for pk in ids]
                        with stage("serialize"):
                            results = CatalogSerializer(
                                indexed_products, many=True, context={'request': request}
                            ).data
                        return Response({
                            'count': count,
                            'page': page,
                            'pages': max(1, (count + page_size - 1) // page_size),
                            'results': results,
                        })
                    logger.warning('Stale search page detected; using authoritative catalog search')
            products = filter_catalog_text(products, search)
            if search_ordering is None:
                products = products.order_by(
                    Case(
                        When(title__iexact=search, then=Value(0)),
                        When(title__istartswith=search, then=Value(1)),
                        When(title__icontains=search, then=Value(2)),
                        When(brand__icontains=search, then=Value(3)),
                        default=Value(4),
                        output_field=IntegerField(),
                    ),
                    '-average_rating',
                    '-created',
                    '-pk',
                )
                return self._page_response(products, request, page)
        if store_obj:
            store_info = StoreInfo.objects.filter(store=store_obj).only('pinned_products').first()
            raw_pinned = store_info.pinned_products if store_info and isinstance(store_info.pinned_products, list) else []
            pinned_ids = [int(p) for p in raw_pinned if str(p).isdigit()][:3]
            if pinned_ids:
                when_clauses = [When(pk=pid, then=Value(idx)) for idx, pid in enumerate(pinned_ids)]
                pinned_order = Case(*when_clauses, default=Value(len(pinned_ids)), output_field=IntegerField())
                return self._page_response(products.order_by(pinned_order, ordering, '-pk'), request, page)

        return self._page_response(products.order_by(ordering, '-pk'), request, page)


class ProductDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id='storefront_product_retrieve', responses=CatalogSerializer, auth=[])
    def get(self, request: Request, pk: int) -> Response:
        product = catalog().filter(pk=pk).first()
        if not product:
            raw_product = with_catalog_details(
                Product.objects.filter(pk=pk)
            ).first()
            if not raw_product:
                raise Http404('No Product matches the given query.')
            user = request.user
            is_authorized = bool(
                user and user.is_authenticated and (
                    user == raw_product.store.user
                    or getattr(user, 'is_staff', False)
                    or getattr(user, 'is_superuser', False)
                    or getattr(user, 'is_business_admin', False)
                )
            )
            is_staff_operator = bool(
                getattr(user, 'is_staff', False)
                or getattr(user, 'is_superuser', False)
                or getattr(user, 'is_business_admin', False)
            )
            operator_preview = is_staff_operator and request.query_params.get('preview') == '1'
            if (
                not is_authorized
                or (not raw_product.visibility and not operator_preview)
                or (raw_product.is_blocked and not is_staff_operator)
            ):
                raise Http404('No Product matches the given query.')
            product = raw_product
        if request.user.is_authenticated:
            from core.models import Recent
            with transaction.atomic():
                User.objects.select_for_update().get(pk=request.user.pk)
                recent = Recent.objects.filter(user=request.user, product=product).order_by('-updated').first()
                if recent:
                    recent.save(update_fields=['updated'])
                else:
                    Recent.objects.create(user=request.user, product=product)
        return Response(CatalogSerializer(product, context={'request': request}).data)


class ProductDropLiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        operation_id='storefront_product_drop_live',
        responses={200: OpenApiTypes.OBJECT},
        auth=[],
        description='Real-time drop presence and countdown status stream via SSE or JSON.'
    )
    def get(self, request: Request, pk: int) -> Response | StreamingHttpResponse:
        product = get_object_or_404(catalog(), pk=pk)

        if request.query_params.get('format') == 'json' or request.headers.get('Accept') == 'application/json':
            from django.core.cache import cache
            cached_viewers = cache.get(f'drop_viewers:{pk}', 1)
            return Response({
                'product_id': product.pk,
                'viewers': max(1, int(cached_viewers)),
                'drop_at': product.drop_at.isoformat() if product.drop_at else None,
                'is_dropped': not product.is_upcoming_drop,
                'server_time': timezone.now().isoformat(),
            })

        import uuid
        import time
        from collections.abc import Iterator
        from django.core.cache import cache
        from notification.realtime import broker, encode_event

        client_token = str(uuid.uuid4())
        viewers_cache_key = f'drop_viewers:{pk}'

        def events() -> Iterator[str]:
            redis_client = None
            try:
                redis_client = broker()
            except Exception:
                redis_client = None

            try:
                if redis_client:
                    try:
                        redis_client.sadd(f'drop:viewers:set:{pk}', client_token)
                        redis_client.expire(f'drop:viewers:set:{pk}', 60)
                        count = redis_client.scard(f'drop:viewers:set:{pk}')
                    except Exception:
                        count = 1
                else:
                    count = cache.get(viewers_cache_key, 1)

                yield 'retry: 3000\n\n'

                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    from product.models import Product
                    curr = Product.objects.filter(pk=pk).first()
                    is_dropped = not (curr and curr.is_upcoming_drop)

                    if redis_client:
                        try:
                            count = redis_client.scard(f'drop:viewers:set:{pk}')
                        except Exception:
                            count = 1

                    data = {
                        'product_id': pk,
                        'viewers': max(1, count),
                        'drop_at': curr.drop_at.isoformat() if curr and curr.drop_at else None,
                        'is_dropped': is_dropped,
                        'server_time': timezone.now().isoformat(),
                    }
                    yield encode_event('drop_status', data)

                    if is_dropped and curr and curr.drop_at:
                        yield encode_event('dropped', {'product_id': pk, 'is_dropped': True})
                        break

                    time.sleep(3)
            except GeneratorExit:
                pass
            finally:
                if redis_client:
                    try:
                        redis_client.srem(f'drop:viewers:set:{pk}', client_token)
                        redis_client.close()
                    except Exception:
                        pass

        response = StreamingHttpResponse(events(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache, no-transform'
        response['X-Accel-Buffering'] = 'no'
        return response


class VisualSearchPresetsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='storefront_visual_search_presets',
        responses=VisualSearchPresetLookSerializer(many=True),
        auth=[],
        description='Returns curated sample looks for instant visual search and shop-the-look test drive.',
    )
    def get(self, request: Request) -> Response:
        from product.visual_search import PRESET_LOOKS
        return Response([
            {**preset, 'items': [{**item, 'confidence': None} for item in preset['items']]}
            for preset in PRESET_LOOKS.values()
        ])


class VisualSearchView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = 'visual_search'

    @extend_schema(
        operation_id='storefront_visual_search',
        request=VisualSearchRequestSerializer,
        responses=VisualSearchResponseSerializer,
        auth=[],
        description='Local image recognition with image-to-description catalog ranking. Presets are curated metadata examples, not recognition.',
    )
    def post(self, request: Request) -> Response:
        import re
        from product.visual_search import VisualSearchEngine, PRESET_LOOKS

        inputs = VisualSearchRequestSerializer(data=request.data)
        inputs.is_valid(raise_exception=True)
        data = inputs.validated_data
        image_file = data.get('image')
        preset_id = data.get('preset_id')
        item_id = data.get('item_id')
        user_query = data.get('query', '')
        category_filter = data.get('category', '')
        store_id = data.get('store_id')
        focus_box = data.get('focus_box')

        if image_file:
            image = VisualSearchEngine.load_and_validate_image(image_file)
            analysis = VisualSearchEngine.analyze_look(
                image=image,
                focus_box=focus_box,
                selected_item_id=item_id,
                user_query=user_query,
                category_filter=category_filter,
                store_id=store_id,
            )
        elif preset_id and preset_id in PRESET_LOOKS:
            preset = PRESET_LOOKS[preset_id]
            items = [{**item, 'confidence': None} for item in preset['items']]
            active_item = None
            if item_id:
                for item in items:
                    if item['id'] == item_id:
                        active_item = item
                        break
            if not active_item and items:
                active_item = items[0]

            target_category = category_filter or (active_item['category'] if active_item else '')
            target_colors = active_item.get('dominant_colors', []) if active_item else []
            target_keywords = list(active_item.get('keywords', [])) if active_item else []
            if user_query:
                target_keywords.extend([t.lower() for t in re.findall(r"\b[a-zA-Z0-9_-]+\b", user_query)])

            matched_results = VisualSearchEngine.match_products(
                target_category=target_category,
                target_colors=target_colors,
                target_keywords=target_keywords,
                user_query=user_query,
                store_id=store_id,
            )
            analysis = {
                'palette': [],
                'method': 'preset_metadata',
                'message': 'Curated example look: related category and catalog text, not image recognition.',
                'detected_items': items,
                'selected_item_id': active_item['id'] if active_item else None,
                'selected_item': active_item,
                'results': matched_results,
                'query_applied': user_query or (active_item['label'] if active_item else preset['title']),
            }
        else:
            raise ValidationError({'image': 'Provide an image file or a valid preset_id.'})

        serialized_results = []
        for item in analysis['results']:
            serialized_results.append({
                'similarity_score': item['similarity_score'],
                'match_reasons': item['match_reasons'],
                'product': CatalogSerializer(item['product'], context={'request': request}).data,
            })

        response_data = {
            'method': analysis['method'],
            'message': analysis['message'],
            'palette': analysis['palette'],
            'detected_items': analysis['detected_items'],
            'selected_item_id': analysis['selected_item_id'],
            'selected_item': analysis.get('selected_item'),
            'selection_required': analysis.get('selection_required', False),
            'results': serialized_results,
            'query_applied': analysis['query_applied'],
        }
        return Response(response_data)


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


class PublicStoreImageView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='storefront_store_branding_image',
        responses={(200, 'image/png'): OpenApiTypes.BINARY},
        description='Public store branding image; unverified stores require owner or backoffice access.',
    )
    def get(self, request: Request, pk: int, kind: str) -> FileResponse:
        store = get_object_or_404(Store, pk=pk)
        user = request.user
        public = store.status == Store.STATUS_ACTIVE and store.verified_at is not None
        authorized = user.is_authenticated and (
            user == store.user or user.is_staff or user.is_superuser
        )
        if not public and not authorized:
            raise Http404('No Store matches the given query.')
        if kind not in {'avatar', 'banner'}:
            raise Http404('No image matches the given query.')
        profile = StoreInfo.objects.filter(store=store).order_by('pk').first()
        image = getattr(profile, f'{kind}_image', None)
        if not image:
            raise Http404('No image matches the given query.')
        try:
            return FileResponse(image.open('rb'), filename=image.name.rsplit('/', 1)[-1])
        except (FileNotFoundError, OSError):
            raise Http404('No image matches the given query.')


class PublicUserImageView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='public_user_avatar_image',
        responses={(200, 'image/png'): OpenApiTypes.BINARY},
        description='Public avatar image for a user profile.',
    )
    def get(self, request: Request, pk: int) -> FileResponse:
        user = get_object_or_404(User, pk=pk)
        image = getattr(user, 'avatar_image', None)
        if not image:
            raise Http404('No image matches the given query.')
        try:
            return FileResponse(image.open('rb'), filename=image.name.rsplit('/', 1)[-1])
        except (FileNotFoundError, OSError):
            raise Http404('No image matches the given query.')


def verified_buyer_ids(product_id: int, user_ids: set[int]) -> set[int]:
    """Return purchasers for one product with bounded database queries."""
    if not user_ids:
        return set()

    eligible_orders = list(
        Order.objects.filter(user_id__in=user_ids, ordered=True)
        .exclude(status__in=['cancelled', 'refunded'])
        .only('user_id', 'cart_id', 'items_snapshot')
    )
    verified_ids: set[int] = set()
    legacy_cart_ids: list[int] = []
    for order in eligible_orders:
        rows = order.items_snapshot if isinstance(order.items_snapshot, list) else []
        if any(
            isinstance(item, dict)
            and str(item.get('product', '')) == str(product_id)
            for item in rows
        ):
            if order.user_id is not None:
                verified_ids.add(order.user_id)
        elif order.cart_id:
            legacy_cart_ids.append(order.cart_id)

    matching_carts = set(
        CartItem.objects.filter(
            cart_id__in=legacy_cart_ids,
            product_id=product_id,
        ).values_list('cart_id', flat=True)
    )
    verified_ids.update(
        order.user_id
        for order in eligible_orders
        if order.user_id is not None and order.cart_id in matching_carts
    )
    return verified_ids


def check_is_verified_buyer(user: User | None, product: Product | int) -> bool:
    if not user or not user.is_authenticated:
        return False
    prod_id = product.pk if hasattr(product, 'pk') else int(product)
    return user.pk in verified_buyer_ids(prod_id, {user.pk})


class ReviewsView(APIView):
    permission_classes = [IsCustomer]
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        if self.request.method == "DELETE":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(parameters=[ListingQuerySerializer], responses=ReviewSerializer(many=True), auth=[])
    def get(self, request: Request, pk: int) -> Response:
        product = get_object_or_404(catalog(), pk=pk)
        records = Review.objects.filter(product=product).select_related('user').order_by('-created', '-pk')
        paginated = request.query_params.get('paginated') == '1'
        own_review = records.filter(user=request.user).first() if request.user.is_authenticated else None
        count, page = record_page(records, request.query_params) if paginated else (0, records[:50])
        reviews = list(page)
        verification_rows = reviews + ([own_review] if own_review else [])
        context = {
            'request': request,
            'verified_buyer_ids': verified_buyer_ids(
                product.pk,
                {review.user_id for review in verification_rows},
            ),
        }
        context['verified_buyer_ids'].update(
            review.user_id
            for review in verification_rows
            if review.user.is_staff or review.user.is_superuser
        )
        results = ReviewSerializer(reviews, many=True, context=context).data
        if paginated:
            return Response({
                'count': count,
                'results': results,
                'own_review': ReviewSerializer(own_review, context=context).data if own_review else None,
            })
        return Response(results)

    @extend_schema(request=ReviewSerializer, responses={201: ReviewSerializer, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request, pk):
        product = get_object_or_404(catalog(), pk=pk)
        Product.objects.select_for_update().get(pk=product.pk)
        
        # Verify user is a verified buyer
        if not check_is_verified_buyer(request.user, product):
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

    @extend_schema(
        parameters=[OpenApiParameter(
            'review_id', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False,
            description='Positive review ID for moderation; omit to remove your own review.',
        )],
        responses={204: None, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT},
    )
    @transaction.atomic
    def delete(self, request: Request, pk: int) -> Response:
        product = get_object_or_404(catalog(), pk=pk)
        Product.objects.select_for_update().get(pk=product.pk)
        review_id = request.query_params.get('review_id')
        if review_id is not None:
            review_id = serializers.IntegerField(min_value=1).run_validation(review_id)
            review = get_object_or_404(Review, product=product, pk=review_id)
            is_moderator = (
                request.user.is_staff
                or request.user.is_superuser
                or getattr(request.user, 'is_business_admin', False)
                or (
                    review.product.store is not None
                    and review.product.store.user_id == request.user.id
                )
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


def cart_data(cart: Cart, request: Request) -> dict[str, Any]:
    from product.policies import selected_variant

    items = cart.cart_items.select_related('product__store').prefetch_related('product__images', 'product__tags')
    quantities: dict[int, int] = {}
    for item in items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    rows: list[dict[str, Any]] = []
    for item in items:
        product = item.product
        valid_option = True
        option = None
        try:
            option = selected_variant(product, item.variant)
            price = unit_price(product, item.variant)
        except ValidationError:
            # A seller can retire an option while it is in a shopper's cart.
            # Keep the cart readable/removable; checkout still rejects the option.
            valid_option = False
            # Catalog pricing remains readable even if a later price edit rounds
            # below a payable cent. This row is unavailable, never a free item.
            price = max(Decimal(product.sale_price), Decimal('0.00'))
        available = min(product.available, option.get('available', product.available)) if option else product.available
        data = CartProductSerializer(
            product, context={'request': request, 'cart_unit_price': price},
        ).data
        data['selected_variant'] = item.variant
        data['sale_price'] = str(price)
        data['available'] = available if valid_option else 0
        if item.variant:
            data['title'] += f' ({item.variant})'
        rows.append(
            {
                "product": data,
                "quantity": item.quantity,
                "total": str(price * item.quantity),
                "purchasable": valid_option
                and product.product_type != Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK
                and not is_own_store(product, request.user)
                and product.visibility
                and not product.is_upcoming_drop
                and not product.is_blocked
                and product.store.status == Store.STATUS_ACTIVE
                and product.store.verified_at is not None
                and (
                    item.quantity == 1
                    if product.is_digital
                    else (
                        item.quantity <= available
                        and quantities[product.pk] <= product.available
                    )
                ),
            }
        )
    subtotal = sum((Decimal(row['total']) for row in rows), Decimal('0'))
    has_physical_items = any(not row['product']['is_digital'] for row in rows)
    shipping = None if has_physical_items else Decimal('0.00')
    total = subtotal + (shipping or Decimal('0.00'))
    return {
        'id': cart.pk,
        'updated': cart.updated.isoformat(),
        'items': rows,
        'subtotal': str(subtotal),
        'shipping': str(shipping) if shipping is not None else None,
        'total': str(total),
    }


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
        variant_name = serializers.CharField(max_length=80, allow_blank=True).run_validation(request.data.get('variant', request.query_params.get('variant', '')))
        if request.method == 'DELETE':
            cart.cart_items.filter(product_id=pk, variant=variant_name).delete()
        else:
            quantity = serializers.IntegerField(min_value=1, max_value=1000).run_validation(request.data.get('quantity', 1))
            product = get_object_or_404(catalog(), pk=pk)
            from product.policies import check_drop_bot_protection
            check_drop_bot_protection(product, request)
            validate_purchase(product, request.user)
            if product.is_digital:
                quantity = 1
            item = cart.cart_items.filter(product=product, variant=variant_name).first()
            if request.method == 'POST' and item and not product.is_digital:
                quantity += item.quantity
            from product.policies import selected_variant
            option = selected_variant(product, variant_name)
            unit_price(product, variant_name)
            if option and not product.is_digital and quantity > option.get('available', product.available):
                raise ValidationError({'variant': 'Insufficient stock for the selected option.'})
            other_quantity = sum(row.quantity for row in cart.cart_items.filter(product=product).exclude(variant=variant_name))
            if not product.is_digital and quantity + other_quantity > product.available:
                raise ValidationError({'detail': f'Only {product.available} units of {product.title} are available.'})
            if item:
                item.quantity = quantity
                item.save(update_fields=['quantity', 'updated'])
            else:
                CartItem.objects.create(cart=cart, product=product, quantity=quantity, variant=variant_name)
        from cart.cache import invalidate_cart_cache
        cart.save(update_fields=['updated'])
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


def _iso(val):
    return val.isoformat() if val and hasattr(val, 'isoformat') else (str(val) if val else None)


def load_order_relations(orders: QuerySet[Order]) -> QuerySet[Order]:
    """Batch private order data for the selected page, without response caching."""
    return orders.select_related('user').prefetch_related(
        Prefetch(
            'fulfillments',
            queryset=OrderFulfillment.objects.select_related('store'),
            to_attr='loaded_fulfillments',
        ),
        Prefetch(
            'refund_set', queryset=Refund.objects.order_by('pk'),
            to_attr='loaded_refunds',
        ),
    )


def order_data(order: Order) -> dict[str, Any]:
    refunds = getattr(order, 'loaded_refunds', None)
    if refunds is None:
        refunds = list(order.refund_set.order_by('pk'))
    refund = next((row for row in refunds if row.status == Refund.STATUS_PENDING), None)
    if refund is None:
        refund = max(refunds, key=lambda row: (row.created, row.pk), default=None)
    fulfillments = getattr(order, 'loaded_fulfillments', None)
    if fulfillments is None:
        fulfillments = list(order.fulfillments.select_related('store'))
    items = []
    for source in (order.items_snapshot or []):
        item = dict(source)
        if item.get('is_digital') and item.get('product'):
            item['download_url'] = f"/api/orders/{order.pk}/downloads/{item['product']}"
            if item.get('variant'):
                item['download_url'] += '?' + urlencode({'variant': item['variant']})
        items.append(item)
    return {
        'id': order.pk,
        'reference': order.orderId,
        'status': order.status,
        'created': _iso(order.created),
        'updated': _iso(order.updated),
        'ordered_date': _iso(getattr(order, 'ordered_date', None)),
        'status_updated_at': _iso(getattr(order, 'status_updated_at', None)),
        'cancelled_at': _iso(getattr(order, 'cancelled_at', None)),
        'refunded_at': _iso(getattr(order, 'refunded_at', None)),
        'total': str(order.total),
        'paid_total': str(order.paid_total),
        'refunded_total': str(order.refunded_total),
        'subtotal': str(order.subtotal),
        'payment_type': order.payment_type,
        'carrier': getattr(order, 'carrier', 'USPS') or 'USPS',
        'tracking_number': getattr(order, 'tracking_number', '') or '',
        'tracking_url': getattr(order, 'tracking_url', '') or '',
        'shipped_at': _iso(getattr(order, 'shipped_at', None)),
        'delivered_at': _iso(getattr(order, 'delivered_at', None)),
        'tracking_events': getattr(order, 'tracking_events', []) or [],
        'fulfillments': [
            {
                'store': fulfillment.store_id,
                'store_name': fulfillment.store.name,
                'status': fulfillment.status,
                'carrier': fulfillment.carrier,
                'tracking_number': fulfillment.tracking_number,
                'shipped_at': _iso(fulfillment.shipped_at),
                'delivered_at': _iso(fulfillment.delivered_at),
            }
            for fulfillment in fulfillments
        ],
        'shipping': order.shipping_snapshot,
        'tax': str(order.tax),
        'tax_snapshot': getattr(order, 'tax_snapshot', {}) or {},
        'items': items,
        'address': order.address_snapshot,
        'buyer_email': getattr(order, 'buyer_email', '') or (order.user.email if order.user else ''),
        'buyer_phone': getattr(order, 'buyer_phone', '') or (str(getattr(order.user, 'phone1', '')) if order.user else ''),
        'active_refund': (
            {
                'id': refund.pk,
                'status': refund.status,
                'is_pending': refund.status == Refund.STATUS_PENDING,
                'is_editable': refund.status == Refund.STATUS_PENDING and not refund.provider_reference,
                'reason': refund.reason,
                'refund_type': refund.refund_type,
                'refund_amount': str(refund.refund_amount),
                'product_ids': [
                    item.get('product')
                    for item in (refund.selected_items or [])
                    if item.get('product')
                ],
                'failure_reason': refund_failure_reason(refund),
                'processing_reason': refund.processing_reason,
                'created': _iso(refund.created),
                'updated': _iso(refund.updated),
            }
            if refund is not None
            else None
        ),
        'claimed_product_ids': sorted(list({
            item.get('product')
            for ref in refunds
            if ref.status in [
                Refund.STATUS_PENDING,
                Refund.STATUS_APPROVED,
                Refund.STATUS_DECLINED,
                Refund.STATUS_FAILED,
            ]
            for item in (ref.selected_items or order.items_snapshot or [])
            if item.get('product')
        })),
    }


class OrdersView(APIView):
    permission_classes = [IsCustomer]
    @extend_schema(parameters=[ListingQuerySerializer], responses=OrderSerializer(many=True))
    def get(self, request: Request) -> Response:
        orders = filter_records(
            Order.objects.filter(user=request.user).order_by('-created', '-pk'), request.query_params,
            search_fields=("orderId", "tracking_number", "carrier", "cart__cart_items__product__title"),
            json_search_fields=('items_snapshot',),
            fields={"status": "status", "payment_type": "payment_type"}, amount_field="total",
        )
        orders = load_order_relations(orders)
        count, page = record_page(orders, request.query_params)
        if request.query_params.get("paginated") == "1":
            return Response({"count": count, "results": [order_data(order) for order in page]})
        return Response([order_data(order) for order in orders[:100]])


class OrderDetailView(APIView):
    @staticmethod
    def _needs_digital_delivery(order: Order) -> bool:
        return bool(
            order.status in ('confirmed', 'shipped')
            and order.ordered
            and order.paid_total >= order.total
            and order.items_snapshot
            and all(row.get('is_digital') for row in order.items_snapshot)
        )

    @extend_schema(responses={200: OrderSerializer, 404: OpenApiTypes.OBJECT})
    def get(self, request: Request, pk: int) -> Response:
        if request.user.is_staff or request.user.is_superuser or request.user.is_business_admin:
            orders = Order.objects.all().order_by('-created')
        else:
            orders = Order.objects.filter(user=request.user).order_by('-created')
        order = load_order_relations(orders).filter(pk=pk).first()
        if order is None:
            return Response(
                {"detail": "This order isn’t available to your account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if self._needs_digital_delivery(order):
            with transaction.atomic():
                order = get_object_or_404(
                    load_order_relations(orders.select_for_update(of=('self',))),
                    pk=order.pk,
                )
                if self._needs_digital_delivery(order):
                    now = timezone.now()
                    order.status = 'delivered'
                    order.delivered_at = order.delivered_at or order.created or now
                    order.shipped_at = None
                    order.status_updated_at = now
                    events = list(order.tracking_events or [])
                    if not any(event.get('status') == 'delivered' for event in events):
                        events.append({
                            'status': 'delivered',
                            'description': 'Instant digital fulfillment completed.',
                            'timestamp': now.isoformat(),
                        })
                    order.tracking_events = events
                    order.save(update_fields=[
                        'status', 'delivered_at', 'shipped_at', 'status_updated_at',
                        'tracking_events', 'updated',
                    ])
        return Response(order_data(order))


class DigitalDownloadView(APIView):
    """Stream purchased files without exposing object-storage URLs."""
    def get(self, request: Request, pk: int, product_pk: int) -> FileResponse | Response:
        orders = (
            Order.objects.all()
            if (
                request.user.is_staff
                or request.user.is_superuser
                or request.user.is_business_admin
            )
            else Order.objects.filter(user=request.user)
        )
        order = get_object_or_404(orders, pk=pk)
        if order.status in ["cancelled", "refunded"]:
            return Response(
                {
                    "detail": f"Download access is revoked because this order was {order.status}."
                },
                status=404,
            )
        if (
            not order.ordered
            or order.status not in ["confirmed", "shipped", "delivered", "picked up"]
            or order.paid_total < order.total
        ):
            raise Http404

        matches = [
            row for row in (order.items_snapshot or [])
            if row.get("product") == product_pk and row.get("is_digital")
        ]
        if 'variant' in request.query_params:
            variant = serializers.CharField(
                max_length=80, allow_blank=True, trim_whitespace=False
            ).run_validation(
                request.query_params['variant']
            )
            matches = [row for row in matches if str(row.get('variant') or '') == variant]
        elif len(matches) > 1:
            matches = [row for row in matches if not row.get('variant')]
        item = matches[0] if len(matches) == 1 else None
        if not item:
            raise Http404
        try:
            return self._stream_asset(item, product_pk)
        except Exception:
            logger.exception('Purchased digital asset retrieval failed for order %s', order.pk)
            return Response(
                {'detail': 'Your download is temporarily unavailable. Please try again shortly.'},
                status=503,
            )

    def _stream_asset(self, item: dict[str, Any], product_pk: int) -> FileResponse | Response:
        product = Product.objects.filter(pk=product_pk).first()
        from django.core.files.storage import default_storage
        from urllib.parse import urlparse

        candidates = []
        item_download = (item.get("download_url") or "").strip()
        if item_download and not item_download.startswith("/api/"):
            candidates.append(item_download)
        prod_download = (product.digital_file_url or "").strip() if product and product.is_digital else ''
        # Only legacy purchases without a recorded asset may use the current file.
        # A missing paid edition/variant must never silently become another file.
        if prod_download and not item_download and not item.get('variant'):
            candidates.append(prod_download)

        bucket = getattr(settings, "MINIO_BUCKET_NAME", "commerce-images")
        known_prefixes = (
            f"{bucket}/media/",
            f"{bucket}/",
            "commerce-images/media/",
            "commerce-images/",
            "commerce-media/media/",
            "commerce-media/",
            "media/",
        )

        resolved_path = None
        for raw in candidates:
            path = urlparse(raw).path.lstrip("/")
            for prefix in known_prefixes:
                if path.startswith(prefix):
                    path = path[len(prefix):]
                    break

            variants = [path]
            if path.startswith("media/"):
                variants.append(path[len("media/"):])
            else:
                variants.append(f"media/{path}")

            for candidate in variants:
                if candidate and default_storage.exists(candidate):
                    resolved_path = candidate
                    break
            if resolved_path:
                break

        if not resolved_path:
            external = next((raw for raw in candidates if raw.startswith(('https://', 'http://'))), None)
            if external:
                from types import SimpleNamespace
                from staff.digital_assets import stream_digital_asset

                return stream_digital_asset(SimpleNamespace(pk=product_pk, digital_file_url=external))
            return Response(
                {
                    "detail": "The digital asset is unavailable. Contact support for a replacement."
                },
                status=404,
            )
        response = FileResponse(
            default_storage.open(resolved_path, "rb"),
            as_attachment=True,
            filename=resolved_path.rsplit("/", 1)[-1],
        )
        response["Cache-Control"] = "private, no-store"
        return response


class OrderTrackingView(APIView):
    @extend_schema(responses={200: OrderTrackingSerializer}, description="Get recorded order and store-scoped fulfillment milestones with official carrier tracking links.")
    def get(self, request: Request, pk: int) -> Response:
        if request.user.is_staff or request.user.is_superuser or request.user.is_business_admin:
            orders = Order.objects.all()
        else:
            orders = Order.objects.filter(user=request.user)
        order = get_object_or_404(orders, pk=pk)
        from payment.usps import track_usps_shipment
        tracking_info = track_usps_shipment(order.tracking_number) if order.carrier.upper() == 'USPS' else {'events': [], 'status': 'unknown', 'tracking_url': order.tracking_url, 'summary': 'View the carrier website for current scans.'}
        fulfillments = [
            {
                'store': fulfillment.store_id,
                'store_name': fulfillment.store.name,
                'status': fulfillment.status,
                'carrier': fulfillment.carrier,
                'tracking_number': fulfillment.tracking_number,
                'shipped_at': fulfillment.shipped_at,
                'delivered_at': fulfillment.delivered_at,
            }
            for fulfillment in order.fulfillments.select_related('store').all()
        ]
        return Response({
            'order_id': order.pk,
            'reference': order.orderId,
            'status': order.status,
            'carrier': order.carrier or '',
            'tracking_number': order.tracking_number or '',
            'tracking_url': order.tracking_url or '',
            'shipped_at': order.shipped_at,
            'delivered_at': order.delivered_at,
            'tracking_events': order.tracking_events or [],
            'fulfillments': fulfillments,
            'live_tracking': tracking_info,
        })


class UserWalletView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(
        parameters=[ListingQuerySerializer],
        responses={200: OpenApiTypes.OBJECT},
        description="Get current user's wallet balance and transactions.",
    )
    def get(self, request: Request) -> Response:
        wallet = get_or_create_user_wallet(request.user)
        transactions = filter_records(
            wallet.transactions.order_by("-created", "-pk"), request.query_params,
            search_fields=("description", "reference", "source"),
            fields={"transaction_type": "transaction_type", "source": "source"}, amount_field="amount",
        )
        count, transactions = record_page(transactions, request.query_params)
        return Response(
            {
                "balance": format(wallet.balance, ".2f"),
                "count": count,
                "transactions": UserWalletTransactionSerializer(
                    transactions, many=True
                ).data,
            }
        )


class WalletTopupSessionView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(request=WalletTopupRequestSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        from payment.funding import create_funding_session

        if stripe is None or not getattr(settings, "STRIPE_SECRET", ""):
            raise ValidationError({"detail": "Wallet funding is not configured."})
        if getattr(settings, "STRIPE_CURRENCY", "usd").lower() != "usd":
            raise ValidationError({"detail": "Wallet funding requires USD payments."})
        serializer = WalletTopupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = create_funding_session(
            request.user, serializer.validated_data["amount"]
        )
        return Response({"url": session.url, "id": session.id})


class WalletTopupConfirmView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(
        request=PaymentSessionRequestSerializer, responses=OpenApiTypes.OBJECT
    )
    def post(self, request: Request) -> Response:
        from payment.funding import confirm_funding

        serializer = PaymentSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_id = serializer.validated_data["session_id"]
        if stripe is None or not getattr(settings, "STRIPE_SECRET", ""):
            raise ValidationError({"detail": "Wallet funding is not configured."})
        stripe.api_key = settings.STRIPE_SECRET
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception:
            raise ValidationError({"detail": "Unable to verify wallet top-up."})
        attempt = confirm_funding(request.user, session_id, session)
        if attempt.status != "credited":
            raise ValidationError(
                {
                    "detail": "Payment exceeds the funding allowance or is invalid. A refund is initiated or pending recovery."
                }
            )
        wallet = get_or_create_user_wallet(request.user)
        return Response(
            {"detail": "Wallet funded successfully.", "balance": str(wallet.balance)}
        )


class OrderRefundView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        description="Retrieve active refund request details for an order.",
    )
    def get(self, request: Request, pk: int) -> Response:
        order = get_object_or_404(Order.objects.filter(user=request.user), pk=pk)
        refund = Refund.objects.filter(order=order).order_by("-created").first()
        if not refund:
            return Response(
                {"detail": "No refund request found for this order.", "refund": None},
                status=404,
            )
        reason_code = "other"
        for code, label in [
            ("item_damaged", "Item damaged"),
            ("wrong_item_received", "Wrong item received"),
            ("item_missing", "Item missing"),
        ]:
            if refund.reason == label:
                reason_code = code
                break
        other_reason = refund.reason if reason_code == "other" else ""
        return Response({
            "id": refund.pk,
            "order": order.pk,
            "status": refund.status,
            "is_pending": refund.status == Refund.STATUS_PENDING,
            "is_editable": refund.status == Refund.STATUS_PENDING and not refund.provider_reference,
            "reason": reason_code,
            "other_reason": other_reason,
            "reason_display": refund.reason,
            "refund_type": refund.refund_type,
            "refund_type_display": refund.get_refund_type_display(),
            "refund_amount": format(refund.refund_amount, ".2f"),
            "product_ids": [
                item.get("product")
                for item in (refund.selected_items or [])
                if item.get("product")
            ],
            "failure_reason": refund_failure_reason(refund),
            "processing_reason": refund.processing_reason,
            "created": _iso(refund.created),
            "updated": _iso(refund.updated),
        })

    @extend_schema(
        request=RefundRequestSerializer,
        responses={
            201: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Request a refund for an order within the 7-day return window.",
    )
    @transaction.atomic
    def post(self, request: Request, pk: int) -> Response:
        orders = Order.objects.select_for_update().filter(user=request.user)
        order = get_object_or_404(orders, pk=pk)

        if order.status in ("refunded", "cancelled"):
            raise ValidationError({"detail": "This order can no longer be refunded."})

        if order.paid_total <= 0 or (order.paid_total - order.refunded_total) <= Decimal("0.00"):
            raise ValidationError(
                {"detail": "This order has no remaining refundable payment."}
            )

        if Refund.objects.filter(order=order, status=Refund.STATUS_PENDING).exists():
            raise ValidationError(
                {
                    "detail": "A refund request is already pending review for this order. You can edit your existing request."
                }
            )

        snapshots = order_paid_lines(order)
        is_all_digital = bool(snapshots) and all(
            item.get("is_digital", False) for item in snapshots
        )
        if is_all_digital:
            raise ValidationError(
                {
                    "detail": "Digital products (e-books, software downloads) are non-refundable once delivered. "
                    "If you are experiencing a technical issue with your file, please contact customer support at support@proace.com."
                }
            )

        if not request.data.get("reason"):
            raise ValidationError({"reason": "A reason is required to request a refund."})
        if not request.data.get("product_ids"):
            raise ValidationError({"product_ids": "Select at least one product to refund."})

        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason_code = serializer.validated_data["reason"]
        reason_labels = {
            "item_damaged": "Item damaged",
            "wrong_item_received": "Wrong item received",
            "item_missing": "Item missing",
            "other": serializer.validated_data.get("other_reason", "").strip(),
        }
        reason = reason_labels[reason_code]
        refund_type = serializer.validated_data.get("refund_type", "store_credit")
        selected_ids = set(serializer.validated_data["product_ids"])
        selected = [item for item in snapshots if item.get("product") in selected_ids]
        if len({item.get("product") for item in selected}) != len(selected_ids):
            raise ValidationError(
                {"product_ids": "Choose products from this order only."}
            )
        if any(item.get("is_digital", False) for item in selected):
            raise ValidationError(
                {
                    "product_ids": "Digital products are non-refundable. If you are experiencing issues, please contact support via email."
                }
            )
        from payment.services import validate_return_window

        validate_return_window(order, selected)
        claimed = set()
        for previous in Refund.objects.filter(
            order=order,
            status__in=[
                Refund.STATUS_PENDING,
                Refund.STATUS_APPROVED,
                Refund.STATUS_DECLINED,
                Refund.STATUS_FAILED,
            ],
        ):
            claimed.update(
                item.get("product") for item in (previous.selected_items or snapshots)
            )
        if selected_ids & claimed:
            raise ValidationError(
                {
                    "product_ids": "A refund has already been requested, processed, or declined for one or more selected products."
                }
            )
        refund_amount = sum(
            (Decimal(str(item["line_total"])) for item in selected), Decimal("0")
        ).quantize(Decimal(".01"))

        if (
            refund_amount <= 0
            or refund_amount > order.paid_total - order.refunded_total
        ):
            raise ValidationError(
                {
                    "detail": "The selected items exceed the remaining refundable payment."
                }
            )

        refund = Refund.objects.create(
            email=request.user.email,
            order=order,
            reason=reason,
            refund_type=refund_type,
            selected_items=selected,
            refund_amount=refund_amount,
            accepted=False,
        )

        send_mail(
            "refund-request-acknowledged",
            request.user.email,
            {
                "firstname": request.user.first_name,
                "orderId": order.orderId,
                "refund_amount": format(refund_amount, ".2f"),
                "refund_type": refund.get_refund_type_display(),
                "reason": reason,
                "subject": f"Refund Request Received for Order #{order.orderId}",
            },
        )

        from notification.domain import refund_notice
        refund_notice(refund, request.user, selected, updated=False)

        return Response(
            {
                "detail": "Your refund request has been received. Physical returns are reviewed and processed within 1–2 business days.",
                "status": order.status,
                "refund_id": refund.pk,
                "refund_type": refund_type,
                "refund_amount": format(refund_amount, ".2f"),
            },
            status=201,
        )

    @extend_schema(
        request=RefundRequestSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        description="Edit an existing pending refund request for an order.",
    )
    @transaction.atomic
    def patch(self, request: Request, pk: int) -> Response:
        order = get_object_or_404(
            Order.objects.select_for_update().filter(user=request.user), pk=pk
        )
        if order.status in ("refunded", "cancelled"):
            raise ValidationError({"detail": "This order can no longer be refunded."})

        refund = (
            Refund.objects.select_for_update()
            .filter(order=order, status=Refund.STATUS_PENDING)
            .first()
        )
        if not refund:
            raise ValidationError(
                {
                    "detail": "There is no pending refund request to edit for this order. Only pending requests can be modified."
                }
            )

        if refund.provider_reference:
            raise ValidationError({
                "detail": "This refund is already processing with the payment provider and can no longer be edited."
            })

        serializer = RefundRequestSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        snapshots = order_paid_lines(order)
        if "reason" in serializer.validated_data:
            reason_code = serializer.validated_data["reason"]
            reason_labels = {
                "item_damaged": "Item damaged",
                "wrong_item_received": "Wrong item received",
                "item_missing": "Item missing",
                "other": serializer.validated_data.get(
                    "other_reason", refund.reason if reason_code == "other" else ""
                ).strip(),
            }
            refund.reason = reason_labels[reason_code]
        elif (
            "other_reason" in serializer.validated_data
            and serializer.validated_data["other_reason"].strip()
        ):
            refund.reason = serializer.validated_data["other_reason"].strip()

        if "refund_type" in serializer.validated_data:
            refund.refund_type = serializer.validated_data["refund_type"]

        if "product_ids" in serializer.validated_data:
            selected_ids = set(serializer.validated_data["product_ids"])
            selected = [item for item in snapshots if item.get("product") in selected_ids]
            if len({item.get("product") for item in selected}) != len(selected_ids):
                raise ValidationError({"product_ids": "Choose products from this order only."})
            if any(item.get("is_digital", False) for item in selected):
                raise ValidationError({
                    "product_ids": "Digital products are non-refundable. If you are experiencing issues, please contact support via email."
                })
            claimed = set()
            for previous in Refund.objects.filter(
                order=order,
                status__in=[
                    Refund.STATUS_PENDING,
                    Refund.STATUS_APPROVED,
                    Refund.STATUS_DECLINED,
                    Refund.STATUS_FAILED,
                ],
            ).exclude(pk=refund.pk):
                claimed.update(
                    item.get("product") for item in (previous.selected_items or snapshots)
                )
            if selected_ids & claimed:
                raise ValidationError({
                    "product_ids": "A refund has already been requested, processed, or declined for one or more selected products."
                })
            new_amount = sum(
                (Decimal(str(item["line_total"])) for item in selected), Decimal("0")
            ).quantize(Decimal(".01"))
            if new_amount <= 0 or new_amount > (order.paid_total - order.refunded_total):
                raise ValidationError({
                    "detail": "The selected items exceed the remaining refundable payment."
                })
            refund.selected_items = selected
            refund.refund_amount = new_amount

        from payment.services import validate_return_window

        validate_return_window(order, refund.selected_items or snapshots)
        refund.save(update_fields=["reason", "refund_type", "selected_items", "refund_amount", "updated"])

        from notification.domain import refund_notice
        refund_notice(refund, request.user, refund.selected_items, updated=True)

        return Response(
            {
                "detail": "Your refund request has been updated. Physical returns are reviewed and processed within 1–2 business days.",
                "status": refund.status,
                "refund_id": refund.pk,
                "refund_type": refund.refund_type,
                "refund_amount": format(refund.refund_amount, ".2f"),
            },
            status=200,
        )

    def put(self, request: Request, pk: int) -> Response:
        return self.patch(request, pk)


class OrderCancelView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Cancel a pending or confirmed order before fulfillment, restoring stock and reversing settled wallet/card payments.",
    )
    @transaction.atomic
    def post(self, request: Request, pk: int) -> Response:
        order = get_object_or_404(
            Order.objects.select_for_update(), user=request.user, pk=pk
        )
        has_physical = any(
            not item.get("is_digital", False) for item in (order.items_snapshot or [])
        )
        if not has_physical:
            raise ValidationError(
                {
                    "detail": "Digital orders are fulfilled immediately upon purchase and cannot be cancelled or refunded."
                }
            )
        has_digital = any(
            item.get("is_digital", False) for item in (order.items_snapshot or [])
        )
        if has_digital:
            raise ValidationError(
                {
                    "detail": "Orders containing instant digital products cannot be cancelled once access is delivered."
                }
            )
        cancellation_window_hours = getattr(settings, "CANCELLATION_WINDOW_HOURS", 12)
        from datetime import timedelta

        if timezone.now() > order.created + timedelta(hours=cancellation_window_hours):
            raise ValidationError(
                {
                    "detail": f"Orders can only be cancelled within {cancellation_window_hours} hours of placement."
                }
            )
        if order.status not in {"pending", "confirmed"}:
            raise ValidationError(
                {
                    "detail": "Only unfulfilled pending or confirmed orders can be cancelled."
                }
            )
        if order.fulfillments.exclude(status="confirmed").exists():
            raise ValidationError(
                {"detail": "Part of this order has already been fulfilled."}
            )
        order = execute_order_status_transition(
            order, "cancelled", request.user, "Customer cancelled before fulfillment."
        )
        return Response(
            {
                "detail": "Order cancelled and settled payments reversed.",
                "order": order_data(order),
            }
        )


class CouponValidateView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT})
    def post(self, request):
        code = str(request.data.get("code", "")).strip()
        if not code:
            raise ValidationError({"detail": "Enter a coupon code."})

        coupon = Coupon.objects.filter(
            code__iexact=code,
            active=True,
            valid_from__lte=timezone.now(),
            valid_to__gte=timezone.now(),
        ).first()

        if not coupon:
            raise ValidationError(
                {"detail": "This coupon code is invalid or has expired."}
            )

        if coupon.num_available and coupon.num_used >= coupon.num_available:
            raise ValidationError(
                {"detail": "This coupon has reached its maximum usage limit."}
            )

        cart = active_cart(request.user)
        items = list(cart.cart_items.select_related("product").all())
        if not items:
            raise ValidationError(
                {"detail": "Add items to your bag before applying a coupon."}
            )

        coupon_lines = []
        subtotal = Decimal("0")
        for item in items:
            price = unit_price(item.product, item.variant)
            subtotal += price * item.quantity
            coupon_lines.append(
                {
                    "product": item.product,
                    "quantity": item.quantity,
                    "unit_price": price,
                }
            )

        try:
            discount = calculate_coupon_discount(
                coupon, request.user, coupon_lines, subtotal, reserve=False
            )
        except ValidationError as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                first_msg = next(iter(detail.values()), "This coupon cannot be applied.")
                if isinstance(first_msg, (list, tuple)) and first_msg:
                    first_msg = first_msg[0]
                error_text = str(first_msg)
            elif isinstance(detail, (list, tuple)) and detail:
                error_text = str(detail[0])
            else:
                error_text = str(detail)
            raise ValidationError({"detail": error_text})
        except Exception:
            raise ValidationError({"detail": "This coupon cannot be applied to your cart."})

        return Response(
            {
                "code": coupon.code,
                "discount": coupon.discount,
                "discount_amount": format(discount, ".2f"),
                "valid": True,
                "message": f"Coupon {coupon.code.upper()} applied! Saved ${discount:.2f}",
            }
        )


class ShippingRatesView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "address",
                OpenApiTypes.INT,
                OpenApiParameter.QUERY,
                required=True,
                description="Owned delivery address ID",
            ),
            OpenApiParameter(
                "coupon",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                description="Coupon used to preview discounted destination tax",
            ),
            OpenApiParameter(
                "carrier",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                enum=["USPS", "UPS", "FEDEX", "DHL"],
            ),
        ],
        responses={200: ShippingRateSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        cart = active_cart(request.user)
        items = list(cart.cart_items.select_related("product__store").all())
        if not items:
            return Response([])

        has_physical_items = any(not item.product.is_digital for item in items)
        cart, snapshots, coupon_lines, subtotal = CheckoutView()._lines(request)
        code = str(request.query_params.get("coupon", "")).strip()
        coupon = None
        discount = Decimal("0")
        if code:
            coupon = Coupon.objects.filter(code__iexact=code).first()
            discount = calculate_coupon_discount(
                coupon, request.user, coupon_lines, subtotal, reserve=False
            )
        snapshots = allocate_checkout_lines(snapshots, coupon_lines, coupon, discount)
        taxable_subtotal = subtotal - discount

        if not has_physical_items:
            tax_breakdown = calculate_tax(
                snapshots, taxable_subtotal, Decimal("0.00"), None
            )
            tax = str(tax_breakdown.amount)
            digital_rate = {
                "carrier": "DIGITAL",
                "service_id": "digital_delivery",
                "service_name": "Instant Digital Delivery",
                "name": "Instant Digital Delivery",
                "rate": "0.00",
                "amount": "0.00",
                "delivery_days": 0,
                "estimated_delivery": "Immediate access upon confirmation",
                "description": "Worldwide digital delivery",
                "tax": tax,
                "tax_rate": str(tax_breakdown.rate),
                "tax_jurisdiction": tax_breakdown.jurisdiction,
                "is_default": True,
            }
            digital_rate["quote_token"] = issue_quote(
                digital_rate, request.user, cart, None
            )
            return Response([digital_rate])

        total_weight = sum(
            Decimal(str(item.product.weight or "1.00")) * item.quantity
            for item in items
            if not item.product.is_digital
        )

        address_id = request.query_params.get("address")
        if address_id:
            try:
                addr = Address.objects.get(
                    pk=serializers.IntegerField(min_value=1).run_validation(address_id),
                    user=request.user,
                    is_deleted=False,
                )
                if has_physical_items:
                    country = "".join(c for c in addr.country.lower() if c.isalnum())
                    us_names = {"us", "usa", "unitedstates", "unitedstatesofamerica"}
                    if country not in us_names:
                        raise ValidationError(
                            {
                                "address": "Physical products are currently delivered only within the United States. "
                                "Digital products remain available worldwide."
                            }
                        )
            except Address.DoesNotExist:
                raise ValidationError({"address": "Address not found."})

        carrier = str(request.query_params.get("carrier", "USPS")).upper()
        if carrier not in CARRIERS:
            raise ValidationError({"carrier": "Choose USPS, UPS, FEDEX, or DHL."})
        if not address_id:
            raise ValidationError(
                {"address": "Select a delivery address to issue shipping quotes."}
            )
        rates = cart_rates(carrier, cart, addr)
        for rate in rates:
            shipping_amount = Decimal(rate["amount"])
            tax_breakdown = calculate_tax(
                snapshots, taxable_subtotal, shipping_amount, addr
            )
            rate["tax"] = str(tax_breakdown.amount)
            rate["tax_rate"] = str(tax_breakdown.rate)
            rate["tax_jurisdiction"] = tax_breakdown.jurisdiction
            rate["quote_token"] = issue_quote(rate, request.user, cart, addr)
        return Response(rates)


class CheckoutView(APIView):
    permission_classes = [IsCustomer]

    @staticmethod
    def _validate_service_area(
        address: Address | None, snapshots: list[dict[str, Any]]
    ) -> None:
        if not any(not row["is_digital"] for row in snapshots):
            return
        if not address:
            raise ValidationError(
                {"address": "A delivery address is required for physical items."}
            )
        from payment.geo import validate_military_address

        validate_military_address(
            address.city, address.state, address.zip, address.country
        )
        country = "".join(
            character for character in address.country.lower() if character.isalnum()
        )
        us_names = {"us", "usa", "unitedstates", "unitedstatesofamerica"}
        if country not in us_names:
            raise ValidationError(
                {
                    "address": "Physical products are currently delivered only within the United States. "
                    "Digital products remain available worldwide.",
                }
            )

    def _lines(
        self, request: Any, lock: bool = False
    ) -> tuple[Cart, list[dict[str, Any]], list[dict[str, Any]], Decimal]:
        user = getattr(request, "user", request)
        cart = active_cart(user)
        items = list(cart.cart_items.order_by("product_id"))
        if not items:
            raise ValidationError({"detail": "Your cart is empty."})
        quantities: dict[int, int] = {}
        variant_quantities: dict[tuple[int, str], int] = {}
        for item in items:
            quantities[item.product_id] = (
                quantities.get(item.product_id, 0) + item.quantity
            )
            variant_key = (item.product_id, item.variant)
            variant_quantities[variant_key] = (
                variant_quantities.get(variant_key, 0) + item.quantity
            )
        snapshots, coupon_lines = [], []
        for item in items:
            query = Product.objects.select_for_update() if lock else Product.objects
            product = query.get(pk=item.product_id)
            validate_purchase(product, user)
            if product.is_digital and item.quantity != 1:
                raise ValidationError({'detail': 'Digital products require one entitlement per option. Update your cart.'})
            from product.policies import selected_variant

            option = selected_variant(product, item.variant)
            if option and not product.is_digital and variant_quantities[
                (item.product_id, item.variant)
            ] > option.get("available", product.available):
                raise ValidationError(
                    {"variant": "Insufficient stock for the selected option."}
                )
            if (
                product.is_blocked
                or not product.visibility
                or product.store.status != Store.STATUS_ACTIVE
                or product.store.verified_at is None
                or (
                    not product.is_digital
                    and product.available < quantities[item.product_id]
                )
            ):
                raise ValidationError(
                    {
                        "detail": f"{product.title} is unavailable in the requested quantity."
                    }
                )
            price = unit_price(product, item.variant)
            variant_download = str(option.get('digital_file_url') or '') if option else ''
            snapshots.append(
                {
                    "product": product.pk,
                    "store": product.store_id,
                    "title": product.title,
                    "image": product.image_url,
                    "quantity": item.quantity,
                    "unit_price": str(price),
                    "is_digital": product.is_digital,
                    "variant": item.variant,
                    "digital_preview_watermark": bool(
                        getattr(product, "digital_preview_watermark", False)
                    ),
                    "download_url": variant_download or product.digital_file_url
                    if product.is_digital
                    else "",
                }
            )
            coupon_lines.append(
                {"product": product, "quantity": item.quantity, "unit_price": price}
            )
        subtotal = sum(
            (Decimal(row["unit_price"]) * row["quantity"] for row in snapshots),
            Decimal("0"),
        )
        if subtotal > Decimal("99999999.99"):
            raise ValidationError(
                {"detail": "Order value exceeds the supported maximum."}
            )
        return cart, snapshots, coupon_lines, subtotal

    def _complete(
        self,
        request: Any,
        key: UUID,
        address: Address | None,
        code: str,
        payment_type: str,
        stripe_session_id: str | None = None,
        shipping_service: str | None = None,
        shipping_quote: str | None = None,
        paid_amount: int | None = None,
        wallet_paid_amount: Decimal = Decimal("0"),
    ) -> Order:
        user = getattr(request, "user", request)
        User.objects.select_for_update().get(pk=user.pk)
        existing = Order.objects.filter(checkout_key=key).first()
        if existing:
            if existing.user_id != user.pk:
                raise ValidationError({"detail": "Invalid checkout reference."})
            return existing
        cart, snapshots, coupon_lines, subtotal = self._lines(user, lock=True)
        self._validate_service_area(address, snapshots)
        coupon = None
        discount = Decimal("0")
        if code:
            coupon = (
                Coupon.objects.select_for_update()
                .filter(
                    code__iexact=code,
                    active=True,
                    valid_from__lte=timezone.now(),
                    valid_to__gte=timezone.now(),
                )
                .first()
            )
            try:
                discount = calculate_coupon_discount(
                    coupon, user, coupon_lines, subtotal
                )
            except ValidationError as exc:
                detail = exc.detail
                if isinstance(detail, dict):
                    first_msg = next(iter(detail.values()), "This coupon cannot be applied.")
                    if isinstance(first_msg, (list, tuple)) and first_msg:
                        first_msg = first_msg[0]
                    error_text = str(first_msg)
                elif isinstance(detail, (list, tuple)) and detail:
                    error_text = str(detail[0])
                else:
                    error_text = str(detail)
                raise ValidationError({"detail": error_text})
            coupon.used()
        snapshots = allocate_checkout_lines(snapshots, coupon_lines, coupon, discount)
        for item in cart.cart_items.order_by("product_id"):
            product = Product.objects.select_for_update().get(pk=item.product_id)
            if not product.is_digital:
                product.available -= item.quantity
                if item.variant:
                    from product.policies import selected_variant

                    option = selected_variant(product, item.variant)
                    if option.get("available") is not None:
                        option["available"] -= item.quantity
            product.sales += item.quantity
            product.save(update_fields=["available", "variants", "sales", "updated"])
            transaction.on_commit(lambda product=product: invalidate_catalog(product))
        has_physical_items = any(not row["is_digital"] for row in snapshots)
        total_weight = sum(
            Decimal(str(item.product.weight or "1.00")) * item.quantity
            for item in cart.cart_items.select_related("product").all()
            if not item.product.is_digital
        )
        if not has_physical_items:
            address = None
            shipping_service = "digital_delivery"
            rate = {
                "carrier": "DIGITAL",
                "service_id": "digital_delivery",
                "amount": "0.00",
            }
        elif shipping_quote:
            rate = verify_quote(
                shipping_quote,
                user,
                cart,
                address,
                shipping_service,
                paid=paid_amount is not None,
            )
        else:
            # Backwards compatible direct API clients still receive a server-validated carrier rate.
            carrier = (
                (shipping_service or "usps_ground_advantage")
                .split("_", 1)[0]
                .upper()
            )
            rates = cart_rates(carrier, cart, address)
            rate = next(
                (row for row in rates if row["service_id"] == shipping_service),
                None,
            )
            if rate is None:
                raise ValidationError(
                    {"shipping_service": "Select an available shipping service."}
                )
        if has_physical_items:
            from payment.geo import validate_military_carrier

            validate_military_carrier(
                address, str(rate.get("carrier") or rate["service_id"].split("_", 1)[0])
            )
        shipping = Decimal(rate["amount"])
        tax_breakdown = calculate_tax(
            items=snapshots,
            subtotal=subtotal - discount,
            shipping_fee=shipping,
            address=address,
        )
        tax = tax_breakdown.amount
        line_taxes = tax_breakdown.details.get("line_taxes")
        taxes = (
            [Decimal(str(value)) for value in line_taxes]
            if isinstance(line_taxes, list) and len(line_taxes) == len(snapshots)
            else allocate_amount(
                tax - tax_breakdown.shipping_tax,
                [Decimal(row["net_total"]) for row in snapshots],
            )
        )
        snapshots = allocate_line_taxes(snapshots, taxes)
        if (
            paid_amount is not None
            and int((subtotal - discount + shipping + tax) * 100) != paid_amount
        ):
            raise ValidationError(
                {"detail": "Paid amount does not match this cart. Contact support."}
            )
        delivery_method = "home delivery" if has_physical_items else "digital"
        delivery_service = shipping_service or (
            "usps_ground_advantage" if has_physical_items else "digital_delivery"
        )
        delivery = DeliveryInfo.objects.create(
            user=user,
            address=address,
            method=delivery_method,
            delivery_type=delivery_service,
            total=shipping,
        )
        buyer_email = getattr(user, "email", "") or ""
        buyer_phone = str(getattr(user, "phone1", "") or "")
        now = timezone.now()
        is_instant_digital = not has_physical_items and payment_type != "cash_on_delivery"
        initial_status = "delivered" if is_instant_digital else "confirmed"
        order = Order(
            user=user,
            cart=cart,
            delivery=delivery,
            status=initial_status,
            delivered_at=now if is_instant_digital else None,
            status_updated_at=now if is_instant_digital else None,
            ordered=True,
            coupon_code=code,
            total=subtotal - discount + shipping + tax,
            subtotal=subtotal,
            tax=tax,
            carrier=rate.get("carrier", "DIGITAL"),
            shipping_snapshot=rate,
            buyer_email=buyer_email,
            buyer_phone=buyer_phone,
            payment_type=payment_type,
            checkout_key=key,
            stripe_session_id=stripe_session_id,
            paid_total=subtotal - discount + shipping + tax
            if payment_type != "cash_on_delivery"
            else Decimal("0"),
            wallet_paid=subtotal - discount + shipping + tax
            if payment_type == "user_wallet"
            else wallet_paid_amount,
            items_snapshot=snapshots,
            address_snapshot=AddressSerializer(address).data
            if address
            else {"country": "Worldwide", "digital": True},
            tax_snapshot=tax_breakdown.to_dict(),
            tracking_events=[
                {
                    "status": "confirmed",
                    "description": "Order confirmed and payment received.",
                    "timestamp": now.isoformat(),
                },
                {
                    "status": "delivered",
                    "description": "Instant digital fulfillment completed.",
                    "timestamp": now.isoformat(),
                },
            ] if is_instant_digital else [
                {
                    "status": "confirmed",
                    "description": "Order confirmed.",
                    "timestamp": now.isoformat(),
                }
            ],
        )
        order._notification_managed = True
        order.save()
        if payment_type == "user_wallet" and order.total > 0:
            debit_user_wallet(
                user,
                order.total,
                f"ProAce Wallet payment for Order #{order.orderId}",
                source=UserWalletTransaction.SOURCE_PURCHASE,
                reference=order.orderId,
            )
        if coupon:
            CouponRedemption.objects.filter(coupon=coupon, user=user).update(
                order=order
            )
        cart.ordered = True
        cart.save(update_fields=["ordered", "updated"])
        from cart.cache import invalidate_cart_cache
        transaction.on_commit(lambda: invalidate_cart_cache(cart))

        OrderFulfillment.objects.bulk_create(
            [
                OrderFulfillment(order=order, store_id=store_id)
                for store_id in {
                    row["store"] for row in snapshots if not row["is_digital"]
                }
            ]
        )

        # Record granular store ledger entries and update unified merchant wallet
        if order.paid_total > 0:
            record_order_earnings_for_merchant(order)

        process_referral_reward_for_order(order)

        # The buyer's HTML receipt is the only buyer email for order creation.
        order._receipt_recipient_ids = {order.user_id} if order.user_id else set()
        order._notification_managed = False
        from notification.events import order_changed
        order_changed(Order, order, created=True)

        recipient_email = str(order.buyer_email or getattr(user, "email", "") or "").strip()
        if recipient_email:
            ordered_items = [
                {
                    "title": item.get("title") or item.get("product_title") or "",
                    "variant": item.get("variant") or "",
                    "quantity": item.get("quantity"),
                    "price": str(item["unit_price"]) if item.get("unit_price") is not None else None,
                }
                for item in snapshots
            ]
            has_physical_items = any(not row.get("is_digital", False) for row in snapshots)
            address_snapshot = order.address_snapshot if has_physical_items else {}
            delivery_details = [
                {"label": label, "value": str(address_snapshot[key]).strip()}
                for key, label in (
                    ("address", "Address"),
                    ("city", "City"),
                    ("state", "State"),
                    ("zip", "ZIP code"),
                    ("country", "Country"),
                )
                if address_snapshot.get(key) and str(address_snapshot[key]).strip()
            ]
            contact_details = [
                {"label": label, "value": str(value).strip()}
                for label, value in (
                    ("Email", order.buyer_email),
                    ("Phone number", order.buyer_phone),
                )
                if value and str(value).strip()
            ]
            send_mail(
                "order-summary",
                recipient_email,
                {
                    "firstname": getattr(user, "first_name", ""),
                    "orderId": order.orderId,
                    "ordered_items": ordered_items,
                    "has_physical_items": has_physical_items,
                    "delivery_details": delivery_details,
                    "contact_details": contact_details,
                    "totals": [
                        {"label": "Subtotal", "value": str(order.subtotal)},
                        {"label": "Discount", "value": str(discount)},
                        {"label": "Shipping", "value": str(shipping)},
                        {"label": "Tax", "value": str(order.tax)},
                        {"label": "Total", "value": str(order.total)},
                    ],
                    "total": str(order.total),
                    "subject": f"ProAce Order #{order.orderId} Confirmation",
                },
            )

        return order

    @extend_schema(
        request=CheckoutRequestSerializer,
        responses={201: OrderSerializer, 200: OrderSerializer},
    )
    @transaction.atomic
    def post(self, request: Request) -> Response:
        User.objects.select_for_update().get(pk=request.user.pk)
        key = serializers.UUIDField().run_validation(request.data.get("checkout_key"))
        existing = Order.objects.filter(checkout_key=key).first()
        if existing:
            if existing.user_id != request.user.pk:
                raise ValidationError({"detail": "Invalid checkout reference."})
            return Response(order_data(existing), status=200)
        cart = active_cart(request.user)
        has_physical_items = any(
            not item.product.is_digital
            for item in cart.cart_items.select_related("product").all()
        )
        raw_address = request.data.get("address")
        if has_physical_items and not raw_address:
            raise ValidationError({"address": "Choose a delivery address first."})
        address = None
        if raw_address:
            address = get_object_or_404(
                Address,
                pk=serializers.IntegerField(min_value=1).run_validation(raw_address),
                user=request.user,
                is_deleted=False,
            )
        payment_type = request.data.get("payment_type", "cash_on_delivery")
        if payment_type not in ("cash_on_delivery", "user_wallet"):
            raise ValidationError(
                {
                    "detail": "Choose cash on delivery, ProAce user wallet, or use Stripe wallet checkout."
                }
            )
        if (
            payment_type == "cash_on_delivery"
            and cart.cart_items.filter(product__is_digital=True).exists()
        ):
            raise ValidationError(
                {"payment_type": "Digital products require payment before delivery."}
            )
        shipping_service = str(
            request.data.get(
                "shipping_service",
                "usps_ground_advantage" if has_physical_items else "digital_delivery",
            )
        ).strip()
        order = self._complete(
            request,
            key,
            address,
            str(request.data.get("coupon", "")).strip(),
            payment_type,
            shipping_service=shipping_service,
            shipping_quote=request.data.get("shipping_quote"),
        )
        return Response(order_data(order), status=201)


class WalletCheckoutSessionView(CheckoutView):
    @extend_schema(request=WalletCheckoutSerializer, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request: Request) -> Response:
        if stripe is None or not getattr(settings, "STRIPE_SECRET", ""):
            logger.warning("Stripe checkout requested but STRIPE_SECRET is not configured.")
            raise ValidationError(
                {
                    "detail": "Online card payments are currently unavailable. Please select another payment method or try again later."
                }
            )
        if getattr(settings, "STRIPE_CURRENCY", "usd").lower() != "usd":
            raise ValidationError({"detail": "Carrier checkout requires USD payments."})
        stripe.api_key = settings.STRIPE_SECRET
        key = serializers.UUIDField().run_validation(request.data.get("checkout_key"))
        from payment.models import CheckoutAttempt

        User.objects.select_for_update().get(pk=request.user.pk)
        previous = CheckoutAttempt.objects.filter(
            user=request.user, checkout_key=key
        ).first()
        if previous:
            if previous.status != "reserved":
                raise ValidationError(
                    {
                        "checkout_key": "Start a new checkout after a completed or released attempt."
                    }
                )
            previous_session = stripe.checkout.Session.retrieve(previous.session_id)
            return Response(
                {
                    "id": previous.session_id,
                    "url": previous_session.url,
                    "wallet_deduction": str(previous.wallet_amount),
                }
            )
        code = str(request.data.get("coupon", "")).strip()
        cart, snapshots, coupon_lines, subtotal = self._lines(request)
        has_physical_items = any(not row["is_digital"] for row in snapshots)
        raw_address = request.data.get("address")
        if has_physical_items and not raw_address:
            raise ValidationError({"address": "Choose a delivery address first."})
        address = None
        if raw_address:
            address = get_object_or_404(
                Address,
                pk=serializers.IntegerField(min_value=1).run_validation(raw_address),
                user=request.user,
                is_deleted=False,
            )
        self._validate_service_area(address, snapshots)
        coupon = None
        discount = Decimal("0")
        if code:
            coupon = Coupon.objects.filter(
                code__iexact=code,
                active=True,
                valid_from__lte=timezone.now(),
                valid_to__gte=timezone.now(),
            ).first()
            discount = calculate_coupon_discount(
                coupon, request.user, coupon_lines, subtotal, reserve=False
            )
        snapshots = allocate_checkout_lines(snapshots, coupon_lines, coupon, discount)
        total_weight = sum(
            Decimal(str(item.product.weight or "1.00")) * item.quantity
            for item in cart.cart_items.select_related("product").all()
            if not item.product.is_digital
        )
        shipping_service = str(
            request.data.get(
                "shipping_service",
                "usps_ground_advantage" if has_physical_items else "digital_delivery",
            )
        ).strip()
        shipping_quote = request.data.get("shipping_quote")
        paid_amount = None
        if not has_physical_items:
            address = None
            shipping_service = "digital_delivery"
            rate = {
                "carrier": "DIGITAL",
                "service_id": "digital_delivery",
                "amount": "0.00",
            }
        elif shipping_quote:
            rate = verify_quote(
                shipping_quote,
                request.user,
                cart,
                address,
                shipping_service,
                paid=paid_amount is not None,
            )
        else:
            carrier = (
                (shipping_service or "usps_ground_advantage")
                .split("_", 1)[0]
                .upper()
            )
            rates = cart_rates(carrier, cart, address)
            rate = next(
                (row for row in rates if row["service_id"] == shipping_service),
                None,
            )
            if rate is None:
                raise ValidationError(
                    {"shipping_service": "Select an available shipping service."}
                )
        if has_physical_items:
            from payment.geo import validate_military_carrier

            validate_military_carrier(
                address, str(rate.get("carrier") or rate["service_id"].split("_", 1)[0])
            )
        shipping = Decimal(rate["amount"])
        tax_breakdown = calculate_tax(
            items=snapshots,
            subtotal=subtotal - discount,
            shipping_fee=shipping,
            address=address,
        )
        tax = tax_breakdown.amount
        if (
            paid_amount is not None
            and int((subtotal - discount + shipping + tax) * 100) != paid_amount
        ):
            raise ValidationError(
                {"detail": "Paid amount does not match this cart. Contact support."}
            )
        total = subtotal - discount + shipping + tax
        wallet_amount_raw = request.data.get("wallet_amount")
        wallet_deduction = Decimal("0")
        if wallet_amount_raw is not None and str(wallet_amount_raw).strip():
            try:
                wallet_deduction = Decimal(str(wallet_amount_raw)).quantize(
                    Decimal(".01")
                )
            except Exception:
                raise ValidationError(
                    {"wallet_amount": "Invalid wallet deduction amount."}
                )
            if not wallet_deduction.is_finite():
                raise ValidationError(
                    {"wallet_amount": "Invalid wallet deduction amount."}
                )
            if wallet_deduction < Decimal("0"):
                raise ValidationError(
                    {"wallet_amount": "Wallet deduction cannot be negative."}
                )
            if wallet_deduction > Decimal("0"):
                user_wallet = get_or_create_user_wallet(request.user)
                if user_wallet.balance < wallet_deduction:
                    raise ValidationError(
                        {"wallet_amount": "Insufficient wallet balance."}
                    )
                max_deduction = max(Decimal("0"), total - Decimal("0.50"))
                wallet_deduction = min(wallet_deduction, max_deduction)

        charge_total = total - wallet_deduction
        methods = [
            configured_method.strip()
            for configured_method in getattr(
                settings, "STRIPE_WALLET_PAYMENT_METHODS", "cashapp"
            ).split(",")
            if configured_method.strip()
            and configured_method.strip().lower() != "paypal"
        ]
        if not methods:
            raise ValidationError(
                {"detail": "No Stripe wallet payment methods are configured."}
            )
        shipping_quote = shipping_quote or issue_quote(
            rate, request.user, cart, address
        )
        payment_metadata = {
            "checkout_key": str(key),
            "address": str(address.pk) if address else "",
            "coupon": code,
            "shipping_service": shipping_service,
            "shipping_quote": shipping_quote,
            "carrier": rate.get("carrier", "DIGITAL"),
            "wallet_deduction": str(wallet_deduction),
        }
        expires_at = timezone.now() + timedelta(minutes=30)
        if wallet_deduction > 0:
            debit_user_wallet(
                request.user,
                wallet_deduction,
                "Reserved split-tender checkout",
                reference=str(key),
            )
        session = stripe.checkout.Session.create(
            idempotency_key=f"checkout-{request.user.pk}-{key}",
            expires_at=int(expires_at.timestamp()),
            mode="payment",
            payment_method_types=methods,
            line_items=[
                {
                    "price_data": {
                        "currency": getattr(settings, "STRIPE_CURRENCY", "usd"),
                        "product_data": {"name": "ProAce order"},
                        "unit_amount": int(charge_total * 100),
                    },
                    "quantity": 1,
                }
            ],
            client_reference_id=str(request.user.pk),
            metadata=payment_metadata,
            payment_intent_data={"metadata": payment_metadata},
            success_url=f"{settings.FRONTEND_URL.rstrip('/')}/orders/stripe-return?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=(
                f"{settings.FRONTEND_URL.rstrip('/')}/checkout?wallet_cancelled=1"
                f"&checkout_key={key}"
            ),
        )
        CheckoutAttempt.objects.create(
            user=request.user,
            checkout_key=key,
            session_id=session.id,
            wallet_amount=wallet_deduction,
            expires_at=expires_at,
        )
        return Response(
            {
                "id": session.id,
                "url": session.url,
                "payment_methods": methods,
                "wallet_deduction": str(wallet_deduction),
            }
        )


class WalletCheckoutConfirmView(CheckoutView):
    @extend_schema(request=serializers.Serializer, responses=OrderSerializer)
    def post(self, request):
        session_id = str(request.data.get("session_id", "")).strip()
        if (
            stripe is None
            or not session_id
            or not getattr(settings, "STRIPE_SECRET", "")
        ):
            raise ValidationError({"detail": "Invalid wallet session."})
        stripe.api_key = settings.STRIPE_SECRET
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception:
            raise ValidationError({"detail": "Unable to verify wallet payment."})
        if session.get("payment_status") != "paid" or session.get(
            "client_reference_id"
        ) != str(request.user.pk):
            raise ValidationError({"detail": "Wallet payment has not been completed."})
        key = serializers.UUIDField().run_validation(
            session.get("metadata", {}).get("checkout_key")
        )
        existing = Order.objects.filter(checkout_key=key).first()
        if existing:
            if existing.user_id != request.user.pk:
                raise ValidationError({"detail": "Invalid checkout reference."})
            return Response(order_data(existing), status=200)
        from payment.models import CheckoutAttempt
        from payment.checkout_recovery import compensate_checkout

        attempt = CheckoutAttempt.objects.filter(
            user=request.user, session_id=session_id, checkout_key=key
        ).first()
        reserved_wallet = attempt is not None
        if not attempt:
            attempt = CheckoutAttempt.objects.create(
                user=request.user,
                checkout_key=key,
                session_id=session_id,
                wallet_amount=0,
                expires_at=timezone.now(),
            )
        if attempt and attempt.status in {"refunded", "released", "refund_pending"}:
            raise ValidationError(
                {
                    "detail": "This checkout failed. Its payment is refunded or awaiting refund; start a new checkout."
                }
            )
        try:
            with transaction.atomic():
                User.objects.select_for_update().get(pk=request.user.pk)
                existing = Order.objects.filter(checkout_key=key).first()
                if existing:
                    if existing.user_id != request.user.pk:
                        raise ValidationError({"detail": "Invalid checkout reference."})
                    return Response(order_data(existing), status=200)
                order = complete_stripe_checkout(request.user, session, attempt)
        except Exception as exc:
            if attempt:
                refunded = compensate_checkout(attempt, session, str(exc))
                raise ValidationError(
                    {
                        "detail": "Checkout could not be completed. Card refund initiated and wallet reservation released."
                        if refunded
                        else "Checkout could not be completed. Automatic refund is pending; do not pay again."
                    }
                )
            raise
        return Response(order_data(order), status=201)


@transaction.atomic
def complete_stripe_checkout(
    user: User, session: dict, attempt: Any = None
) -> Order:
    User.objects.select_for_update().get(pk=user.pk)
    if session.get('payment_status') != 'paid' or session.get('client_reference_id') != str(user.pk):
        raise ValidationError({'detail': 'Invalid paid checkout owner.'})
    if attempt and (attempt.user_id != user.pk or attempt.session_id != session.get('id')):
        raise ValidationError({'detail': 'Invalid checkout reservation.'})
    key_raw = session.get("metadata", {}).get("checkout_key")
    if not key_raw:
        raise ValidationError({"detail": "Session has no checkout reference."})
    key = serializers.UUIDField().run_validation(key_raw)
    existing = Order.objects.filter(checkout_key=key).first()
    if existing:
        if existing.user_id != user.pk:
            raise ValidationError({'detail': 'Invalid checkout reference.'})
        if attempt and attempt.status != "completed":
            attempt.status = "completed"
            attempt.save(update_fields=["status", "updated"])
        return existing
    if attempt and attempt.status in {'released', 'refunded', 'refund_pending'}:
        raise ValidationError({'detail': 'This checkout reservation is no longer active.'})

    address_raw = session.get("metadata", {}).get("address")
    address = None
    if address_raw:
        address = Address.objects.filter(
            pk=serializers.IntegerField(min_value=1).run_validation(address_raw),
            user=user,
        ).first()

    paid_amount = serializers.IntegerField(min_value=0).run_validation(
        session.get("amount_total")
    )
    if session.get("currency") != "usd":
        raise ValidationError({"detail": "Unsupported payment currency."})

    shipping_service = session.get("metadata", {}).get(
        "shipping_service",
        "digital_delivery" if not address else "usps_ground_advantage",
    )
    wallet_deduction_val = Decimal(
        str(session.get("metadata", {}).get("wallet_deduction", "0"))
    )
    if attempt and attempt.wallet_amount > 0 and wallet_deduction_val != attempt.wallet_amount:
        raise ValidationError(
            {"wallet_amount": "The payment does not match its wallet reservation."}
        )

    order = CheckoutView()._complete(
        user,
        key,
        address,
        session.get("metadata", {}).get("coupon", ""),
        "split_tender" if wallet_deduction_val > Decimal("0") else "stripe_wallet",
        session.get("id"),
        shipping_service=shipping_service,
        shipping_quote=session.get("metadata", {}).get("shipping_quote"),
        paid_amount=paid_amount + int(wallet_deduction_val * 100),
        wallet_paid_amount=wallet_deduction_val,
    )
    intent = session.get("payment_intent")
    if isinstance(intent, str) and intent:
        Order.objects.filter(pk=order.pk).update(stripe_payment_intent=intent)
    if attempt:
        attempt.status = "completed"
        attempt.save(update_fields=["status", "updated"])
    elif wallet_deduction_val > 0:
        debit_user_wallet(
            user,
            wallet_deduction_val,
            f"Split payment for #{order.orderId}",
            reference=order.orderId,
        )
    return order


class WalletCheckoutCancelView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(request=serializers.Serializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request: Request) -> Response:
        from payment.models import CheckoutAttempt
        from payment.checkout_recovery import compensate_checkout

        session_id = str(request.data.get("session_id", "")).strip()
        checkout_key_raw = request.data.get("checkout_key")
        if not session_id and not checkout_key_raw:
            raise ValidationError({"detail": "A checkout reference is required."})

        attempts = CheckoutAttempt.objects.filter(user=request.user)
        if session_id:
            attempts = attempts.filter(session_id=session_id)
        else:
            checkout_key = serializers.UUIDField().run_validation(checkout_key_raw)
            attempts = attempts.filter(checkout_key=checkout_key)
        attempt = attempts.first()

        if not attempt:
            return Response({"detail": "No active wallet reservation to release.", "released": False})

        if attempt.status != "reserved":
            response_data = {
                "detail": "This checkout reservation is already resolved.",
                "released": attempt.status in {"released", "refunded"},
                "completed": attempt.status == "completed",
            }
            if attempt.status == "completed":
                response_data["session_id"] = attempt.session_id
            return Response(response_data)
        if not stripe or not getattr(settings, "STRIPE_SECRET", ""):
            return Response(
                {"detail": "Unable to verify the payment session. Your wallet reservation is still held."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        stripe.api_key = settings.STRIPE_SECRET
        try:
            session = stripe.checkout.Session.retrieve(attempt.session_id)
            if session.get("payment_status") == "paid":
                recovered = compensate_checkout(
                    attempt, session, "Payment completed during cancellation"
                )
                attempt.refresh_from_db()
                if attempt.status == "completed":
                    return Response({
                        "detail": "Payment was completed and the order is ready.",
                        "released": False,
                        "completed": True,
                        "session_id": attempt.session_id,
                    })
                if recovered and attempt.status in {"released", "refunded"}:
                    return Response({
                        "detail": "The order could not be completed. Payment recovery has started and your wallet reservation was returned.",
                        "released": True,
                        "completed": False,
                    })
                return Response(
                    {"detail": "Payment recovery is pending. Do not start another checkout yet.", "released": False},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if session.get("status") == "complete":
                return Response(
                    {"detail": "Payment is still processing. Your wallet reservation remains held."},
                    status=status.HTTP_409_CONFLICT,
                )
            if session.get("status") == "open":
                session = stripe.checkout.Session.expire(attempt.session_id)
            if session.get("status") != "expired":
                return Response(
                    {"detail": "Stripe has not confirmed checkout cancellation. Your wallet reservation is still held."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        except Exception as exc:
            logger.warning("Unable to cancel Stripe checkout %s (%s)", attempt.pk, type(exc).__name__)
            return Response(
                {"detail": "Unable to verify checkout cancellation. Your wallet reservation is still held."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        compensate_checkout(attempt, session, "Cancelled by user")
        return Response({"detail": "Checkout reservation released back to wallet.", "released": True})


class WalletTopupCancelView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(request=serializers.Serializer, responses={200: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request: Request) -> Response:
        from payment.models import WalletFundingAttempt

        User.objects.select_for_update().get(pk=request.user.pk)
        session_id = str(request.data.get("session_id", "")).strip()
        query = WalletFundingAttempt.objects.filter(user=request.user, status="reserved")
        if session_id:
            query = query.filter(session_id=session_id)
        else:
            active_count = query.count()
            if active_count == 0:
                return Response(
                    {"detail": "No active wallet funding reservation to release.", "released": False}
                )
            if active_count > 1:
                return Response(
                    {"detail": "A specific wallet top-up session is required when multiple checkouts are active.", "released": False},
                    status=status.HTTP_409_CONFLICT,
                )
        attempt = query.select_for_update().order_by("-created").first()

        if not attempt:
            return Response({"detail": "No active wallet funding reservation to release.", "released": False})

        if not stripe or not getattr(settings, "STRIPE_SECRET", ""):
            return Response(
                {"detail": "Unable to verify the payment session. Your wallet top-up remains pending."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        stripe.api_key = settings.STRIPE_SECRET
        try:
            session = stripe.checkout.Session.retrieve(attempt.session_id)
            if session.get("payment_status") == "paid" or session.get("status") == "complete":
                return Response(
                    {"detail": "Payment was completed or is still processing. Your top-up remains pending."},
                    status=status.HTTP_409_CONFLICT,
                )
            if session.get("status") == "open":
                session = stripe.checkout.Session.expire(attempt.session_id)
            if session.get("status") != "expired":
                return Response(
                    {"detail": "Stripe has not confirmed top-up cancellation. Your reservation remains pending."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        except Exception as exc:
            logger.warning("Unable to cancel wallet top-up %s (%s)", attempt.pk, type(exc).__name__)
            return Response(
                {"detail": "Unable to verify top-up cancellation. Your reservation remains pending."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        attempt.status = "released"
        attempt.save(update_fields=["status", "updated"])
        return Response({"detail": "Wallet top-up reservation released.", "released": True})


class StripeWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT})
    def post(self, request: Request) -> Response:
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        event = None

        if not stripe or not webhook_secret:
            logger.error('Stripe webhook verification is not configured')
            return Response({'detail': 'Payment notifications are temporarily unavailable.'}, status=503)
        if not sig_header:
            return Response({'detail': 'A valid payment notification signature is required.'}, status=400)
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception as exc:
            logger.warning('Stripe webhook verification failed (%s)', type(exc).__name__)
            return Response({'detail': 'Invalid payment notification signature.'}, status=400)
        if not isinstance(event, dict):
            return Response({'detail': 'Invalid payment notification.'}, status=400)

        try:
            return self._process_event(event)
        except ValidationError:
            logger.warning('Verified payment notification failed settlement validation')
            return Response({'detail': 'Invalid payment notification.'}, status=400)
        except Exception:
            logger.exception('Verified payment notification processing failed')
            return Response({'detail': 'Payment update will be retried.'}, status=503)

    def _process_event(self, event: dict[str, Any]) -> Response:
        event_type = event.get("type", "")
        data = event.get('data')
        if not isinstance(data, dict) or not isinstance(data.get('object'), dict):
            return Response({'detail': 'Invalid payment notification.'}, status=400)
        data_object = data['object']

        if event_type == "checkout.session.completed":
            session = data_object
            if session.get("payment_status") == "paid":
                client_ref = session.get("client_reference_id")
                user = User.objects.filter(pk=client_ref).first() if client_ref else None
                if user:
                    if session.get("metadata", {}).get("wallet_topup") == "true":
                        from payment.funding import confirm_funding
                        confirm_funding(user, session.get("id"), session)
                    elif session.get("metadata", {}).get("checkout_key"):
                        from payment.models import CheckoutAttempt
                        attempt = CheckoutAttempt.objects.filter(session_id=session.get("id")).first()
                        complete_stripe_checkout(user, session, attempt)

        elif event_type in {
            "charge.refunded",
            "refund.created",
            "refund.updated",
            "refund.failed",
            "charge.dispute.created",
            "charge.dispute.updated",
            "charge.dispute.closed",
        }:
            from payment.provider_events import reconcile_event

            try:
                reconcile_event(event_type, data_object)
            except Exception:
                logger.exception("Payment adjustment reconciliation failed")
                return Response(
                    {"detail": "Payment update will be retried."}, status=503
                )

        elif event_type == "checkout.session.expired":
            session = data_object
            session_id = session.get("id")
            if session_id:
                from payment.models import CheckoutAttempt, WalletFundingAttempt
                from payment.checkout_recovery import compensate_checkout
                attempt = CheckoutAttempt.objects.filter(session_id=session_id).first()
                if attempt:
                    compensate_checkout(attempt, session, "Stripe session expired")
                funding_attempt = WalletFundingAttempt.objects.filter(session_id=session_id, status="reserved").first()
                if funding_attempt:
                    funding_attempt.status = "released"
                    funding_attempt.save(update_fields=["status", "updated"])

        return Response({"received": True}, status=200)


class CouponAdminView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(responses=CouponAdminSerializer(many=True))
    def get(self, request):
        coupons = Coupon.objects.select_related("product", "created_by").order_by("-created", "-pk")
        return Response(CouponAdminSerializer(coupons, many=True).data)

    @extend_schema(request=CouponAdminSerializer, responses=CouponAdminSerializer)
    def post(self, request):
        serializer = CouponAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        coupon = serializer.save(created_by=request.user if request.user.is_authenticated else None)
        return Response(CouponAdminSerializer(coupon).data, status=201)


class TaxJurisdictionAdminView(APIView):
    permission_classes = [IsBackoffice]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        from payment.models import TaxJurisdiction
        from payment.serializers import TaxJurisdictionSerializer

        qs = TaxJurisdiction.objects.all()

        search = str(request.query_params.get("search", "")).strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(state__icontains=search)
                | Q(postal_code__startswith=search)
            )

        country = str(request.query_params.get("country", "")).strip().upper()
        if country:
            qs = qs.filter(country=country)

        state = str(request.query_params.get("state", "")).strip().upper()
        if state:
            qs = qs.filter(state=state)

        is_active_raw = request.query_params.get("is_active")
        if is_active_raw is not None:
            if str(is_active_raw).lower() in {"true", "1"}:
                qs = qs.filter(is_active=True)
            elif str(is_active_raw).lower() in {"false", "0"}:
                qs = qs.filter(is_active=False)

        total_count = TaxJurisdiction.objects.count()
        active_count = TaxJurisdiction.objects.filter(is_active=True).count()
        zip_overrides = TaxJurisdiction.objects.exclude(postal_code="").count()

        items = qs.order_by("country", "state", "postal_code")
        serialized = TaxJurisdictionSerializer(items, many=True).data

        provider = getattr(settings, "TAX_PROVIDER", "local")
        stripe_tax_enabled = getattr(settings, "STRIPE_TAX_ENABLED", False)
        default_rate = str(
            getattr(
                settings,
                "DEFAULT_TAX_RATE",
                getattr(settings, "CHECKOUT_TAX_RATE", "0.00"),
            )
        )

        return Response(
            {
                "provider": provider,
                "stripe_tax_enabled": stripe_tax_enabled,
                "default_tax_rate": default_rate,
                "summary": {
                    "total_jurisdictions": total_count,
                    "active_jurisdictions": active_count,
                    "zip_overrides": zip_overrides,
                },
                "results": serialized,
            }
        )

    @extend_schema(
        request=TaxJurisdictionSerializer, responses=TaxJurisdictionSerializer
    )
    def post(self, request: Request) -> Response:
        from payment.serializers import TaxJurisdictionSerializer

        serializer = TaxJurisdictionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        jurisdiction = serializer.save()
        return Response(TaxJurisdictionSerializer(jurisdiction).data, status=201)


class TaxJurisdictionDetailAdminView(APIView):
    permission_classes = [IsBackoffice]

    @extend_schema(responses=TaxJurisdictionSerializer)
    def get(self, request: Request, pk: int) -> Response:
        from payment.models import TaxJurisdiction
        from payment.serializers import TaxJurisdictionSerializer

        jurisdiction = get_object_or_404(TaxJurisdiction, pk=pk)
        return Response(TaxJurisdictionSerializer(jurisdiction).data)

    @extend_schema(
        request=TaxJurisdictionSerializer, responses=TaxJurisdictionSerializer
    )
    def patch(self, request: Request, pk: int) -> Response:
        from payment.models import TaxJurisdiction
        from payment.serializers import TaxJurisdictionSerializer

        jurisdiction = get_object_or_404(TaxJurisdiction, pk=pk)
        serializer = TaxJurisdictionSerializer(jurisdiction, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(TaxJurisdictionSerializer(updated).data)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, pk: int) -> Response:
        from payment.models import TaxJurisdiction
        jurisdiction = get_object_or_404(TaxJurisdiction, pk=pk)
        jurisdiction.delete()
        return Response(status=204)


class TaxJurisdictionSeedDefaultsAdminView(APIView):
    permission_classes = [IsBackoffice]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        from payment.tax import DEFAULT_US_JURISDICTIONS
        from payment.models import TaxJurisdiction
        count = 0
        for entry in DEFAULT_US_JURISDICTIONS:
            _, created = TaxJurisdiction.objects.update_or_create(
                country="US",
                state=entry["state"],
                postal_code="",
                defaults={
                    "name": entry["name"],
                    "rate": entry["rate"],
                    "tax_shipping": entry["tax_shipping"],
                    "tax_digital": entry["tax_digital"],
                    "is_active": True,
                },
            )
            if created:
                count += 1
        return Response({
            'detail': f"Baseline tax jurisdictions initialized. {count} new entries created, {len(DEFAULT_US_JURISDICTIONS)} total baseline rules active."
        })


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
        from notification.views import password_changed_notification

        password_changed_notification(user)
        from core.auth_sync import sync_technical_admin_credentials, is_technical_super_admin
        if is_technical_super_admin(user):
            sync_technical_admin_credentials(user, password)
        return Response(tokens(user))
