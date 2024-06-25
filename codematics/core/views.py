from django.utils.encoding import smart_str
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, get_list_or_404
from django.utils.encoding import smart_str, force_bytes

from utils.functions import TokenGenerator, auth_token, send_mail
from rest_framework_simplejwt.tokens import RefreshToken


from kink import di
from drf_spectacular.utils import extend_schema


from core.serializers import CreateRecentsSerializer, CreateReviewsSerializer, CreateWishlistSerializer, EmailSerializer, LoginSerializer, UserAuthSerializer
from core.models import Recent, Review, User, Wishlist, Address



from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework import viewsets
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.decorators import action

from payment.models import Order
from payment.serializers import OrdersSerializer
from notification.views import refund_requested_nofication
from core.serializers import AddressSerializer, RecentsSerializer, RefundsSerializer, ReviewsSerializer, SetNewPasswordSerializer, UserSerializer, WishlistSerializer





class AuthViewSet(viewsets.GenericViewSet):
    auth_user: User = di[User]
    
    def send_activation_mail(self, request, email):
        user = get_object_or_404(self.auth_user, email=email)
        uuidb64 = urlsafe_base64_encode(force_bytes(user.id))
        token = TokenGenerator().make_token(user)
        current_site = get_current_site(request).domain
        relativeLink = reverse('activate', kwargs={'uidb64': uuidb64, 'token': token})
        absolute_url = f"http://{current_site}{relativeLink}"
        send_mail("onboarding-user", user.email, data={"firstname": user.first_name, "absolute_url": absolute_url})
        
        
    @extend_schema(responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['get'], url_path='activate')
    def verify_activation(self, request, uidb64, token):
        
        id = smart_str(urlsafe_base64_decode(uidb64))
        user = get_object_or_404(self.auth_user, pk=id)

        if not TokenGenerator().check_token(user, token):
            return Response({'error': 'Token is not valid, please request a new one'}, status=status.HTTP_401_UNAUTHORIZED)
        user.is_active = True
        user.save()
        
        return Response({'message': 'Email verified, you can now login'}, status=status.HTTP_200_OK)
    
        
    @extend_schema(request=UserSerializer, responses={status.HTTP_201_CREATED: UserSerializer})
    @action(detail=False, methods=['post'], url_path='register')
    def create_user(self, request):
        data = JSONParser().parse(request)
        serializer = UserAuthSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        if self.auth_user.objects.filter(email=email).exists():
            return Response({'message': 'Email already registered'},status=status.HTTP_400_BAD_REQUEST)
        
        self.auth_user.objects.create_user(**data)
        self.send_activation_mail(request, email)
        return Response({"message": "User successfully created, Verify your email account"}, status=status.HTTP_201_CREATED)

    @extend_schema(request=LoginSerializer, responses={status.HTTP_200_OK: UserSerializer})
    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        data = JSONParser().parse(request)
        serializer = LoginSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(self.auth_user, email = data['email'])
        token = auth_token(user)
        return Response(headers={"Authorization": token}, status=status.HTTP_400_BAD_REQUEST)
    
    
    @extend_schema(request=LoginSerializer, responses={status.HTTP_200_OK: UserSerializer})
    @action(detail=False, methods=['post'], url_path='login/refresh')
    def login_token_refresh(self):
        return TokenRefreshView.as_view()
    
   
    @extend_schema(request=None, responses={status.HTTP_205_RESET_CONTENT: None})
    @action(detail=False, methods=['post'], url_path='logout')
    def logout(self, request):
        data = JSONParser().parse(request)
        try:
            RefreshToken(data['refresh']).blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except:
            return Response(status=status.HTTP_400_BAD_REQUEST)
    
    
    @extend_schema(request=EmailSerializer, responses={status.HTTP_200_OK: dict})
    @action(detail=False, methods=['post'], url_path='reset-password/request')
    def request_reset_password(self, request):
        data = JSONParser().parse(request)
        serializer = EmailSerializer(email = data['email'])
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = get_object_or_404(self.auth_user, email = data['email'])
        uidb64 = urlsafe_base64_encode(user.id.to_bytes())
        token = PasswordResetTokenGenerator().make_token(user)
        
        current_site = get_current_site(request).domain
        relativeLink = reverse('password_reset_confirmation', kwargs={'uidb64': uidb64, 'token': token})
        abs_url = f"http://{current_site}{relativeLink}"
        mail_data = {'absolute_url': abs_url, 'email': email}

        send_mail('password-reset', email, data=mail_data)

        return Response({'success': 'We have sent you a mail to reset your password'}, status=status.HTTP_200_OK)
        
    
    
    @extend_schema(request=None, responses={status.HTTP_200_OK: None})
    @action(detail=False, methods=['post'], url_path='reset-password/verify')
    def verify_password_reset_token(self, request, uidb64, token):
        
        id = smart_str(urlsafe_base64_decode(uidb64))
        user = get_object_or_404(self.auth_user, pk=id)

        if not PasswordResetTokenGenerator().check_token(user, token):
            return Response({'error': 'Token is not valid, please request a new one'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({'uidb64': uidb64, 'token': token}, status=status.HTTP_200_OK)

        
        
    @extend_schema(request=SetNewPasswordSerializer, responses={status.HTTP_205_RESET_CONTENT: None})
    @action(detail=False, methods=['post'], url_path='reset-password/')
    def reset_password(self, request):
        data = JSONParser().parse(request)
        serializer = SetNewPasswordSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        Response({'message': 'Password reset successful'}, status=status.HTTP_200_OK)
            
            
    


class UserViewSet(viewsets.GenericViewSet):
    auth_user: User = di[User]
    user_address: Address = di[Address]
    user_recents: Recent = di[Recent]
    user_wishlist: Wishlist = di[Wishlist]
    user_reviews: Review = di[Review]
    user_orders: Order = di[Order]
    
    
    
    @extend_schema(request=None, responses={status.HTTP_200_OK: UserSerializer})
    @action(detail=False, methods=['get'], url_path='get')
    def get_user(self, request):
        data = JSONParser().parse(request)
        user = get_object_or_404(self.auth_user, pk=data['id'])
        serializer = UserSerializer(user)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    @extend_schema(request=None, responses={status.HTTP_201_CREATED: UserSerializer})
    @action(detail=False, methods=['put'], url_path='update')
    def update_user(self, request):
        data = JSONParser().parse(request)
        user = get_object_or_404(self.auth_user, pk=data['id'], email=data['email'])
    
        serializer = UserSerializer(user, partial=True, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
    
    @extend_schema(request=None, responses={status.HTTP_202_ACCEPTED:  None})
    @action(detail=False, methods=['delete'], url_path='delete')
    def delete_user(self, request):
        data = JSONParser().parse(request)
        user = get_object_or_404(self.auth_user, pk=data['id'], email=data['email'])
        # will add some sort of verification here, like if user have an order to be delivered soon, the account wouldn't be deleted

        user.delete()
        return Response(status=status.HTTP_202_ACCEPTED)
    
    
    @extend_schema(request=AddressSerializer, responses={status.HTTP_202_ACCEPTED: AddressSerializer})
    @action(detail=False, methods=['post'], url_path='address/add')
    def create_address(self, request):
        data = JSONParser().parse(request)
        serializer = AddressSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        try:
            default_address = self.user_address.objects.get(self.user_address, user=serializer.validated_data['user'], is_default=True)
            default_address.is_default = False
            default_address.save()
            serializer.save()
            return Response(status=status.HTTP_202_ACCEPTED)
        except:
            serializer.save()
            return Response(status=status.HTTP_202_ACCEPTED)
        
    
    @extend_schema(request=AddressSerializer, responses={status.HTTP_202_ACCEPTED: AddressSerializer})
    @action(detail=False, methods=['put'], url_path='address/update')
    def update_address(self, request):
        data = JSONParser().parse(request)
        serializer = AddressSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        id = serializer.validated_data['id']

        address = get_object_or_404(self.user_address, user=user, id=id)
        is_default = serializer.validated_data['is_default']
        default_address = get_object_or_404(self.user_address, user=user, is_default=True) if is_default else None
        
       
        if not default_address:
            serializer.save()
        
        elif (is_default and default_address.id != address.id):
            default_address.is_default = False
            default_address.save()
            serializer.save()
        
        elif default_address.id != address.id:
             serializer.save()
            
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
    
    
    @extend_schema(request=AddressSerializer, responses={status.HTTP_200_OK: AddressSerializer})
    @action(detail=False, methods=['get'], url_path='address')
    def get_address(self, request):
        data = JSONParser().parse(request)
        address = get_object_or_404(self.user_address, user=data['user'], id=data['id'])
        serializer = AddressSerializer(address)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    
    @extend_schema(request=AddressSerializer, responses={status.HTTP_200_OK: AddressSerializer})
    @action(detail=False, methods=['get'], url_path='addresses')
    def get_addresses(self, request):
        data = JSONParser().parse(request)
        address = get_list_or_404(self.user_address, user=data['user'])
        serializer = AddressSerializer(address, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    
    
    @extend_schema(request=None, responses={status.HTTP_202_ACCEPTED: None})
    @action(detail=False, methods=['delete'], url_path='address/delete')
    def delete_address(self, request):
        data = JSONParser().parse(request)
        address = get_object_or_404(self.user_address, user=data['user'], id=data['id'])
        address.delete()
        return Response(status=status.HTTP_202_ACCEPTED)
    
    
    
    @extend_schema(responses={status.HTTP_200_OK: RecentsSerializer})
    @action(detail=False, methods=['get'], url_path='recents/')
    def get_recents(self, request):
        data = JSONParser().parse(request)
        recents = get_list_or_404(self.user_recents, user=data['user'])
        page_number = request.GET.get('offset', 1)
        per_page = request.GET.get('limit', 15)
        paginator = Paginator(recents, per_page=per_page)
        recent_chunk = paginator.get_page(number=page_number)
        serializer = RecentsSerializer(recent_chunk, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    
    @extend_schema(request=None, responses={status.HTTP_202_ACCEPTED: None})
    @action(detail=False, methods=['post'], url_path='recents/add')
    def add_recents(self, request):
        data = JSONParser().parse(request)
        serializer = CreateRecentsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_202_ACCEPTED)
    
    
    
    @extend_schema(request=CreateWishlistSerializer, responses={status.HTTP_201_CREATED: dict})
    @action(detail=False, methods=['post'], url_path='wishlist/add')
    def create_wishlists_product(self, request):
        data = JSONParser().parse(request)
        product = get_object_or_404(self.user_wishlist, product=data['product'], user=data['user'])
        serializer = CreateWishlistSerializer(product)
        return Response({'success': 'Added to wishlist'}, serializer.data, status=status.HTTP_201_CREATED)
    
    
    @extend_schema(responses={status.HTTP_202_ACCEPTED: dict})
    @action(detail=False, methods=['delete'], url_path='wishlist/delete')
    def delete_wishlist_product(self, request):
        data = JSONParser().parse(request)
        product = get_object_or_404(self.user_wishlist, product=data['product'], user=data['user'])
        product.delete()
        return Response({'success': 'Removed from wishlist'}, status=status.HTTP_202_ACCEPTED)
    
    
    @extend_schema(responses={status.HTTP_200_OK: WishlistSerializer})
    @action(detail=False, methods=['get'], url_path='wishlist/')
    def get_wishlists_products(self, request):
        data = JSONParser().parse(request)
        wishlist_products = get_list_or_404(self.user_wishlist, user=data['user'])
        page_number = request.GET.get('offset', 1)
        per_page = request.GET.get('limit', 15)
        paginator = Paginator(wishlist_products, per_page=per_page)
        product_chunk = paginator.get_page(number=page_number)
        serializer = WishlistSerializer(product_chunk, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


    @extend_schema(responses={status.HTTP_201_CREATED: None})
    @action(detail=False, methods=['post', 'put', 'delete', 'get'], url_path='reviews/')
    def reviews(self, request):
        data = JSONParser().parse(request)
        
        
        if request.method == "PUT":
            review = self.user_reviews.objects.get(user=user, product=product)
            serializer = CreateReviewsSerializer(review, data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            review.set_avg_rating()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        
        elif request.method == "POST":
            serializer = CreateReviewsSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            product = serializer.validated_data['product']
            review = serializer.save()
            review.set_avg_rating()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        elif request.method == 'DELETE':
            review = self.user_reviews.objects.get(user=user, product=product)
            review.delete()
            return Response(status=status.HTTP_202_ACCEPTED)
        
        elif request.method == 'GET':
            reviews = get_list_or_404(self.user_reviews, user=data['user'])
            
            page_number = request.GET.get('offset', 1)
            per_page = request.GET.get('limit', 15)
            paginator = Paginator(reviews, per_page=per_page)
            items = paginator.get_page(number=page_number)
            serializer = ReviewsSerializer(items, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)


    @extend_schema(responses={status.HTTP_200_OK: OrdersSerializer})
    @action(detail=False, methods=['get'], url_path='orders/')
    def get_orders(self, request):
        data = JSONParser().parse(request)
        orders = get_list_or_404(self.user_orders, user=data['user'])
  
        page_number = request.GET.get('offset', 1)
        per_page = request.GET.get('limit', 15)
        paginator = Paginator(orders, per_page=per_page)
        orders_chunk = paginator.get_page(number=page_number)
        serializer = OrdersSerializer(orders_chunk, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    @extend_schema(responses={status.HTTP_200_OK: OrdersSerializer})
    @action(detail=False, methods=['post'], url_path='request-refund')
    def request_refund(request):
        data = JSONParser().parse(request)
        serializer = RefundsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['order']
        serializer.save()
        
        mail_data = {
            'firstname': email,
            'order': serializer.validated_data['order'],
            'product': [],
            'created': serializer.validated_data['created']
        }
        
        send_mail('refund-request-acknowledged', email, data=mail_data)
        refund_requested_nofication()
        return Response({'message': 'Refund accepted, this may take 1 to 3 business days before you get a response'}, status=status.HTTP_201_CREATED)



