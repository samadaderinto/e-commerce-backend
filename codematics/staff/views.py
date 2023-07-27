from django.shortcuts import render
from django.contrib.auth.models import Group


from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from payment.models import Coupon

from payment.serializers import CouponSerializer


from core.serializers import UserSerializer, VerifyUserSerializer
from core.permissions import EcommerceAccessPolicy
from core.utilities import get_auth_tokens_for_user, methods, send_mail
from core.models import User


# Create your views here.


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_staff(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            password = serializer.validated_data["password"]
            phone1 = serializer.validated_data["phone1"]
            phone2 = serializer.validated_data.get("phone2", None)
            firstname = serializer.validated_data["firstname"]
            lastname = serializer.validated_data["lastname"]
            gender = serializer.validated_data["gender"]

            if User.objects.filter(email=email).exists():
                return Response("email already exist", status=301)
            else:
                VerifyUserSerializer.validate(data=data)
                user = User.objects.create_staffuser(
                    email=email,
                    password=password,
                    firstname=firstname,
                    lastname=lastname,
                    phone1=phone1,
                    phone2=phone2,
                    gender=gender,
                )
                auth_token = get_auth_tokens_for_user(user)
            return Response(
                serializer.data,
                status=201,
                headers={"Authorization": auth_token},
                message="Account successfully created, permissions may be granted within 1 to 3 business days",
            )
        return Response(serializer.errors, status=400)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def give_staff_permission(request):
    data = JSONParser().parse(request)
    serializer = UserSerializer(data=data)
    if serializer.is_valid():
        email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email, is_superuser=True)
        user.groups.add(Group.objects.get(name="staff"))
    except:
        return Response(status=404)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_staff_detail(request, userId):
    data = JSONParser().parse(request)

    try:
        user = User.objects.get(pk=userId, email=data.get("email"), is_superuser=True)
    except:
        return Response(status=404)

    if request.method == methods["post"]:
        serializer = UserSerializer(user, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_staff_account(request):
    if request.method == methods["delete"]:
        data = JSONParser().parse(request)
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            serializer.validated_data()
            serializer.create(serializer)
            send_mail("welcome", serializer.validated_data["email"], None)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


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
        return Response(status=404)


@api_view([methods["get"], methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def get_staffs(request):
    if request.method == methods["get"]:
        staffs = User.objects.all().order_by("created").reverse()
        serializer = UserSerializer(staffs, many=True)
        return Response(serializer.data, safe=False)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["get"]])
def get_staff(request, userId):
    staff = User.objects.get(pk=userId, is_staff=True)
    if request.method == methods["get"]:
        serializer = User(staff)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_coupons(request):
    try:
        coupons = Coupon.objects.all()
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = CouponSerializer(coupons, many=True)
        return Response(serializer.data, safe=False)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_coupon(request, codeId):
    try:
        coupons = Coupon.objects.get(pk=codeId)
    except:
        return Response(status=404)

    if request.method == methods["delete"]:
        coupons.delete()
    return Response(status=201)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_coupon(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = CouponSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


@api_view([methods["post"], methods["patch"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_coupon(request, code):
    if request.method == methods.patch:
        queryset = Coupon.objects.filter(code=code)
        serializer = CouponSerializer(queryset)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)
