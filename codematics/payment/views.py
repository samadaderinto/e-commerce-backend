from django.conf import settings


from payment.models import Coupon, Order, Payment
from product.models import Product
from core.models import Address
from core.permissions import EcommerceAccessPolicy
from core.utilities import methods, calculate_order_amount
from payment.serializers import OrdersSerializer

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
        orders = Order.objects.filter(user=request.user, status="")
        order_items = orders[0].Order.all()
        order_total = orders[0].get_totals()
        context = {"form": form, "order_items": order_items, "order_total": order_total}
        # Getting the saved saved_address
        # cartId, orderId, coupon_used, tax, status, delivery, total, subtotal, ordered_date, payment_type

        saved_address = Address.objects.filter(user=request.user)
        if saved_address.exists():
            savedAddress = saved_address
            context = {
                "form": form,
                "order_items": order_items,
                "order_total": order_total,
                "savedAddress": savedAddress,
            }
        if request.method == methods["post"]:
            saved_address = Address.objects.filter(user=request.user)
            if saved_address.exists():
                savedAddress = saved_address.first()
                form = OrdersSerializer(request.POST, instance=savedAddress)
                if form.is_valid():
                    billingaddress = form.save(commit=False)
                    billingaddress.user = request.user
                    billingaddress.save()
            else:
                form = OrdersSerializer(request.POST)
                if form.is_valid():
                    billingaddress = form.save(commit=False)
                    billingaddress.user = request.user
                    billingaddress.save()


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
        return Response("coupon does not exist", status=404)

    if request.method == methods["post"]:
        if coupon.can_use():
            coupon.used()
            return Response(
                {"discount": coupon.discount, "message": "discount successfully used"},
                safe=False,
            )
    return Response("invalid coupon", status=status.HTTP_401_UNAUTHORIZED)





