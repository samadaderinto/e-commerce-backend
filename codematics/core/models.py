from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator


from phonenumber_field.modelfields import PhoneNumberField
from product.models import Product

from core.utilities import USPS_SERVICE_CHOICE, GENDER_STATUS, DELIVERY_METHOD_CHOICE
from store.models import StoreAddress

from notifications.base.models import AbstractNotification


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
        user = self.model(email=emailnew, **extra_fields)

        user.set_password(password)
        # user.password = make_password(password)

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
    username = None
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(choices=GENDER_STATUS, max_length=7)
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    phone1 = PhoneNumberField(region="US")
    password = models.CharField(max_length=90)
    phone2 = PhoneNumberField(region="US", null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "gender", "phone1", "password"]

    objects = UserManager()


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.TextField(null=False, blank=False,)
    zip = models.CharField(null=False, blank=False, max_length=10)
    country = models.CharField(
        max_length=30,
        null=False,
        blank=False,
    )
    state = models.CharField(
        max_length=30,
        null=False,
        blank=False,
    )
    city = models.CharField(max_length=100)
    is_default = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    productId = models.ForeignKey('product.Product', on_delete=models.CASCADE)
    label = models.CharField(max_length=40)
    comment = models.TextField(max_length=60)
    rating = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


    def set_avg_rating(self):
        product = Product.objects.get(id=self.productId.id)
        product.average_rating = Review.objects.filter(productId=self.productId).aggregate(models.Avg("rating"))["rating__avg"]
        product.save()

    def num_of_reviews(self):
        return Review.objects.filter(productId=self.productId.id).count()


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    liked = models.BooleanField(default=True)
    productId = models.ForeignKey('product.Product', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)


class Recent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    productId = models.ForeignKey('product.Product', on_delete=models.CASCADE)
    viewed = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)


class Refund(models.Model):
    userId = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey("payment.Order", on_delete=models.CASCADE)
    reason = models.TextField()
    accepted = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    
    
class Device(models.Model):
    user =  models.ForeignKey(User, on_delete=models.CASCADE)
    device_ip = models.GenericIPAddressField()
    verified = models.BooleanField(default=False)
    type = models.CharField(max_length=50)
    version = models.CharField(max_length=50)
    last_login = models.DateTimeField(auto_now_add=True)



