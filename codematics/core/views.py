from django_filters import rest_framework
from django.conf import settings


from rest_framework import status
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.generics import ListAPIView, GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView


from core.permissions import EcommerceAccessPolicy
from core.utilities import get_auth_tokens_for_user, methods

from payment.models import Order
from core.models import Recent, Review, User, Wishlist
from product.models import Product, ProductImg

from product.serializers import (
    ProductCardSerializer,
    ProductImgSerializer,
    ProductSerializer,
)
from core.serializers import (
    AddressSerializer,
    CustomTokenObtainPairSerializer,
    RecentsPostSerializer,
    RecentsSerializer,
    RefundsSerializer,
    VerifyUserSerializer,
    ReviewsPostSerializer,
    ReviewsSerializer,
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
            return Response({"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            serializer = UserSerializer(data=data)

        if serializer.is_valid():
            # email = serializer.validated_data["email"]
            # password = serializer.validated_data["password"]
            # phone1 = serializer.validated_data["phone1"]
            # first_name = serializer.validated_data["first_name"]
            # last_name = serializer.validated_data["last_name"]
            # phone2 = serializer.validated_data.get("phone2", None)
            # gender = serializer.validated_data["gender"]

            # user = User.objects.create_user(
            #     email=email,
            #     password=password,
            #     first_name=first_name,
            #     last_name=last_name,
            #     phone1=phone1,
            #     phone2=phone2,
            #     gender=gender,
            # )

            # headers={"Authorization": auth_token}
            serializer.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["patch"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_user_detail(request, userId):
    data = JSONParser().parse(request)

    try:
        user = User.objects.get(pk=userId)
    except:
        return Response(status=404)

    if request.method == methods["patch"]:
        serializer = UserSerializer(user, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def delete_user_account(request, userId):
    try:
        user = User.objects.get(pk=userId)

    except:
        return Response(status=404)

    if request.method == methods["delete"]:
        user.delete()
        return Response(status=201)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_users(request):
    try:
        users = User.objects.all().order_by("created").reverse()
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, safe=False)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_user(request, userId):
    try:
        user = User.objects.get(pk=userId)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = UserSerializer(user)

    return Response(serializer.data, status=201)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["post"]])
def create_wishlist(request, userId, productId):
    try:
        wishlist = Wishlist.objects.get(productId=productId, user=userId)
    except:
        return Response(status=404)

    if request.method == methods["post"]:
        serializer = WishlistSerializer(wishlist)
        if wishlist.exists():
            wishlist.delete()
        else:
            if serializer.is_valid():
                serializer.save()
                return Response({"status": "successfully added"}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["get"]])
def get_wishlist_by_user_id(request, userId):
    try:
        wishlist = Wishlist.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = WishlistSerializer(wishlist, many=True)
        return Response(serializer.data, safe=False, status=status.HTTP_200_OK)


@permission_classes((EcommerceAccessPolicy,))
@api_view([methods["get"]])
def reviews_by_user_id(request, userId):
    try:
        reviews = Review.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ReviewsSerializer(reviews, many=True)
        return Response(serializer.data, safe=False)


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
            return Response(serializer.data)
        return Response(serializer.errors)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def recent_product_by_user(request, userId):
    try:
        recent = (
            Recent.objects.filter(user=userId)
            .prefetch_related("productId")
            .order_by("created")
            .reverse()
        )
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = RecentsSerializer(recent, many=True, context={"request": request})
        return Response(serializer.data, safe=False)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_recent(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = RecentsPostSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=201)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def orders_by_user(request, userId):
    try:
        orders = Order.objects.filter(user=userId).order_by("created").reverse()
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = OrdersSerializer(orders, many=True)
        return Response(serializer.data, safe=False)


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
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = RecentsSerializer(recent, many=True)
        return Response(serializer.data, safe=False)


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
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = RecentsSerializer(recent, many=True)
        return Response(serializer.data, safe=False)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def product_list(request):
    if request.method == methods["get"]:
        products = Product.objects.all().order_by("created").reverse()
        serializer = ProductSerializer(
            products, context={"request": request}, many=True
        )
        return Response(serializer.data, safe=False)


@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def productcard_by_id(request, id):
    try:
        product = Product.objects.prefetch_related("productId").get(pk=id)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ProductCardSerializer(product)
        return Response(serializer.data)
    elif request.method == methods["delete"]:
        product.delete()
        return Response(status=201)


@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def product_by_id(request, id):
    try:
        product = Product.objects.prefetch_related("productId").get(pk=id)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ProductCardSerializer(product)
        return Response(serializer.data)
    elif request.method == methods["delete"]:
        product.delete()
        return Response(status=201)


@api_view([methods["get"], methods["put"]])
@permission_classes((EcommerceAccessPolicy,))
def product_image_list(request):
    if request.method == methods["get"]:
        productImages = ProductImg.objects.all()
        serializer = ProductImgSerializer(productImages, many=True)
        return Response(serializer.data, safe=False)

    elif request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = ProductImgSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def product_images_by_product_id(request, productId):
    try:
        productImg = ProductImg.objects.filter(productId=productId)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ProductImgSerializer(productImg, many=True)
        return Response(serializer.data, safe=False)


@api_view([methods["get"], methods["delete"]])
@permission_classes((EcommerceAccessPolicy,))
def product_image_by_id(request, id):
    try:
        productImg = ProductImg.objects.filter(pk=id)
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ProductImgSerializer(productImg)
        return Response(serializer.data)

    elif request.method == methods["delete"]:
        productImg.delete()
        return Response(status=201)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def create_address(request):
    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = AddressSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=201)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def edit_review_by_product_id(request, productId):
    try:
        review = Review.objects.get(productId=productId)
    except:
        return Response(status=404)

    if request.method == methods["post"]:
        data = JSONParser().parse(request)
        serializer = ReviewsPostSerializer(data=data)
        if serializer.is_valid():
            review.rate(serializer.validated_data["rating"])
            serializer.save()
            review.set_avg_rating()

    elif request.method == methods["delete"]:
        review.delete()
        return Response(status=201)


