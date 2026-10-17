from django.db import models
from django.urls import reverse
from django.conf import settings
from django.core.exceptions import ValidationError
from product.models import Product
from utils.mixins import DatesMixin
from nanoid import generate
from decimal import Decimal

# Create your models here.

class Marketer(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    marketer_id = models.CharField(max_length=70, unique=True, editable=False)
    name = models.CharField(max_length=70)
    
    def save(self, *args, **kwargs):
        if not self.marketer_id:
            self.marketer_id = self._generate_unique_username()
        super().save(*args, **kwargs)

    def _generate_unique_username(self, size=15):
        marketer_id = generate(size=size)
        while Marketer.objects.filter(marketer_id=marketer_id).exists():
            marketer_id = generate(size=size)
        return marketer_id
    
   
class Url(DatesMixin):
    marketer = models.ForeignKey('Marketer', on_delete=models.CASCADE) 
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    identifier = models.CharField(max_length=120)
    abs_url = models.URLField()
    active = models.BooleanField(default=True)
    
    def set_refferal_link(self):
        domain = "http://localhost:8000/"
        identifier = self.identifier
        marketer = self.marketer.marketer_id
        product = self.product.pk
        self.abs_url = f"https://www.{domain}.com/{marketer}/{product}/{identifier}/"
        return self.abs_url
    
class Redirect(DatesMixin):   
    last_clicked_at = models.DateTimeField(null=True, blank=True)
    urlId = models.ForeignKey('Url', on_delete=models.CASCADE)
    product_url = models.URLField()
    refferal_url = models.CharField(max_length=15, unique=True, blank=True)
    click_rate = models.PositiveIntegerField(default=0)  


class AffiliateWallet(DatesMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return f"{self.user_id}: ${self.balance}"


class AffiliateWalletTransaction(DatesMixin):
    CREDIT = "credit"
    DEBIT = "debit"
    TRANSACTION_TYPE_CHOICES = (
        (CREDIT, "Credit"),
        (DEBIT, "Debit"),
    )

    wallet = models.ForeignKey(
        AffiliateWallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    reason = models.CharField(max_length=120)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created", "-pk"]

    def clean(self):
        if self.amount <= 0:
            raise ValidationError({"amount": "Transaction amount must be greater than zero."})


class Referral(DatesMixin):
    PENDING = "pending"
    REWARDED = "rewarded"
    STATUS_CHOICES = (
        (PENDING, "Pending"),
        (REWARDED, "Rewarded"),
    )

    marketer = models.ForeignKey(Marketer, on_delete=models.CASCADE, related_name="referrals")
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_referral",
    )
    reward_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("25.00"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    wallet_transaction = models.OneToOneField(
        AffiliateWalletTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral",
    )
    order = models.ForeignKey(
        "payment.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["marketer", "referred_user"],
                name="unique_marketer_referred_user",
            )
        ]


class ClickBankOutboundClick(DatesMixin):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="clickbank_clicks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clickbank_clicks",
    )
    tracking_id = models.CharField(max_length=120, unique=True, db_index=True)
    hoplink_used = models.URLField(max_length=1000)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"ClickBank Click {self.tracking_id} for Product #{self.product_id}"


class ClickBankConversion(DatesMixin):
    click = models.ForeignKey(
        ClickBankOutboundClick,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversions",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clickbank_conversions",
    )
    receipt = models.CharField(max_length=100, unique=True, db_index=True)
    tracking_id = models.CharField(max_length=120, blank=True, default='', db_index=True)
    transaction_type = models.CharField(max_length=50, default='SALE')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    affiliate_commission = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='USD')
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"ClickBank Receipt {self.receipt} ({self.transaction_type}) - ${self.affiliate_commission}"

