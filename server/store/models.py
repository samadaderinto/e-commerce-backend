from decimal import Decimal
from django.db import models
from django.conf import settings

from utils.mixins import DatesMixin
from django.utils import timezone
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
    is_official = models.BooleanField(default=False)
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
        if self.user_id:
            user = getattr(self, 'user', None)
            if getattr(user, 'is_superuser', False) or self.is_official:
                self.is_official = True
                if self.status == self.STATUS_PENDING:
                    self.status = self.STATUS_ACTIVE
                    if not self.verified_at:
                        self.verified_at = timezone.now()
                    if not self.verified_by and user:
                        self.verified_by = user
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
    bio = models.TextField(blank=True, default='')
    avatar_url = models.URLField(max_length=1000, null=True, blank=True)
    banner_url = models.URLField(max_length=1000, null=True, blank=True)
    website = models.URLField(max_length=500, null=True, blank=True)
    instagram = models.URLField(blank=True, default='')
    twitter = models.URLField(blank=True, default='')
    facebook = models.URLField(blank=True, default='')
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


class MerchantWallet(DatesMixin):
    """
    Unified merchant account / wallet per User.
    Consolidates earnings and payouts across all stores owned by this vendor.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="merchant_wallet",
    )
    stripe_account_id = models.CharField(max_length=100, blank=True, default="")
    stripe_details_submitted = models.BooleanField(default=False)
    stripe_payouts_enabled = models.BooleanField(default=False)

    available_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    pending_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    total_withdrawn = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))

    def __str__(self) -> str:
        return f"MerchantWallet(User: {self.user_id}, Available: ${self.available_balance}, Pending: ${self.pending_balance})"


class StoreEarningsLedger(DatesMixin):
    """
    Granular, store-attributed financial ledger entry.
    Tracks sales, escrow holds, fee deductions, payouts, and refunds per store
    while maintaining consistent aggregate balances in the merchant's unified wallet.
    """
    TYPE_SALE = "sale"
    TYPE_FEE = "fee"
    TYPE_PAYOUT = "payout"
    TYPE_REFUND = "refund"
    TYPE_ADJUSTMENT = "adjustment"
    TYPE_CHOICES = (
        (TYPE_SALE, "Sale"),
        (TYPE_FEE, "Platform Fee"),
        (TYPE_PAYOUT, "Payout"),
        (TYPE_REFUND, "Refund"),
        (TYPE_ADJUSTMENT, "Adjustment"),
    )

    STATUS_PENDING = "pending"       # In escrow / refund window
    STATUS_AVAILABLE = "available"   # Cleared into available balance
    STATUS_COMPLETED = "completed"   # Paid out / finalized
    STATUS_REVERSED = "reversed"     # Cancelled or refunded
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_AVAILABLE, "Available"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REVERSED, "Reversed"),
    )

    wallet = models.ForeignKey(
        MerchantWallet,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    order = models.ForeignKey(
        "payment.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="store_ledger_entries",
    )
    entry_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SALE)
    gross_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    fee_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    available_at = models.DateTimeField(null=True, blank=True, help_text="When escrow hold clears")
    cleared_at = models.DateTimeField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True, default="")
    reference = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["-created", "-pk"]

    def __str__(self) -> str:
        return f"StoreEarningsLedger(Store: {self.store_id}, {self.entry_type}: ${self.net_amount}, Status: {self.status})"


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

    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='payouts', null=True, blank=True)
    wallet = models.ForeignKey(
        MerchantWallet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payouts",
    )
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