@api_view([methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def get_reviews_by_product_id(request, productId):
    try:
        product = (
            Review.objects.filter(productId=productId).order_by("created").reverse()
        )
    except:
        return Response(status=404)

    if request.method == methods["get"]:
        serializer = ReviewsSerializer(product, many=True)
        return Response(serializer.data, safe=False)


class search_productListView(ListAPIView):
    permission_classes = (EcommerceAccessPolicy,)
    queryset = Product.objects.all()
    serializer = ProductSerializer()
    search_field = (
        "title",
        "description",
        "category",
        "discount",
        "average_rating",
        "tags",
        "store",
    )
    filter_backends = SearchFilter
    paginate_by = 15


# @permission_classes(AllowAny,)
# def filter_all_max_rating(request, minprice, maxprice, minrating, categories, colors):
#     try:
#         products = Product.objects.filter(price__range(minprice, maxprice)).filter(
#             categories=categories).filter(rating__get(minrating)).filter(colors=colors)
#     except:
#         return Response(status=404)

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
        return Response(status=201)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class Reset_password(GenericAPIView):
    serializer_class = VerifyUserSerializer
    permission_classes = (EcommerceAccessPolicy,)

    def post(self, request):
        data = {"request": request, "data": request.data}
        serializer = self.serializer_class(data=data)


class Password_token_checkAPI(GenericAPIView):
    permission_classes = (EcommerceAccessPolicy,)

    def get(self, request, uidb64, token):
        pass


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@api_view([methods["post"], methods["get"]])
@permission_classes((EcommerceAccessPolicy,))
def usps_estimate_delivery(request, service, origin_zip, destination_zip):
    usps_api_route = f'https://secure.shippingapis.com/ShippingAPI.dll?API=FirstClassMail&XML=<FirstClassMailRequest USERID="{settings.USPS_USERNAME}"> <OriginZip>{origin_zip}</OriginZip> <DestinationZip>{destination_zip}</DestinationZip><FirstClassMailRequest>'

    return usps_api_route.text


@api_view([methods["post"]])
@permission_classes((EcommerceAccessPolicy,))
def UserLogout(request):
    if request.method == methods["post"]:
        try:
            refresh_token = request.POST.get["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=205)
        except:
            return Response(status=404)
