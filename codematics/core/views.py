from django.conf import settings
from django.shortcuts import redirect
from django.utils.encoding import smart_str
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.paginator import Paginator


from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.generics import GenericAPIView
from rest_framework_simplejwt.views import TokenObtainPairView
from affiliates.models import Redirect, Url
from affiliates.serializers import RedirectSerializer


from core.permissions import EcommerceAccessPolicy
from core.utilities import auth_token, methods, send_mail

from payment.models import Order
from core.models import Recent, Review, User, Wishlist, Address


from core.serializers import (
    AddressSerializer,
    CustomTokenObtainPairSerializer,
    WishlistPostSerializer,
    RecentsPostSerializer,
    RecentsSerializer,
    RefundsSerializer,
    VerifyUserSerializer,
    ReviewsPostSerializer,
    ReviewsSerializer,
    SetNewPasswordSerializer,
    UserSerializer,
    WishlistSerializer,
    RefreshToken,
)
from payment.serializers import OrdersSerializer


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_user(request):
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


@api_view([methods["put"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_user_detail(request, userId):
    data = JSONParser().parse(request)

    try:
        user = User.objects.get(pk=userId, email=data.get("email"))
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["put"]:
        serializer = UserSerializer(user, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_user_account(request, userId):
    data = JSONParser().parse(request)
    try:
        user = User.objects.get(pk=userId, email=data.get("email"))

    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        user.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_user(request, userId):
    try:
        user = User.objects.get(pk=userId)
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = UserSerializer(user)

        return Response(serializer.data, status=status.HTTP_200_OK)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["post"]])
def create_wishlist(request, userId, productId):
    try:
        wishlist = Wishlist.objects.get(productId=productId, user=userId)
    except:
        data = {"productId": productId, "user": userId}
        serializer = WishlistPostSerializer(data=data)
        if serializer.is_valid():
            serializer.save()

        return Response(
            {"success": "Added to wishlist"}, status=status.HTTP_201_CREATED
        )

    if request.method == methods["post"]:
        wishlist.delete()
        return Response(
            {"success": "Removed from wishlist"}, status=status.HTTP_202_ACCEPTED
        )


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["get"]])
def get_wishlist(request, userId):
    try:
        wishlist = Wishlist.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        page_number = request.GET.get("offset", 1)
        per_page = request.GET.get("limit", 15)
        paginator = Paginator(wishlist, per_page=per_page)
        items = paginator.get_page(number=page_number)

        serializer = WishlistSerializer(items, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["get"]])
def get_reviews(request, userId):
    try:
        reviews = Review.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        page_number = request.GET.get("offset", 1)
        per_page = request.GET.get("limit", 15)
        paginator = Paginator(reviews, per_page=per_page)
        items = paginator.get_page(number=page_number)
        serializer = ReviewsSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["post"]])
