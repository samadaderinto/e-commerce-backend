from django.shortcuts import render
from django.contrib.auth.models import Group

from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from payment.models import Coupon

from payment.serializers import CouponSerializer


from core.serializers import UserSerializer, VerifyUserSerializer
from core.permissions import EcommerceAccessPolicy
from core.utilities import auth_token, methods, send_mail
from core.models import User


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
            serializer.validated_data()
            serializer.create(serializer)
            send_mail("welcome", serializer.validated_data["email"], None)
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
        return Response(serializer.data, safe=False,status=status.HTTP_200_OK)


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
        return Response(serializer.data, safe=False,status=status.HTTP_200_OK)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_coupon(request, codeId):
    try:
        coupons = Coupon.objects.get(pk=codeId)
    except:
        return Response(status=404)

    if request.method == methods["delete"]:
        coupons.delete()
    return Response(status=status.HTTP_200_OK)


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


@api_view([methods["post"], methods["patch"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_coupon(request, code):
    if request.method == methods["patch"]:
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
        return Response(serializer.data,status=status.HTTP_200_OK)