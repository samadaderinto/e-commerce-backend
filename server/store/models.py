from django.db import models
from django.conf import settings

from utils.mixins import DatesMixin
from phonenumber_field.modelfields import PhoneNumberField
from nanoid import generate


# Create your models here.


class Store(DatesMixin):
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_BLOCKED = "blocked"
    STATUS_CHOICES = (
        (STATUS_PENDING, "pending"),
        (STATUS_ACTIVE, "active"),
        (STATUS_BLOCKED, "blocked"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    username = models.CharField(max_length=17, unique=True)
    name = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_stores",
    )
    blocked_reason = models.TextField(blank=True, default="")
    blocked_at = models.DateTimeField(null=True, blank=True)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocked_stores",
    )
    
    def save(self, *args, **kwargs) -> None:
        if not self.username:
            self.username = self._generate_unique_username()
        super().save(*args, **kwargs)

    def _generate_unique_username(self, size: int = 15) -> str:
        username = generate(size=size)
        while Store.objects.filter(username=username).exists():
            username = generate(size=size)
        return username




class Schedule(DatesMixin):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey('product.Product', on_delete=models.CASCADE)
    make_visible_at = models.DateTimeField()


class StoreInfo(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    email = models.EmailField(null=True, blank=True)
    bio = models.TextField()
    instagram = models.URLField()
    twitter = models.URLField()
    facebook = models.URLField()
    whatsapp = PhoneNumberField(null=True, blank=True)
    phone2 = PhoneNumberField(null=True, blank=True)
    phone1 = PhoneNumberField(null=True, blank=True)
    
    


class StoreAddress(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    address = models.TextField()
    zip = models.CharField(null=True, blank=True, max_length=10)
    country = models.CharField(max_length=30, null=False, blank=False)
    state = models.CharField(max_length=30, null=False, blank=False)
    city = models.CharField(max_length=100, null=False, blank=False)
    is_default = models.BooleanField()


class StoreImg(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    url = models.ImageField(upload_to='images', default='', null=True, blank=True)


class Budget(DatesMixin):
    
    BUDGET_TYPE = (
        ("C", "CREDIT"), 
        ("D", "DEBIT")
    )
    
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    type = models.CharField(choices=BUDGET_TYPE, max_length=10)
   

class Wallet(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)


class StorePayout(DatesMixin):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REJECTED, "Rejected"),
    )

    METHOD_BANK_TRANSFER = "bank_transfer"
    METHOD_STRIPE_CONNECT = "stripe_connect"
    METHOD_CHOICES = (
        (METHOD_BANK_TRANSFER, "Bank Transfer"),
        (METHOD_STRIPE_CONNECT, "Stripe Connect"),
    )

    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payout_method = models.CharField(max_length=50, choices=METHOD_CHOICES, default=METHOD_BANK_TRANSFER)
    account_details = models.JSONField(default=dict, blank=True)
    reference = models.CharField(max_length=100, blank=True, default="")
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_store_payouts",
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created"]

