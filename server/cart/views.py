from rest_framework.decorators import action

from core.models import User
from product.models import Product
from cart.cache import (
    active_cart_cache_key,
    CART_CACHE_TIMEOUT,
    get_cached_active_cart_data,
    invalidate_cart_cache,
)
from cart.models import Cart, CartItem

from cart.seralizers import CartSerializer

from kink import di

from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from django.core.cache import cache
from django.shortcuts import get_object_or_404

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
    auth_user: User = di[User]
    cart_item: CartItem = di[CartItem]
    user_cart: Cart = di[Cart]
    merchant_product: Product = di[Product]

    serializer_class = CartSerializer
    
    
    @extend_schema(responses={status.HTTP_200_OK: CartSerializer})
    @action(detail=False, methods=['get'], url_path='get')
    def get_or_create_cart(self, request):
        data = request_payload(request)
        user = get_object_or_404(self.auth_user, id=data["user"])
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
    def add_to_cart(self, request):
        data = request_payload(request)
        quantity = parse_quantity(data)
        product = get_object_or_404(self.merchant_product, pk=data["product"])

        if product.available < quantity:
            return Response(
                {'message': 'Not enough stock available'},
                status=status.HTTP_409_CONFLICT
            )

        cart, created_cart = self.user_cart.objects.get_or_create(
            user_id=data["user"],
            ordered=False
        )
        cart_item, created = self.cart_item.objects.get_or_create(cart=cart, product=product)
        if not created:
            quantity += cart_item.quantity

        if product.available < quantity:
            return Response(
                {'message': 'Not enough stock available'},
                status=status.HTTP_409_CONFLICT
            )

        cart_item.quantity = quantity
        cart_item.save()
        if created_cart:
            invalidate_cart_cache(cart)
        invalidate_cart_cache(cart)
        return Response(serialize_cart(cart), status=status.HTTP_201_CREATED)

    @extend_schema(responses={status.HTTP_200_OK: CartSerializer})
    @action(detail=False, methods=['patch'], url_path='update')
    def update_cart_item(self, request):
        data = request_payload(request)
        quantity = parse_quantity(data)
        cart_item = get_object_or_404(
            self.cart_item,
            cart=data["cart"],
            product=data["product"],
        )

        if cart_item.product.available < quantity:
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
    def increase_cart_item(self, request):
        data = request_payload(request)
        increment_by = parse_quantity(data)
        cart_item = get_object_or_404(
            self.cart_item,
            cart=data["cart"],
            product=data["product"],
        )
        quantity = cart_item.quantity + increment_by

        if cart_item.product.available < quantity:
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
    def decrease_cart_item(self, request):
        data = request_payload(request)
        decrement_by = parse_quantity(data)
        cart_item = get_object_or_404(
            self.cart_item,
            cart=data["cart"],
            product=data["product"],
        )
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
    def delete_cart_item(self, request):
        data = request_payload(request)
        cart_item = get_object_or_404(
            self.cart_item,
            cart=data["cart"],
            product=data["product"],
        )
        cart = cart_item.cart
        cart_item.delete()
        invalidate_cart_cache(cart)
        return Response(serialize_cart(cart), status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses={status.HTTP_202_ACCEPTED: CartSerializer})
    @action(detail=False, methods=['delete'], url_path='clear')
    def clear_cart(self, request):
        data = request_payload(request)
        cart = get_object_or_404(self.user_cart, id=data["cart"], ordered=False)
        self.cart_item.objects.filter(cart=cart).delete()
        invalidate_cart_cache(cart)
        return Response(serialize_cart(cart), status=status.HTTP_202_ACCEPTED)
