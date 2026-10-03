from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings

from payment.models import Order
from utils.mixins import DatesMixin

from phonenumber_field.modelfields import PhoneNumberField
from product.models import Product





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
    GENDER_STATUS = (
        ("male", "male"),
        ("female", "female")
    )
    
    username = None
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(choices=GENDER_STATUS, max_length=7)
    email = models.EmailField(unique=True, db_index=True)
    phone1 = PhoneNumberField()
    phone2 = PhoneNumberField(null=True, blank=True)
    password = models.CharField(max_length=128)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'gender', 'phone1']

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
    label = models.CharField(max_length=120)
    comment = models.TextField(max_length=1000)
    rating = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    images = models.JSONField(default=list, blank=True)

    def set_avg_rating(self) -> None:
        average = Review.objects.filter(product=self.product).aggregate(
            models.Avg('rating')
        )['rating__avg'] or 0
        from decimal import Decimal
        self.product.average_rating = Decimal(str(round(float(average), 2)))
        self.product.save(update_fields=["average_rating", "updated"])

    def num_of_reviews(self) -> int:
        return Review.objects.filter(product=self.product).count()

    
    class Meta:
        ordering = ["-created"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_user_product_review"
            )
        ]


class Wishlist(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    liked = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_user_product_wishlist"
            )
        ]
    


class Recent(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)


from decimal import Decimal


class Refund(DatesMixin):
    REFUND_TYPE_STORE_CREDIT = 'store_credit'
    REFUND_TYPE_ORIGINAL_PAYMENT = 'original_payment'
    REFUND_TYPE_CHOICES = (
        (REFUND_TYPE_STORE_CREDIT, 'Store Credit'),
        (REFUND_TYPE_ORIGINAL_PAYMENT, 'Original Payment Method'),
    )

    email = models.EmailField()
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.TextField()
    accepted = models.BooleanField(default=False)
    refund_type = models.CharField(
        max_length=20,
        choices=REFUND_TYPE_CHOICES,
        default=REFUND_TYPE_STORE_CREDIT,
    )


class Device(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    device_ip = models.GenericIPAddressField()
    verified = models.BooleanField(default=False)
    type = models.CharField(max_length=50)
    version = models.CharField(max_length=50)
    last_login = models.DateTimeField(auto_now_add=True)


class UserWallet(DatesMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return f"UserWallet({self.user_id}: ${self.balance})"


class UserWalletTransaction(DatesMixin):
    CREDIT = "credit"
    DEBIT = "debit"
    TRANSACTION_TYPE_CHOICES = (
        (CREDIT, "Credit"),
        (DEBIT, "Debit"),
    )

    SOURCE_REFUND = "refund"
    SOURCE_PURCHASE = "purchase"
    SOURCE_DEPOSIT = "deposit"
    SOURCE_REFERRAL = "referral"
    SOURCE_ADJUSTMENT = "adjustment"
    SOURCE_CHOICES = (
        (SOURCE_REFUND, "Refund Store Credit"),
        (SOURCE_PURCHASE, "Checkout Purchase"),
        (SOURCE_DEPOSIT, "Deposit"),
        (SOURCE_REFERRAL, "Referral Reward"),
        (SOURCE_ADJUSTMENT, "Adjustment"),
    )

    wallet = models.ForeignKey(
        UserWallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_REFUND)
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["-created"]

