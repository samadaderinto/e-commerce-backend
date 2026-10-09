from core.access import IsCustomer
from rest_framework.decorators import action

from core.models import User
from product.models import Product
from product.policies import validate_purchase
from rest_framework.permissions import IsAuthenticated
from cart.cache import (
    active_cart_cache_key,
    CART_CACHE_TIMEOUT,
    get_cached_active_cart_data,
    invalidate_cart_cache,
)
from cart.models import Cart, CartItem

from cart.serializers import CartSerializer

from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.db import transaction

from drf_spectacular.utils import extend_schema
# Create your views here.


def request_payload(request):
    if request.method == "GET":
        return request.query_params or JSONParser().parse(request)
    return JSONParser().parse(request)


def parse_quantity(data, default=1):
    try:
        quantity = int(data.get("quantity", default))
    except (TypeError, ValueError):
        raise ValidationError({"quantity": "Quantity must be a valid number"})

    if quantity < 1:
        raise ValidationError({"quantity": "Quantity must be at least 1"})
    return quantity


def serialize_cart(cart):
    return CartSerializer(cart).data


class CartViewSet(viewsets.GenericViewSet):
    permission_classes = [IsCustomer]
    auth_user = User
    cart_item = CartItem
    user_cart = Cart
    merchant_product = Product

    serializer_class = CartSerializer
    
    
    @extend_schema(responses={status.HTTP_200_OK: CartSerializer})
    @action(detail=False, methods=['get'], url_path='get')
    def get_or_create_cart(self, request):
        user = request.user
        cart, created = self.user_cart.objects.get_or_create(user=user, ordered=False)
        if created:
            invalidate_cart_cache(cart)

        cache_key = active_cart_cache_key(user.id)
        cached_cart = cache.get(cache_key)
        if cached_cart is not None:
            return Response(cached_cart, status=status.HTTP_200_OK)

        cart_data = get_cached_active_cart_data(user.id)
        cache.set(cache_key, cart_data, CART_CACHE_TIMEOUT)
        return Response(cart_data, status=status.HTTP_200_OK)
    
    @extend_schema(responses={status.HTTP_200_OK: None})
    @action(detail=False, methods=['post'], url_path='add')
    @transaction.atomic
    def add_to_cart(self, request):
        data = request_payload(request)
        quantity = parse_quantity(data)
        product = get_object_or_404(self.merchant_product, pk=data["product"])

        if product.product_type == 'affiliate_clickbank':
            return Response(
                {
                    'message': 'This item is fulfilled directly by our partner. Please use the official partner link.',
                    'affiliate_hoplink': product.affiliate_hoplink,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validate_purchase(product, request.user)
        # Digital goods represent a single entitlement. Re-downloads are
        # provided from completed orders, so quantity can never exceed one.
        if product.is_digital:
            quantity = 1
        if not product.is_digital and product.available < quantity:
            return Response(
                {'message': 'Not enough stock available'},
                status=status.HTTP_409_CONFLICT
            )

        cart, created_cart = self.user_cart.objects.select_for_update().get_or_create(
            user=request.user,
            ordered=False
        )
        from product.policies import selected_variant
        variant_name = str(data.get('variant') or '')
        option = selected_variant(product, variant_name)
        cart_item, created = self.cart_item.objects.select_for_update().get_or_create(cart=cart, product=product, variant=variant_name)
        if not created:
            quantity += cart_item.quantity

        if not product.is_digital and product.available < quantity:
            return Response(
                {'message': 'Not enough stock available'},
                status=status.HTTP_409_CONFLICT
            )

        if option and quantity > option.get('available', product.available):
            raise ValidationError({'variant': 'Insufficient option stock.'})
        cart_item.quantity = quantity
        cart_item.save()
        if created_cart:
            invalidate_cart_cache(cart)
        invalidate_cart_cache(cart)
        return Response(serialize_cart(cart), status=status.HTTP_201_CREATED)

    @extend_schema(responses={status.HTTP_200_OK: CartSerializer})
    def _resolve_cart_item(self, request, data, lock=False):
        product_id = data.get("product")
        if not product_id:
            raise ValidationError({"product": "Product ID is required."})
        cart_id = data.get("cart")
        cart_filter = {"cart_id": cart_id} if cart_id else {}
        query = self.cart_item.objects.select_for_update() if lock else self.cart_item.objects
        return get_object_or_404(
            query,
            cart__user=request.user,
            cart__ordered=False,
            product_id=product_id,
            variant=str(data.get("variant") or ""),
            **cart_filter,
        )

    @extend_schema(responses={status.HTTP_200_OK: CartSerializer})
    @action(detail=False, methods=['patch'], url_path='update')
    @transaction.atomic
    def update_cart_item(self, request):
        data = request_payload(request)
        quantity = parse_quantity(data)
        cart_item = self._resolve_cart_item(request, data, lock=True)

        from product.policies import selected_variant
        option = selected_variant(cart_item.product, cart_item.variant)
        if option and quantity > option.get('available', cart_item.product.available):
            raise ValidationError({'variant': 'Insufficient option stock.'})
        validate_purchase(cart_item.product, request.user)
        if cart_item.product.is_digital:
            quantity = 1
        if not cart_item.product.is_digital and cart_item.product.available < quantity:
            return Response(
                {'message': 'Not enough stock available'},
                status=status.HTTP_409_CONFLICT
            )

        cart_item.quantity = quantity
        cart_item.save()
        invalidate_cart_cache(cart_item.cart)
        return Response(serialize_cart(cart_item.cart), status=status.HTTP_200_OK)

    @extend_schema(responses={status.HTTP_200_OK: CartSerializer})
    @action(detail=False, methods=['post'], url_path='increase')
    @transaction.atomic
    def increase_cart_item(self, request):
        data = request_payload(request)
        increment_by = parse_quantity(data)
        cart_item = self._resolve_cart_item(request, data, lock=True)
        quantity = cart_item.quantity + increment_by
        from product.policies import selected_variant
        option = selected_variant(cart_item.product, cart_item.variant)
        if option and quantity > option.get('available', cart_item.product.available):
            raise ValidationError({'variant': 'Insufficient option stock.'})

        validate_purchase(cart_item.product, request.user)
        if cart_item.product.is_digital:
            quantity = 1
        if not cart_item.product.is_digital and cart_item.product.available < quantity:
            return Response(
                {'message': 'Not enough stock available'},
                status=status.HTTP_409_CONFLICT
            )

        cart_item.quantity = quantity
        cart_item.save()
        invalidate_cart_cache(cart_item.cart)
        return Response(serialize_cart(cart_item.cart), status=status.HTTP_200_OK)

    @extend_schema(responses={status.HTTP_200_OK: CartSerializer})
    @action(detail=False, methods=['post'], url_path='decrease')
    @transaction.atomic
    def decrease_cart_item(self, request):
        data = request_payload(request)
        decrement_by = parse_quantity(data)
        cart_item = self._resolve_cart_item(request, data, lock=True)
        cart = cart_item.cart
        quantity = cart_item.quantity - decrement_by

        if quantity < 1:
            cart_item.delete()
        else:
            cart_item.quantity = quantity
            cart_item.save()

        invalidate_cart_cache(cart)
        return Response(serialize_cart(cart), status=status.HTTP_200_OK)

    @extend_schema(responses={status.HTTP_202_ACCEPTED: None})
    @action(detail=False, methods=['delete'], url_path='delete')
    @transaction.atomic
    def delete_cart_item(self, request):
        data = request_payload(request)
        cart_item = self._resolve_cart_item(request, data, lock=True)
        cart = cart_item.cart
        cart_item.delete()
        invalidate_cart_cache(cart)
        return Response(serialize_cart(cart), status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses={status.HTTP_202_ACCEPTED: CartSerializer})
    @action(detail=False, methods=['delete'], url_path='clear')
    @transaction.atomic
    def clear_cart(self, request):
        data = request_payload(request)
        cart_id = data.get("cart")
        cart_filter = {"id": cart_id} if cart_id else {}
        cart = get_object_or_404(self.user_cart, user=request.user, ordered=False, **cart_filter)
        self.cart_item.objects.filter(cart=cart).delete()
        invalidate_cart_cache(cart)
        return Response(serialize_cart(cart), status=status.HTTP_202_ACCEPTED)
