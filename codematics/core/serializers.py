from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.contrib.auth import password_validation


from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainSerializer
from rest_framework.response import Response
from rest_framework import serializers


from store.models import Store
from core.models import Address, Recent, Review, User, Wishlist


from core.utilities import generate_token, send_mail,get_auth_tokens_for_user
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
            user = User.objects.create_user(password=validated_data.password,**validated_data)
            headers={"Authorization": get_auth_tokens_for_user}
            return user
        
        


class RefundsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
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


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
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


class VerifyUserSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150)

    class Meta:
        fields = ["email"]

        def validate(self, attrs):
            email = attrs["data"].get("email", "")
            mode = attrs["data"].get("mode", "signup")

            if mode == "signup":
                user = User.objects.get(email=email)
                uidb64 = urlsafe_base64_encode(user.id)
                token = str(generate_token.make_token(user))
                current_domain = get_current_site(
                    request=attrs["data"].get("request")
                ).domain
                relative_link = reverse("email-verify")
                absolute_url = f"https://{current_domain}\{relative_link}?token={token}"
                data = {"firstname": user.firstname, "absolute_url": absolute_url}
                send_mail("onboarding-user", user.email, data=data)

            else:
                try:
                    user = User.objects.get(email=email)
                    uidb64 = urlsafe_base64_encode(user.id)
                    token = str(generate_token.make_token(user))
                    current_domain = get_current_site(
                        request=attrs["data"].get("request")
                    ).domain
                    relative_link = reverse("email-verify")
                    absolute_url = (
                        f"https://{current_domain}\{relative_link}?token={token}"
                    )
                    data = {"firstname": user.firstname, "absolute_url": absolute_url}
                    send_mail("password-reset", user.email, data=data)
                except:
                    Response("Account does not exist", status=404)


class UserMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email"]


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "user", "username", "name", "created"]


class StoreInfoForProductCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["url", "name"]


class WishlistSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source="productId")

    class Meta:
        model = Wishlist
        fields = ["liked", "product_details"]


class WishlistPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wishlist
        fields = ["user", "productId"]


class RecentsSerializer(serializers.ModelSerializer):
    product_details = ProductCardSerializer(source="productId")
    # store_info = StoreInfoForProductCardSerializer(source="productId")

    class Meta:
        model = Recent
        fields = [
            "product_details",
            #   "store_info"
        ]


class RecentsPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recent
        fields = ["productId", "user"]


class ReviewsSerializer(serializers.ModelSerializer):
    user_details = UserMailSerializer(source="user", read_only=True)

    class Meta:
        model = Review
        fields = [
            "user_details",
            "user",
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
