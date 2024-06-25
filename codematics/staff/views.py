
from django.conf import settings

from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView


from affiliates.models import Marketer
from affiliates.serializers import MarketerSerializer
from notification.views import refund_requested_nofication 
from store.serializers import StoreAddressSerializer

from staff.serilalizers import CommentSerializer

from staff.models import Comment
from payment.models import Coupon, Order
from payment.serializers import CouponSerializer, OrdersSerializer


from django.contrib.sites.shortcuts import get_current_site

from rest_framework.generics import RetrieveUpdateDestroyAPIView, ListCreateAPIView
from core.serializers import UserSerializer, RefundsSerializer, StoreSerializer, StaffSerializer, AdminSerializer
from core.utilities import auth_token, methods, send_mail, TokenGenerator
from core.models import User, Refund
from product.models import Specification
from store.models import StoreAddress, Store

from usps import USPSApi, Address as uspsAddress
from usps import SERVICE_PRIORITY, LABEL_ZPL


from django.utils.http import urlsafe_base64_encode
from django.urls import reverse
from django.utils.encoding import (
    smart_str,
    force_str,
    smart_bytes,
    force_bytes,

    DjangoUnicodeDecodeError
)

# Create your views here.

usps = USPSApi(settings.USPS_USERNAME, test=True)



