from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings

from payment.models import Order
from utils.mixins import DatesMixin

from phonenumber_field.modelfields import PhoneNumberField
from product.models import Product
from core.utilities import USPS_SERVICE_CHOICE, GENDER_STATUS, DELIVERY_METHOD_CHOICE


from notifications.base.models import AbstractNotification


class UserManager(BaseUserManager):
    def create_user(self, email=None, password=None, **extra_fields):
    

        if not email:
            raise ValueError('Email Address Is Needed')
        if not password:
            raise ValueError('Password Must Be Provided')

        emailnew = self.normalize_email(email)
        user = self.model(email=emailnew, **extra_fields)

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email=None, password=None, **extra_fields):
     
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)

    def create_staffuser(self, email=None, password=None, **extra_fields):
     
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('staffuser must have is_staff=True.')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(choices=GENDER_STATUS, max_length=7)
    email = models.EmailField(unique=True, db_index=True)
    phone1 = PhoneNumberField()
    phone2 = PhoneNumberField(null=True, blank=True)
    password = models.CharField(max_length=90)
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'gender', 'phone1', 'password']

    objects = UserManager()


class Address(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    address = models.TextField(null=False, blank=False)
    zip = models.CharField(null=False, blank=False, max_length=10)
    country = models.CharField(max_length=30, null=False, blank=False)
    state = models.CharField(max_length=30, null=False, blank=False)
    city = models.CharField(max_length=100)
    is_default = models.BooleanField(default=True)


class Review(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    label = models.CharField(max_length=40)
    comment = models.TextField(max_length=60)
    rating = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])

    def set_avg_rating(self):
        product = Product.objects.get(id=self.productId.id)
        product.average_rating = Review.objects.filter(productId=self.productId).aggregate(models.Avg('rating'))['rating__avg']
        product.save()

    def num_of_reviews(self):
        return Review.objects.filter(productId=self.productId.id).count()


class Wishlist(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    


class Recent(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)


class Refund(DatesMixin):
    email = models.EmailField(unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.TextField()
    accepted = models.BooleanField(default=False)


class Device(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    device_ip = models.GenericIPAddressField()
    verified = models.BooleanField(default=False)
    type = models.CharField(max_length=50)
    version = models.CharField(max_length=50)
    last_login = models.DateTimeField(auto_now_add=True)
