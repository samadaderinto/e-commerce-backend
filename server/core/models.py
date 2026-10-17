from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from typing import Any

from payment.models import Order
from utils.mixins import DatesMixin

from phonenumber_field.modelfields import PhoneNumberField
from product.models import Product





class BankAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
    )
    bank_name = models.CharField(max_length=120)
    account_holder_name = models.CharField(max_length=160)
    account_number_encrypted = models.TextField()
    routing_number_encrypted = models.TextField()
    account_last4 = models.CharField(max_length=4)
    routing_last4 = models.CharField(max_length=4)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='one_default_bank_account_per_user',
            ),
        ]


class StripePayoutDestination(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stripe_payout_destinations',
    )
    label = models.CharField(max_length=120)
    account_id_encrypted = models.TextField()
    account_id_last4 = models.CharField(max_length=4)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='one_default_stripe_destination_per_user',
            ),
        ]


class UserManager(BaseUserManager):
    def create_user(
        self,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        if not email:
            raise ValueError('Email Address Is Needed')
        if not password:
            raise ValueError('Password Must Be Provided')

        # The application treats email addresses case-insensitively for sign-in.
        # Store a canonical value so invitations and direct account creation use
        # the same identity as registration and social sign-in.
        emailnew = self.normalize_email(email).strip().lower()
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
    updated = models.DateTimeField(auto_now=True)
    last_active_at = models.DateTimeField(null=True, blank=True, db_index=True)

    @property
    def created(self) -> datetime:
        return self.date_joined

    def save(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get('update_fields') and set(kwargs['update_fields']) - {'last_login', 'last_active_at'}:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'updated'}
        super().save(*args, **kwargs)
    GENDER_STATUS = (
        ("male", "male"),
        ("female", "female")
    )
    
    is_business_admin = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    credential_version = models.PositiveIntegerField(default=0)
    staff_email_verified = models.BooleanField(default=True)
    staff_invitation_secret = models.TextField(blank=True, default="")
    staff_blocked_at = models.DateTimeField(null=True, blank=True)

    @property
    def role(self):
        if self.is_superuser:
            return "technical_admin"
        if self.is_business_admin:
            return "business_admin"
        return "staff" if self.is_staff else "customer"

    username = None
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(choices=GENDER_STATUS, max_length=7)
    email = models.EmailField(unique=True, db_index=True)
    phone1 = PhoneNumberField()
    phone2 = PhoneNumberField(null=True, blank=True)
    password = models.CharField(max_length=128)
    avatar_url = models.URLField(max_length=1000, null=True, blank=True)
    avatar_image = models.ImageField(upload_to='user-profiles/avatars/', blank=True, default='')
    email_product_recommendations = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'gender', 'phone1']

    objects = UserManager()


class SocialAccount(models.Model):
    """Provider identity ownership survives disconnect to prevent silent relinking."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_accounts')
    provider = models.CharField(max_length=10, choices=[('google', 'Google'), ('apple', 'Apple')])
    subject = models.CharField(max_length=255)
    email = models.EmailField()
    connected = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provider', 'subject'], name='social_provider_subject_unique'),
            models.UniqueConstraint(fields=['user', 'provider'], condition=models.Q(connected=True), name='social_user_provider_unique'),
        ]


class Address(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    address = models.TextField(null=False, blank=False)
    zip = models.CharField(null=False, blank=False, max_length=10)
    country = models.CharField(max_length=30, null=False, blank=False)
    state = models.CharField(max_length=30, null=False, blank=False)
    city = models.CharField(max_length=100)
    is_default = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)


class Review(DatesMixin):
    is_edited = models.BooleanField(default=False)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            fields = ['label', 'comment', 'rating', 'images']
            previous = type(self).objects.filter(pk=self.pk).values(*fields).first()
            persisted_fields = kwargs.get('update_fields')
            if previous and any(previous[field] != getattr(self, field) for field in fields if persisted_fields is None or field in persisted_fields):
                self.is_edited = True
                if persisted_fields is not None:
                    kwargs['update_fields'] = set(persisted_fields) | {'is_edited', 'updated'}
        super().save(*args, **kwargs)
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
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_DECLINED = 'declined'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DECLINED, 'Declined'),
        (STATUS_FAILED, 'Failed'),
    )
    REFUND_TYPE_STORE_CREDIT = 'store_credit'
    REFUND_TYPE_ORIGINAL_PAYMENT = 'original_payment'
    REFUND_TYPE_CHOICES = (
        (REFUND_TYPE_STORE_CREDIT, 'Store Credit'),
        (REFUND_TYPE_ORIGINAL_PAYMENT, 'Original Payment Method'),
    )

    email = models.EmailField()
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField()
    accepted = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='processed_refunds',
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    refund_type = models.CharField(
        max_length=20,
        choices=REFUND_TYPE_CHOICES,
        default=REFUND_TYPE_STORE_CREDIT,
    )
    provider_reference = models.CharField(max_length=255, blank=True, default='')
    failure_reason = models.TextField(blank=True, default='')
    selected_items = models.JSONField(default=list, blank=True)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    processing_reason = models.TextField(blank=True, default='')


class Device(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    device_ip = models.GenericIPAddressField()
    verified = models.BooleanField(default=False)
    type = models.CharField(max_length=50)
    version = models.CharField(max_length=50)
    last_login = models.DateTimeField(default=timezone.now)


class UserWallet(DatesMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
    idempotency_key = models.CharField(max_length=150, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-created"]
