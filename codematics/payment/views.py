from django.conf import settings


from cart.models import Cart, CartItem
from cart.seralizers import CartSerializer
from core.serializers import AddressSerializer


from payment.models import Coupon, Order, Payment
from product.models import Product
from core.models import Address
from core.permissions import EcommerceAccessPolicy
from core.utilities import methods, calculate_order_amount
from payment.serializers import OrdersSerializer,CheckOutSerializer

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import JSONParser


import stripe


stripe.api_key = settings.STRIPE_SECRET


# Create your views here.


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_checkout_session(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = CheckOutSerializer(data=data)

    if serializer.is_valid():
        id = serializer.validated_data["id"]
        userId = serializer.validated_data["userId"]
        cart = Cart.objects.get(id=id, userId=userId, ordered=False)
        cart_items = CartItem.objects.filter(cartId=cart.id)
        address = serializer.validated_data.get(
            ["address"], Address.objects.get(user=userId, is_default=True)
        )

        address_serializer = AddressSerializer(address)

        if address_serializer.is_valid():
            if address.id is not Address.objects.get(user=userId, is_default=True).id:
                address_serializer.save()
            else:
               Response({"cart_items": cart_items,"total": calculate_order_amount(cart_items)},status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def capture_checkout_session(request):
    if request.method == methods["post"]:
        try:
            user = request.POST.get("user")
            cart = request.POST.get("cart")
            code = request.POST.get("code")

            coupon = Coupon.objects.get(code=code)

        except:
            return Response(status=status.HTTP_404_NOT_FOUND)
        discount = 0

        if coupon.can_use():
            discount = coupon.discount
            coupon.used()

            # subtotal = []
            for item in cart:
                id = item.get("id")
                quantity = item.get("quantity")
                product = Product.objects.get(pk=id)

                # Validate product inventory
                if product.available <= 0:
                    return Response(
                        data={"message": "One of your products is sold out"}, status=409
                    )

            #     subtotal.append(p.price * quantity)

            # # total calculations
            # tax = round(sum(subtotal) * Decimal(tax_list[0]), 2)
            # total = round(Decimal(sum(subtotal) + tax), 2)
            # stripe_total = int(total*100)

            intent = stripe.PaymentIntent.create(
                amount=calculate_order_amount(cart["items"]),
                currency="usd",
                automatic_payment_methods={
                    "enabled": True,
                },
                receipt_email="test@example.com",
            )

            return ""


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def redeem_coupon(request):
    data = JSONParser().parse(request)

    try:
        coupon = Coupon.objects.get(code=data.get("code", ""))

    except:
        return Response("coupon does not exist", status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["post"]:
        if coupon.can_use():
            coupon.used()
            return Response(
                {"discount": coupon.discount, "message": "discount successfully used"},
                status=status.HTTP_200_OK,
            )
    return Response("invalid coupon", status=status.HTTP_401_UNAUTHORIZED)
