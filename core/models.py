from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import BaseUserManager, AbstractUser

from cart.models import CartItem, Product
from core.utilities import DELIVERY_METHOD_CHOICE, USPS_SERVICE_CHOICE
from store.models import StoreAddress

from datetime import datetime
from nanoid import generate
from phonenumber_field.modelfields import PhoneNumberField
from functools import partial

# Create your models here.
class UserManager(BaseUserManager):

    def create_user(self, email=None, password=None, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError("Email Address Is Needed")
        if not password:
            raise ValueError("Password Must Be Provided")

        emailnew = self.normalize_email(email)
        user = self.model(username=emailnew, email=emailnew, **extra_fields)

        user.set_password(password)

        user.save(using=self._db)

        return user

    def create_superuser(self, email=None, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)

    def create_staffuser(self, email=None, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("staffuser must have is_staff=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    firstname = models.CharField(max_length=30)
    lastname = models.CharField(max_length=30)
    gender = models.CharField(max_length=30)
    email = models.EmailField(unique=True)
    phone1 = PhoneNumberField(region="US")
    password = models.CharField(max_length=90)
    phone2 = PhoneNumberField(region="US", null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['firstname', 'lastname', 'phone1', 'password']

    objects = UserManager()


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.TextField()
    zip = models.CharField(null=True, blank=True, max_length=10)
    country = models.CharField(max_length=30, null=True, blank=True)
    state = models.CharField(max_length=30, null=True, blank=True)
    city = models.CharField(max_length=100)
    is_default = models.BooleanField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class Refund(models.Model):
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE, blank=True, null=True)
    order = models.ForeignKey(CartItem, on_delete=models.CASCADE)
    reason = models.TextField()
    accepted = models.BooleanField(default=False)


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    productId = models.ForeignKey(Product, on_delete=models.CASCADE)
    label = models.CharField(max_length=40)
    comment = models.TextField(max_length=60)
    rating = models.IntegerField(default=0, validators=[
                                 MinValueValidator(0), MaxValueValidator(5)])
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def set_email(self):
        self.email = self.user.email

    def rate(self, rating: int):
        Review.objects.filter(productId=self.productId,
                               user=self.user).delete()
        Review.rating.create(user=self.user, rating=rating)

        self.rating = rating

    def set_avg_rating(self):
        products = Product.objects.all()
        for product in products:
            rating = Review.objects.filter(
                productId=product, user=self.user).first()
            product.average_rating = Review.objects.filter(productId=self.productId).aggregate(
                models.Avg("rating"))["rating__avg"] if rating else 0

    def num_of_reviews(self):
        return Review.objects.filter(productId=self.productId.pk).count()


class DeliveryEstimates(models.Model):
    usps_service = models.CharField(choices=USPS_SERVICE_CHOICE, max_length=20)
    usps_delivery_date = models.IntegerField(
        default=0, blank=False, null=False)
    destination_zip = models.ForeignKey(Address, on_delete=models.CASCADE)
    origin_zip = models.ForeignKey(StoreAddress, on_delete=models.CASCADE)
    pick_up = models.IntegerField(default=25, blank=False, null=False)
    standard_delivery = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, blank=False, null=False)
    express_delivery = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, blank=False, null=False)


class DeliveryInfo(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    method = models.CharField(choices=DELIVERY_METHOD_CHOICE, max_length=15)
    delivery_address = models.ForeignKey(Address, on_delete=models.CASCADE)
    discount = models.IntegerField(default=0, blank=False, null=False, validators=[
                                   MinValueValidator(0), MaxValueValidator(100)])
    estimate = models.IntegerField(default=0, blank=False, null=False)
    delivery_type = models.CharField(max_length=50)

    def get_delivery_info(self):
        full_delivery_address = "%s, %s %s, %s" % (
            Address.address, Address.state, Address.country, Address.zip)
        return (self.user, full_delivery_address, self.method, self.delivery_type, self.discount, self.estimate)


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    liked = models.BooleanField(default=False)
    productId = models.ForeignKey(Product, on_delete=models.CASCADE)


class Recent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    productId = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
