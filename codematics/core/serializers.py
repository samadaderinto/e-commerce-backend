from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.utils.encoding import (
    smart_str,
    force_str,
    smart_bytes,
    force_bytes,

    DjangoUnicodeDecodeError
)
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainSerializer
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from phonenumber_field.serializerfields import PhoneNumberField


from store.models import Store
from core.models import Address, Recent, Review, User, Wishlist, Refund, Device


from core.utilities import TokenGenerator, send_mail
from product.serializers import ProductSerializer, ProductCardSerializer


class UserAuthSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone1",
            "phone2",
            "gender",
            "password",
            "created",
            "updated",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

        def create(self, validated_data):
            user = User.objects.create_user(**validated_data)
            user.make_password(self.password)
            user.save()

            return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone1",
            "phone2",
            "gender",
            "created",
            "updated",
        ]
   

        
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    
class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    
class StaffSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone1",
            "phone2",
            "gender",
            "is_staff",
            "password",
            "created",
            "updated",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

        def create(self, validated_data):
            user = User.objects.create_staffuser(**validated_data)
            user.set_password(self.password)
            user.save()

            return user



class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone1",
            "phone2",
            "gender",
            "is_staff",
            "is_superuser",
            "password",
            "created",
            "updated",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

        def create(self, validated_data):
            user = User.objects.create_superuser(**validated_data)
            user.set_password(self.password)
            user.save()

            return user

        def update(self, instance, validated_data):

            password = validated_data.pop('password', None)

            for (key, value) in validated_data.items():
                setattr(instance, key, value)

            if password is not None:
                instance.set_password(password)

            instance.save()

            return instance


class RefundsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = [
            "id",
            "email",
            "order",
            "reason",
            'created',
        ]


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "user",
            "address",
            "zip",
            "country",
            "state",
            "city",
            "is_default",
            "created",
            "updated",
        ]


class SetNewPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=6, max_length=90, write_only=True)
    token = serializers.CharField(min_length=6, max_length=90, write_only=True)
    uidb64 = serializers.CharField(min_length=6, max_length=90, write_only=True)

    fields = ["password", "token", "uidb64"]

    def validate(self, attrs):
        try:
            password = attrs.get("password")
            token = attrs.get("token")
            uidb64 = attrs.get("uidb64")
            id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=id)
            if not PasswordResetTokenGenerator().check_token(user, token):
                raise AuthenticationFailed(
                    "The reset link is invalid", status.HTTP_401_UNAUTHORIZED
                )
            user.set_password(password)
            user.save()
        except:
            raise AuthenticationFailed(
                "The reset link is invalid", status.HTTP_401_UNAUTHORIZED
            )
        return super().validate(attrs)



class UserMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name"]


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "user", "username", "name", "created"]


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer(source="product")

    class Meta:
        model = Wishlist
        fields = ["product"]


class CreateWishlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wishlist
        fields = ["user", "product"]


class RecentsSerializer(serializers.ModelSerializer):
    product_info = ProductCardSerializer(source="product")

    class Meta:
        model = Recent
        fields = ["product_info"]


class CreateRecentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recent
        fields = ["product", "user"]


class ReviewsSerializer(serializers.ModelSerializer):
    name = UserMailSerializer(source="user", read_only=True)

    class Meta:
        model = Review
        fields = [
            "name",
            "product",
            "label",
            "comment",
            "rating",
            "created",
            "updated",
        ]

    extra_kwargs = {"user_details": {"read_only": True}}


class CreateReviewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = [
            "user",
            "product",
            "label",
            "comment",
            "rating",
            "created",
            "updated",
        ]
        
    
    def create(self, validated_data):
        
        return Review.objects.create(**validated_data)
       
          
            


class EmailTokenObtainSerializer(TokenObtainSerializer):
    username_field = User.EMAIL_FIELD


class CustomTokenObtainPairSerializer(EmailTokenObtainSerializer):
    @classmethod
    def get_token(cls, user):
        if user.is_active:
           return RefreshToken.for_user(user)
        else:
           return Response({"message": "Please verify your account first"})

    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)

        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)

        return data


class DeviceSerializer(serializers.ModelSerializer):

    class Meta:
        model = Device
        fields = [
            "user",
            "device_ip"
            "type",
            "version",
            "verified",
            "last_login",
        ]
