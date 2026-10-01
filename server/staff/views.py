
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination


from affiliates.models import Marketer
from affiliates.serializers import MarketerSerializer
from notification.views import refund_requested_nofication, store_moderation_notification
from store.serializers import StoreAddressSerializer

from staff.serilalizers import (
    BackofficeCouponSerializer,
    BackofficeOrderSerializer,
    BackofficeStoreSerializer,
    CommentSerializer,
    DashboardQuerySerializer,
    StaffPermissionSerializer,
    StaffUserSerializer,
    StoreModerationSerializer,
)

from staff.models import Comment
from payment.models import Coupon, Order
from payment.serializers import CouponSerializer, OrdersSerializer


from django.contrib.sites.shortcuts import get_current_site

from rest_framework.generics import RetrieveUpdateDestroyAPIView, ListCreateAPIView
from rest_framework import viewsets
from core.serializers import UserSerializer, RefundsSerializer, StoreSerializer, StaffSerializer, AdminSerializer
from utils.functions import auth_token, send_mail, TokenGenerator
from utils.variables import methods
from core.models import User, Refund
from product.models import Product, Specification
from product.cache import invalidate_product_cache
from store.models import StoreAddress, Store
from observability.models import LogEntry
from observability.serializers import LogEntrySerializer


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

class BackofficePagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


class StaffViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]
    pagination_class = BackofficePagination
    filter_backends = [SearchFilter, OrderingFilter]

    @action(detail=False, methods=["get"], url_path="logs")
    def logs(self, request):
        queryset = LogEntry.objects.all()
        search = request.query_params.get("search")
        level = request.query_params.get("level")
        category = request.query_params.get("category")
        service = request.query_params.get("service")
        route = request.query_params.get("route")
        if search:
            queryset = queryset.filter(Q(message__icontains=search) | Q(logger__icontains=search) | Q(request_id__icontains=search))
        if level:
            queryset = queryset.filter(level=level.upper())
        if category:
            queryset = queryset.filter(category=category)
        if service:
            queryset = queryset.filter(service=service)
        if route:
            queryset = queryset.filter(route__icontains=route)
        if request.query_params.get("from"):
            queryset = queryset.filter(occurred_at__gte=request.query_params["from"])
        if request.query_params.get("to"):
            queryset = queryset.filter(occurred_at__lte=request.query_params["to"])
        return self.paginate_response(queryset, LogEntrySerializer)

    @action(detail=False, methods=["get"], url_path="logs/facets")
    def log_facets(self, request):
        return Response({
            "levels": list(LogEntry.objects.order_by().values_list("level", flat=True).distinct()),
            "categories": list(LogEntry.objects.order_by().values_list("category", flat=True).distinct()),
            "services": list(LogEntry.objects.order_by().values_list("service", flat=True).distinct()),
        })

    def paginate_response(self, queryset, serializer_class):
        page = self.paginate_queryset(queryset)
        serializer = serializer_class(page, many=True, context={"request": self.request})
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        query = DashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        days = query.validated_data["days"]
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)

        orders = Order.objects.filter(created__date__gte=start, created__date__lte=today)
        paid_orders = orders.filter(
            ordered=True,
            status__in=["confirmed", "shipped", "delivered", "picked up"],
        )
        order_total = paid_orders.aggregate(total=Sum("total"))["total"] or Decimal("0")

        return Response({
            "period": {"from": start, "to": today, "days": days},
            "users": {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True).count(),
                "staff": User.objects.filter(is_staff=True).count(),
                "new": User.objects.filter(created__date__gte=start).count(),
            },
            "stores": {
                "total": Store.objects.count(),
                "active": Store.objects.filter(status=Store.STATUS_ACTIVE).count(),
                "blocked": Store.objects.filter(status=Store.STATUS_BLOCKED).count(),
                "new": Store.objects.filter(created__date__gte=start).count(),
            },
            "products": {
                "total": Product.objects.count(),
                "published": Product.objects.filter(visibility=True).count(),
                "hidden": Product.objects.filter(visibility=False).count(),
                "out_of_stock": Product.objects.filter(available=0).count(),
                "sponsored": Product.objects.filter(sponsored=True).count(),
            },
            "orders": {
                "total": orders.count(),
                "ordered": orders.filter(ordered=True).count(),
                "by_status": list(
                    orders.order_by().values("status").annotate(count=Count("pk")).order_by("status")
                ),
                "gross_total": format(order_total, ".2f"),
            },
            "coupons": {
                "total": Coupon.objects.count(),
                "active": Coupon.objects.filter(active=True).count(),
            },
            "refunds": {
                "total": Refund.objects.count(),
                "accepted": Refund.objects.filter(accepted=True).count(),
                "pending": Refund.objects.filter(accepted=False).count(),
            },
            "marketers": {"total": Marketer.objects.count()},
            "recent_orders": BackofficeOrderSerializer(
                Order.objects.select_related("user").order_by("-created", "-pk")[:10],
                many=True,
            ).data,
            "top_stores": list(
                Store.objects.annotate(
                    products=Count("product", distinct=True),
                    orders=Count("product__cartitem__cart__order", distinct=True),
                )
                .order_by("-orders", "-products", "pk")
                .values("id", "name", "username", "status", "products", "orders")[:10]
            ),
        })

    @action(detail=False, methods=["get"])
    def users(self, request):
        users = User.objects.all().order_by("-created", "-pk")
        search = request.query_params.get("search")
        if search:
            users = users.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return self.paginate_response(users, StaffUserSerializer)

    @action(detail=False, methods=["get", "patch"], url_path=r"users/(?P<user_pk>\d+)")
    def user_detail(self, request, user_pk=None):
        user = get_object_or_404(User, pk=user_pk)
        if request.method == "GET":
            return Response(StaffUserSerializer(user).data)
        serializer = StaffPermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(user)
        return Response(StaffUserSerializer(user).data)

    @action(detail=False, methods=["get"])
    def stores(self, request):
        stores = Store.objects.select_related("user").order_by("-created", "-pk")
        store_status = request.query_params.get("status")
        if store_status:
            if store_status not in dict(Store.STATUS_CHOICES):
                return Response({"status": "Use active or blocked."}, status=status.HTTP_400_BAD_REQUEST)
            stores = stores.filter(status=store_status)
        search = request.query_params.get("search")
        if search:
            stores = stores.filter(
                Q(name__icontains=search)
                | Q(username__icontains=search)
                | Q(user__email__icontains=search)
            )
        return self.paginate_response(stores, BackofficeStoreSerializer)

    @action(detail=False, methods=["get"], url_path=r"stores/(?P<store_pk>\d+)")
    def store_detail(self, request, store_pk=None):
        store = get_object_or_404(Store.objects.select_related("user", "blocked_by"), pk=store_pk)
        return Response(BackofficeStoreSerializer(store, context={"request": request}).data)

    @action(detail=False, methods=["post"], url_path=r"stores/(?P<store_pk>\d+)/block")
    def block_store(self, request, store_pk=None):
        store = get_object_or_404(Store, pk=store_pk)
        serializer = StoreModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.block(store, request.user)
        for product in Product.objects.filter(store=store).only("id", "store_id"):
            invalidate_product_cache(product)
        store_moderation_notification(store, actor=request.user, blocked=True)
        return Response(BackofficeStoreSerializer(store).data)

    @action(detail=False, methods=["post"], url_path=r"stores/(?P<store_pk>\d+)/unblock")
    def unblock_store(self, request, store_pk=None):
        store = get_object_or_404(Store, pk=store_pk)
        serializer = StoreModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.unblock(store)
        for product in Product.objects.filter(store=store).only("id", "store_id"):
            invalidate_product_cache(product)
        store_moderation_notification(store, actor=request.user, blocked=False)
        return Response(BackofficeStoreSerializer(store).data)

    @action(detail=False, methods=["get"])
    def orders(self, request):
        orders = Order.objects.select_related("user").order_by("-created", "-pk")
        order_status = request.query_params.get("status")
        if order_status:
            if order_status not in dict(Order.ORDER_STATUS_CHOICE):
                return Response({"status": "Invalid order status."}, status=status.HTTP_400_BAD_REQUEST)
            orders = orders.filter(status=order_status)
        search = request.query_params.get("search")
        if search:
            orders = orders.filter(Q(orderId__icontains=search) | Q(user__email__icontains=search))
        return self.paginate_response(orders, BackofficeOrderSerializer)

    @action(detail=False, methods=["get", "post"])
    def coupons(self, request):
        if request.method == "GET":
            coupons = Coupon.objects.all().order_by("-created", "-pk")
            return self.paginate_response(coupons, BackofficeCouponSerializer)
        serializer = BackofficeCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
