from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.contrib.auth import password_validation
from django.utils.encoding import (
    smart_str,
    force_str,
    smart_bytes,
    DjangoUnicodeDecodeError,
)
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.hashers import make_password
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainSerializer
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed



from store.models import Store
from core.models import Address, Recent, Review, User, Wishlist, Refund, Device


from core.utilities import generate_token, send_mail
from product.serializers import ProductSerializer, ProductCardSerializer


class UserSerializer(serializers.ModelSerializer):
    # note: alternative to extra_kwargs
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)

    #     self.fields['password'].write_only = True

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
            user.set_password(self.password)
            user.save()

            return user
        
        def create_admin(self, validated_data):
            user = User.objects.create_superuser(**validated_data)
            user.set_password(self.password)
            user.save()

            return user
        
        def create_staff(self, validated_data):
            user = User.objects.create_staffuser(**validated_data)
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
            "has_perm",
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
        
        def update(self, instance, validated_data):

            password = validated_data.pop('password', None)

            for (key, value) in validated_data.items():
                setattr(instance, key, value)

            if password is not None:
                instance.set_password(password)

            instance.save()

            return instance


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
            "userId",
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


class VerifyUserSerializer(serializers.Serializer):

    class Meta:
        fields = ["email"]

        def validate(self, data):
            email = data.get("email", "")
            request = data.get("request")
            user = User.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(user.id)
            token = PasswordResetTokenGenerator().make_token(user)
            current_site = get_current_site(request).domain
            relativeLink = reverse(
                "password-reset-confirm", kwargs={"uidb64": uidb64, "token": token}
            )
            absolute_url = f"http://{current_site}{relativeLink}"
            data = {"firstname": user.firstname, "absolute_url": absolute_url}

            send_mail("onboarding-user", user.email, data=data)
            return data


class UserMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name"]


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "user", "username", "name", "created"]



class WishlistSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer(source="productId")

    class Meta:
        model = Wishlist
        fields = ["liked", "product"]


class WishlistPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wishlist
        fields = ["user", "productId"]


class RecentsSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer(source="productId")

    class Meta:
        model = Recent
        fields = ["product"]


class RecentsPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recent
        fields = ["productId", "user"]


class ReviewsSerializer(serializers.ModelSerializer):
    name = UserMailSerializer(source="user", read_only=True)

    class Meta:
        model = Review
        fields = [
            "name",
            "productId",
            "label",
            "comment",
            "rating",
            "created",
            "updated",
        ]

    extra_kwargs = {"user_details": {"read_only": True}}


class ReviewsPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = [
            "user",
            "productId",
            "label",
            "comment",
            "rating",
            "created",
            "updated",
        ]


class EmailTokenObtainSerializer(TokenObtainSerializer):
    username_field = User.EMAIL_FIELD


class CustomTokenObtainPairSerializer(EmailTokenObtainSerializer):
    @classmethod
    def get_token(cls, user):
        return RefreshToken.for_user(user)

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
        
    




  
