from django.shortcuts import render
from django.contrib.auth.models import Group
from django.conf import settings


from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView


from affiliates.models import Marketer
from affiliates.serializers import MarketerSerializer


from codematics.payment.models import Order
from codematics.payment.serializers import OrdersSerializer


from payment.models import Coupon
from payment.serializers import CouponSerializer


from core.serializers import UserSerializer, VerifyUserSerializer, RefundsSerializer
from core.permissions import EcommerceAccessPolicy
from core.utilities import auth_token, methods, send_mail
from core.models import User, Refund
from product.models import Specification
from store.models import StoreAddress, Store

from usps import USPSApi, Address as uspsAddress
from usps import SERVICE_PRIORITY, LABEL_ZPL



# Create your views here.


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_staff(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        if User.objects.filter(email=data["email"]).exists():
            return Response(
                {"error": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            serializer = UserSerializer(data=data)

        if serializer.is_valid():
            user = serializer.save()
            VerifyUserSerializer(data)
            token = auth_token(user)

            return Response(
                serializer.data,
                headers={"Authorization": token},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def give_staff_permission(request):
    data = JSONParser().parse(request)
    serializer = UserSerializer(data=data)
    if serializer.is_valid():
        email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email, is_staff=True)
        user.groups.add(Group.objects.get(name="staff"))
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_staff_detail(request, userId):
    data = JSONParser().parse(request)

    try:
        user = User.objects.get(pk=userId, email=data.get("email"), is_staff=True)
    except:
        return Response(status=404)

    if request.method == methods["post"]:
        serializer = UserSerializer(user, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_staff_account(request):
    if request.method == methods["delete"]:
        data = JSONParser().parse(request)
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            send_mail("account-delete-confirmation", serializer.validated_data["email"], None)
            # on button click in email, account automatically deletes
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def revoke_staff_permission(request):
    data = JSONParser().parse(request)
    serializer = UserSerializer(data=data)
    if serializer.is_valid():
        email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email, is_superuser=True)
        user.groups.remove(Group.objects.get(name="staff"))
        send_mail()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view([methods["get"], methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def get_staffs(request):
    if request.method == methods["get"]:
        staffs = User.objects.all().order_by("created").reverse()
        serializer = UserSerializer(staffs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["get"]])
def get_staff(request, userId):
    staff = User.objects.get(pk=userId, is_staff=True)
    if request.method == methods["get"]:
        serializer = User(staff)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_coupons(request):
    try:
        coupons = Coupon.objects.all()
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = CouponSerializer(coupons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_coupon(request, codeId):
    try:
        coupons = Coupon.objects.get(pk=codeId)
    except:
        return Response(status=404)

    if request.method == methods["delete"]:
        coupons.delete()
    return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_coupon(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = CouponSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# will properly write this later
@api_view([methods["put"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_coupon(request, code):
    if request.method == methods["put"]:
        queryset = Coupon.objects.filter(code=code)
        serializer = CouponSerializer(queryset)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_users(request):
    try:
        users = User.objects.all().order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_shipment(request, test: bool):
    
    usps = USPSApi(settings.USPS_USERNAME, test=test)
    # will use actua addresses later for both
    to_address = uspsAddress(
        name="Tobin Brown",
        address_1="1234 Test Ave.",
        city="Test",
        state="NE",
        zipcode="55555",
        phone="",
    )

    from_address = uspsAddress(
        name="Tobin Brown",
        address_1="1234 Test Ave.",
        city="Test",
        state="NE",
        zipcode="55555",
        phone="",
    )
    validate_to_address = usps.validate_address(to_address)
    validate_from_address = usps.validate_address(from_address)
    weight = 10
    if validate_to_address.result and validate_from_address.result:
        label = usps.create_label(
            to_address, from_address, weight, SERVICE_PRIORITY, LABEL_ZPL
        )
        return Response(
            {"success": "shipment created"}, label.result, status=status.HTTP_200_OK
        )
    return Response(
        {"error": "wrong shipment information"},
        label.result,
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_refunds(request):
    try:
        refunds = Refund.objects.all().order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RefundsSerializer(refunds, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_refund(request,refundId):
    try:
        refunds = Refund.objects.get(id=refundId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RefundsSerializer(refunds)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def refund_response(request):
    data = JSONParser().parse(request)
    serializer = RefundsSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        user = User.objects.get(id=serializer.validated_data["user"])
        email = user.email
        data = {
            "firstname": user.first_name,
            "order": serializer.validated_data["order"],
            "products": [],
        }
        send_mail("refund-request-acknowledged", email, data=data)
        return Response(status=status.HTTP_202_ACCEPTED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_marketers(request):
    try:
        marketer = Marketer.objects.all().order_by("created").reverse()
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = MarketerSerializer(marketer, many=True)
        return Response(serializer.data, safe=False)
    
    
class GetOrders(ListAPIView):
    permission_classes = (EcommerceAccessPolicy,)

    serializer_class = OrdersSerializer

    search_field = (
        "id",
        "status",
        "orderId",
        "ordered_date",
    )

    filter_backends = [SearchFilter,OrderingFilter]
    ordering_fields = ["ordered_date"]

    paginate_by = 15

    def get_queryset(self):
        return Order.objects.all()

    def get_serializer_context(self):
        return {"request": self.request}    