def create_review(request):
    if request.method == methods["post"]:
        # will add checker so only user who bought product can create review
        data = JSONParser().parse(request)
        user = data.get("user")
        productId = data.get("productId")
        serializer = ReviewsPostSerializer(data=data)

        if serializer.is_valid():
            try:
                review = Review.objects.get(user=user, productId=productId)
            except:
                # create review
                serializer.save()
                review = Review.objects.get(user=user, productId=productId)
                # update product rating
                review.set_avg_rating()
                return Response(serializer.data, status=status.HTTP_201_CREATED)

            # update review
            serializer = ReviewsPostSerializer(review, data=data)
            if serializer.is_valid():
                serializer.save()
                # update product rating
                review.set_avg_rating()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_review(request, userId, productId):
    try:
        review = Review.objects.get(user=userId, productId=productId)
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        review.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_recent(request, productId, userId):
    if request.method == methods["post"]:
        data = {"productId": productId, "user": userId}
        serializer = RecentsPostSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_recents(request, userId):
    try:
        recent = Recent.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        page_number = request.GET.get("offset", 1)
        per_page = request.GET.get("limit", 15)
        paginator = Paginator(recent, per_page=per_page)
        items = paginator.get_page(number=page_number)
        serializer = RecentsSerializer(items, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class Orders(ListAPIView):
    permission_classes = (EcommerceAccessPolicy,)

    serializer_class = OrdersSerializer

    search_field = (
        "id",
        "status",
        "orderId",
        "ordered_date",
    )

    filter_backends = [SearchFilter, OrderingFilter]
    ordering_fields = ["ordered_date"]

    paginate_by = 20

    def get_queryset(self):
        return Order.objects.all(user=self.request.data["userId"])

    def get_serializer_context(self):
        return {"request": self.request}


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_address(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = AddressSerializer(data=data)
        if serializer.is_valid():
            # line of code will not work as expected
            # i am trying to create address by setting default address to false and set new address with
            # is_default as Tru to new default and also make sure if it is the first created address, it will become default
            if serializer.validated_data.get("is_default", False) == True:
                try:
                    default_address = Address.objects.get(
                        user=serializer.validated_data["user"], is_default=True
                    )
                    default_address.is_default = False
                    default_address.save()
                    serializer.save()
                except:
                    serializer.save()
                    return Response(status=status.HTTP_202_ACCEPTED)
            else:
                serializer.save()
                return Response(status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["put"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_address(request, userId):
    data = JSONParser().parse(request)

    try:
        user = Address.objects.filter(user=userId, id=data["id"])
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["put"]:
        serializer = AddressSerializer(user, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_address(request, userId, AddressId):
    try:
        user = Address.objects.get(user=userId, id=AddressId)

    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["delete"]:
        user.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def request_refund(request):
    data = JSONParser().parse(request)
    serializer = RefundsSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        user = User.objects.get(id=serializer.validated_data["user"])
        email = user.email
        data = {
            "firstname": user.first_name,
            "order": serializer.validated_data["order"],
            "product": [],
            "created": serializer.validated_data["created"],
        }
        send_mail("refund-request-acknowledged", email, data=data)
        return Response(
            {
                "message": "Refund accepted, this may take 3 to 7 business days before you get a response"
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPassword(GenericAPIView):
    serializer_class = VerifyUserSerializer
    permission_classes = (EcommerceAccessPolicy,)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        email = request.data["email"]

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(user.id)
            token = PasswordResetTokenGenerator().make_token(user)
            current_site = get_current_site(request).domain
            relativeLink = reverse(
                "password-reset-confirm", kwargs={"uidb64": uidb64, "token": token}
            )
            absurl = f"http://{current_site}{relativeLink}"

            email_body = f"Hi {user.username} Use link below to verify your email \n"

            data = {
                "email body": email_body,
                "to email": user.email,
                "email subject": "Verify your email",
            }
            # will put actual data later
            send_mail("onboarding-user", user.email, data=data)

        return Response(
            {"success": "We have sent you a link to reset your password"},
            status=status.HTTP_200_OK,
        )


class PasswordTokenCheckAPI(GenericAPIView):
    permission_classes = (EcommerceAccessPolicy,)

    def get(self, request, uidb64, token):
        try:
            id = smart_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=id)

            if not PasswordResetTokenGenerator().check_token(user, token):
                return Response(
                    {"error": "Token is not valid, please request a new one"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            return Response(
                {
                    "success": True,
                    "message": "Credentials Valid",
                    "uidb64": uidb64,
                    "token": token,
                },
                status=status.HTTP_200_OK,
            )

        except:
            Response(
                {"error": "Token is not valid, please request a new one"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class SetNewPassword(generics.GenericAPIView):
    serializer_class = SetNewPasswordSerializer
    permission_classes = (EcommerceAccessPolicy,)

    def patch(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        Response(
            {"sucess": True, "message": "Password reset successful"},
            status=status.HTTP_200_OK,
        )


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UserLogout(GenericAPIView):
    permission_classes = (EcommerceAccessPolicy,)

    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except:
            return Response(status=status.HTTP_400_BAD_REQUEST)


def redirect_url(request, marketerId, productId, identifier):
    data = {"marketer": marketerId, "product": productId, "identifier": identifier}
    serializer = RedirectSerializer(data=data)

    if serializer.is_valid():
        try:
            url = Url.objects.get(
                marketer=marketerId, product=productId, identifier=identifier
            )
        except:
            return Response(
                "Sorry link is broken or unable to get product :(",
                status=status.HTTP_403_FORBIDDEN,
            )
      
        serializer.save()
        return redirect(
            url.product_url,
            permanent=True,
            status=status.HTTP_308_PERMANENT_REDIRECT,
        )
