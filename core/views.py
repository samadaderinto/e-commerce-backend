from django.shortcuts import render
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView


from django_filters import rest_framework as djfilter
from django.db import transaction
from django.conf import settings

from core.permissions import IsStoreOwnerOrReadOnly, IsStaffEditor,IsUserOrReadOnly
from core.utilities import get_tokens_for_user, methods

# from payment.models import Order
from core.models import User


from cart.serializers import ProductCardSerializer, ProductImgSerializer, ProductPriceRangeFilter, ProductSerializer
from core.serializers import AddressSerializer, CustomTokenObtainPairSerializer, RecentsPostSerializer, RecentsSerializer, RefundsSerializer, VerifyUserSerializer, ReviewsPostSerializer, ReviewsSerializer, UserSerializer, WishlistSerializer, RefreshToken
# from payment.serializers import OrdersSerializer
# Create your views here.

@api_view([methods.post])
@permission_classes([AllowAny])
def create_user(request):
    if request.method == methods.post:
        data = JSONParser().parse(request)
        serializer = UserSerializer(data=data)
        if serializer.is_valid():

            email = serializer.validated_data["email"]
            password = serializer.validated_data["password"]
            phone1 = serializer.validated_data["phone1"]
            firstname = serializer.validated_data["firstname"]
            lastname = serializer.validated_data["lastname"]
            phone2 = serializer.validated_data.get("phone2", None)
            gender = serializer.validated_data["gender"]

            
            if User.objects.get(email=email).exists():
                return Response("Account already exist", status=301)
            else:
                user = User.objects.create_user(
                    email=email, password=password, firstname=firstname, lastname=lastname, phone1=phone1, phone2=phone2, gender=gender)
                VerifyUserSerializer.validate(data=data)
                auth_token = get_tokens_for_user(user)

            return Response(serializer.data, status=201, headers={"Authorization": auth_token})
        return Response(serializer.errors, status=400)
    
    
    