def create_staff(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        if User.objects.filter(email=data["email"]).exists():
            return Response(
                {"error": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User.objects.create_staffuser(**data)
            serializer = StaffSerializer(user)

            uidb64 = urlsafe_base64_encode(force_bytes(user.id))
            token = TokenGenerator().make_token(user)
            current_site = get_current_site(request).domain
            relativeLink = reverse(
                "activate", kwargs={"uidb64": uidb64, "token": token}
            )
            absolute_url = f"http://{current_site}{relativeLink}"

            token = auth_token(user)
            send_mail("onboarding-user", user.email,
                      data={"firstname": user.first_name, "absolute_url": absolute_url})

            return Response(
                serializer.data,
                headers={"Authorization": token},
                status=status.HTTP_201_CREATED,
            )



def create_admin(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        if User.objects.filter(email=data["email"]).exists():
            return Response(
                {"error": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST)
        else:
            user = User.objects.create_superuser(**data)
            serializer = AdminSerializer(user)

            uidb64 = urlsafe_base64_encode(force_bytes(user.id))
            token = TokenGenerator().make_token(user)
            current_site = get_current_site(request).domain
            relativeLink = reverse(
                "activate", kwargs={"uidb64": uidb64, "token": token}
            )
            absolute_url = f"http://{current_site}{relativeLink}"

            token = auth_token(user)
            # send_mail("onboarding-user", user.email,
            #           data={"firstname": user.first_name, "absolute_url": absolute_url})

            return Response(
                serializer.data,
                headers={"Authorization": token},
                status=status.HTTP_201_CREATED,
            )



def give_staff_permission(request):
    data = JSONParser().parse(request)
    serializer = UserSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email, is_staff=True)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    # user.has_perm = True
    user.save()
    return Response({"success": "Permission granted for this staff member"}, status=status.HTTP_200_OK)



def edit_staff_detail(request, userId):
    data = JSONParser().parse(request)

    try:
        user = User.objects.get(
            pk=userId, email=data.get("email"), is_staff=True)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["post"]:
        serializer = UserSerializer(user, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        




def delete_staff_account_by_admin(request):
    if request.method == methods["delete"]:
        data = JSONParser().parse(request)
        serializer = UserSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.delete()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        



def revoke_staff_permission(request):
    data = JSONParser().parse(request)
        
    try:
        staff = User.objects.get(email=data.get("email"),is_staff=True)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    staff.is_active = False
    staff.save()
    return Response({"success": "Permission revoked for this staff member"}, status=status.HTTP_200_OK)



def get_staffs(request):
    
    staffs = User.objects.filter(is_staff=True).order_by("created").reverse()
    serializer = StaffSerializer(staffs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)



def get_staff(request, staffId):
    
    try:
        staff = User.objects.get(id=staffId, is_staff=True)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        
        serializer = UserSerializer(staff)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)



def get_coupons(request):
    try:
        coupons = Coupon.objects.all()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = CouponSerializer(coupons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def delete_coupon(request, codeId):
    try:
        coupons = Coupon.objects.get(pk=codeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        coupons.delete()
    return Response(status=status.HTTP_202_ACCEPTED)



def create_coupon(request):
    
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = CouponSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        

def edit_coupon(request, couponId):
    if request.method == methods["put"]:
        coupon = Coupon.objects.get(code=couponId)
        serializer = CouponSerializer(coupon )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
       



def get_users(request):
    try:
        users = User.objects.all().order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



def create_shipment(request):
    # will use actual addresses later for both
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
        data = {}
        send_mail("order-summary", "fake@email.com", data=data)
        return Response(
            {"success": "shipment created"}, label.result, status=status.HTTP_200_OK
        )
    return Response(
        {"error": "wrong shipment information"},
        label.result,
        status=status.HTTP_400_BAD_REQUEST,
    )



def send_track_order_mail(request):
    # tracking number provided by usps in place of the zero's
    track = usps.track("00000000000000000000")

    if track.result:
        data = {}
        send_mail("order-summary", "fake@email.com", data=data)
        return Response(
            {"success": "shipment created"}, track.result, status=status.HTTP_200_OK
        )
    return Response(
        {"error": "wrong shipment information"}, status=status.HTTP_400_BAD_REQUEST)



def get_refunds(request):
    try:
        refunds = Refund.objects.all().order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RefundsSerializer(refunds, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



def get_refund(request, refundId):
    try:
        refunds = Refund.objects.get(id=refundId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RefundsSerializer(refunds)
        return Response(serializer.data, status=status.HTTP_200_OK)



def refund_response(request,orderId, userId):
    if request.method == methods["post"]:
        user = User.objects.get(id=userId)
     
        data = {
            "firstname": user.first_name,
            "orderId": orderId,
            "message": "",
        }
        send_mail("refund-response", user.email, data=data)
        return Response(status=status.HTTP_200_OK)



def get_marketers(request):
    try:
        marketer = Marketer.objects.all().order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = MarketerSerializer(marketer, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



def get_marketer(request, marketerId):
    try:
       marketer = Marketer.objects.get(id=marketerId)
    except:   
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["get"]:
        
        serializer = MarketerSerializer(marketer)
       
        return Response(serializer.data, status=status.HTTP_201_CREATED)



def suspend_marketer(request, marketerId):
    try:
       marketer = Marketer.objects.get(id=marketerId)
    except:   
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["get"]:
        
        serializer = MarketerSerializer(marketer)
       
        return Response(serializer.data, status=status.HTTP_201_CREATED)

def delete_marketer_account_by_staff(request,marketerId):
    try:
       marketer = Marketer.objects.get(id=marketerId)
    except:   
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["delete"]:

        marketer.delete()
        return Response(status=status.HTTP_202_ACCEPTED)
           

class GetOrders(ListAPIView):
   

    serializer_class = OrdersSerializer
           

    search_field = (
        "id",
        "status",
        "orderId",
        "ordered",
        "payment_type",
        "ordered_date",
    )

    filter_backends = [SearchFilter, OrderingFilter]
    ordering_fields = ["orderId","ordered_date"]


    def get_queryset(self):
        return Order.objects.all()

    def get_serializer_context(self):
        return {"request": self.request}


class CommentList(ListCreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class CommentDetail(RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer



def get_stores(request):
    try:
        store = Store.objects.all().order_by("user").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == methods["get"]:
        serializer = StoreSerializer(store, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



def get_store_by_staff(request, storeId):
    try:
        store = Store.objects.filter(id=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == methods["get"]:
        serializer_context = {"request": request}
        serializer = StoreSerializer(store, context=serializer_context, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)
    
    

def get_store_addresses_by_staff(request, storeId):
    try:
        store = StoreAddress.objects.filter(store=storeId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == methods["get"]:
     
        serializer = StoreAddressSerializer(store, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)    