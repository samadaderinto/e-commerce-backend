from django_filters import rest_framework
from django.conf import settings
from django.utils.encoding import (
    smart_str,
    force_str,
    smart_bytes,
    DjangoUnicodeDecodeError,
)
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework_simplejwt.views import TokenObtainPairView


from core.permissions import EcommerceAccessPolicy
from core.utilities import auth_token, methods, send_mail

from payment.models import Order
from core.models import Recent, Review, User, Wishlist




from core.serializers import (
    AddressSerializer,
    CustomTokenObtainPairSerializer,
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
            return Response({"error": "Email already registered"},status=status.HTTP_400_BAD_REQUEST)
        else:
            serializer = UserSerializer(data=data)

        if serializer.is_valid():
            user = serializer.save()
            VerifyUserSerializer(data)
            token = auth_token(user)

            return Response(serializer.data, headers={"Authorization": token}, status=status.HTTP_201_CREATED)
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
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["post"]:
        serializer = WishlistSerializer(wishlist)
        if wishlist.exists():
            wishlist.delete()
        else:
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"status": "successfully added"}, status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["get"]])
def get_wishlist_by_user_id(request, userId):
    try:
        wishlist = Wishlist.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = WishlistSerializer(wishlist, many=True)
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["get"]])
def reviews_by_user_id(request, userId):
    try:
        reviews = Review.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ReviewsSerializer(reviews, many=True)
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["post"]])
def create_review(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)

        user = data.get("user")
        productId = data.get("productId")
        rate = data.get("rating")
        serializer = ReviewsPostSerializer(data=data)

        if serializer.is_valid():
            try:
                review = Review.objects.get(user=user, productId=productId)
            except:
                serializer.save()
                return Response(serializer.data)

            review = Review.objects.get(user=user, productId=productId)

            serializer = ReviewsPostSerializer(review, data=data)
            if serializer.is_valid():
                serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_recent(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = RecentsPostSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def orders_by_user(request, userId):
    try:
        orders = Order.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = OrdersSerializer(orders, many=True)
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def orders_by_user_and_status(request, userId, status):
    try:
        recent = (
            Recent.objects.filter(user=userId)
            .filter(status=status)
            .order_by("created")
            .prefetch_related("productId")
            .order_by("created")
            .reverse()
        )
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RecentsSerializer(recent, many=True)
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def orders_by_user_and_status_and_id(request, userId, status, id):
    try:
        recent = (
            Recent.objects.filter(user=userId)
            .filter(status=status)
            .get(pk=id)
            .prefetch_related("productId")
        )
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = RecentsSerializer(recent, many=True)
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)



@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_address(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = AddressSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_review_by_product_id(request, productId):
    try:
        review = Review.objects.get(productId=productId)
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = ReviewsPostSerializer(data=data)
        if serializer.is_valid():
            review.rate(serializer.validated_data["rating"])
            serializer.save()
            review.set_avg_rating()

    elif request.method == methods["delete"]:
        review.delete()
        return Response(status=status.HTTP_202_ACCEPTED)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_reviews_by_product_id(request, productId):
    try:
        product = (
            Review.objects.filter(productId=productId).order_by("created").reverse()
        )
    except:
        return Response(status.HTTP_404_NOT_FOUND)

    if request.method == methods["get"]:
        serializer = ReviewsSerializer(product, many=True)
        return Response(serializer.data, safe=False)




# @permission_classes(AllowAny,)
# def filter_all_max_rating(request, minprice, maxprice, minrating, categories, colors):
#     try:
#         products = Product.objects.filter(price__range(minprice, maxprice)).filter(
#             categories=categories).filter(rating__get(minrating)).filter(colors=colors)
#     except:
#         return Response(status.HTTP_404_NOT_FOUND)

#     if request.method == methods["get"]:
#         serializer = ProductSerializer(products, many=True)
#         return Response(serializer.data, safe=False)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def request_refund(request):
    data = JSONParser().parse(request)
    serializer = RefundsSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(status=status.HTTP_202_ACCEPTED)
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
                {"success": True,
                "message": "Credentials Valid",
                "uidb64": uidb64,
                "token": token},
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
    
    
    def patch(self,request):
        serializer=self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        Response(
                {"sucess": True,"message": "Password reset successful"},
                status=status.HTTP_200_OK,
            )
        
class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@api_view([methods["post"], methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def usps_estimate_delivery(request, service, origin_zip, destination_zip):
    usps_api_route = f'https://secure.shippingapis.com/ShippingAPI.dll?API=FirstClassMail&XML=<FirstClassMailRequest USERID="{settings.USPS_USERNAME}"> <OriginZip>{origin_zip}</OriginZip> <DestinationZip>{destination_zip}</DestinationZip><FirstClassMailRequest>'

    return usps_api_route.text

class UserLogout(GenericAPIView):
    """
    An endpoint to logout users.
    """

    permission_classes = (EcommerceAccessPolicy,)

    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except:
            return Response(status=status.HTTP_400_BAD_REQUEST)
