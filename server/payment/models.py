from decimal import Decimal
from django.db import models
from typing import Any
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from cart.models import Cart
from utils.mixins import DatesMixin
from nanoid import generate


def generate_order_reference() -> str:
    return generate(size=13)


# Create your models here.
class Payment(DatesMixin):
    PAYMENT_STATUS_CHOICE = (
        ("pending", "pending"),
        ("successful", "successful"),
        ("failed", "failed"),
    )

    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True
    )
    amount = models.FloatField()
    status = models.CharField(
        choices=PAYMENT_STATUS_CHOICE, max_length=50, default="pending"
    )


class Coupon(DatesMixin):
    last_used_at = models.DateTimeField(null=True, blank=True)
    ORDER_TOTAL = "order_total"
    PRODUCT = "product"
    PRODUCT_QUANTITY = "product_quantity"
    CATEGORY = "category"
    TYPE_CHOICES = (
        (ORDER_TOTAL, "Order total"),
        (PRODUCT, "Product"),
        (PRODUCT_QUANTITY, "Product quantity"),
        (CATEGORY, "Category"),
    )
    code = models.CharField(max_length=50, unique=True, blank=False, null=False)
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_to = models.DateTimeField()
    discount = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    num_available = models.IntegerField(validators=[MinValueValidator(0)])
    num_used = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    active = models.BooleanField(default=True)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=ORDER_TOTAL)
    product = models.ForeignKey(
        "product.Product",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="coupons",
    )
    category = models.CharField(max_length=100, blank=True, default="")
    minimum_quantity = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_coupons",
    )

    def can_use(self) -> bool:
        from django.utils import timezone

        now = timezone.now()
        is_active = self.active
        is_usable = self.num_used < self.num_available
        is_valid_date = self.valid_to >= now
        return is_active and is_usable and is_valid_date

    def used(self) -> None:
        from django.utils import timezone

        self.last_used_at = timezone.now()
        self.num_used += 1
        if self.num_used >= self.num_available:
            self.active = False
        self.save()


class CouponRedemption(DatesMixin):
    coupon = models.ForeignKey(
        Coupon, on_delete=models.CASCADE, related_name="redemptions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="coupon_redemptions",
    )
    order = models.OneToOneField(
        "Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coupon_redemption",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "user"], name="unique_coupon_redemption_per_user"
            )
        ]


class DeliveryInfo(DatesMixin):
    DELIVERY_TYPE_CHOICES = (
        ("standard", "Standard"),
        ("express", "Express"),
    )

    DELIVERY_METHOD_CHOICE = (
        ("pick up", "pick up"),
        ("home delivery", "home delivery"),
        ("digital", "digital"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    method = models.CharField(choices=DELIVERY_METHOD_CHOICE, max_length=150)
    address = models.ForeignKey(
        "core.Address", on_delete=models.SET_NULL, null=True, blank=True
    )
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_type = models.CharField(max_length=150)

    def get_delivery_info(self) -> tuple:
        if self.address:
            full_delivery_address = "%s, %s %s, %s" % (
                self.address.address,
                self.address.state,
                self.address.country,
                self.address.zip,
            )
        else:
            full_delivery_address = "Address archived"
        return (
            self.user,
            full_delivery_address,
            self.method,
            self.delivery_type,
            self.total,
        )


class Order(DatesMixin):
    ORDER_STATUS_CHOICE = (
        ("pending", "pending"),
        ("cancelled", "cancelled"),
        ("refunded", "refunded"),
        ("delivered", "delivered"),
        ("shipped", "shipped"),
        ("picked up", "picked up"),
        ("confirmed", "confirmed"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    cart = models.ForeignKey(Cart, on_delete=models.SET_NULL, null=True, blank=True)
    orderId = models.CharField(
        max_length=15, default=generate_order_reference, unique=True, editable=False
    )
    coupon_code = models.CharField(max_length=50)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(choices=ORDER_STATUS_CHOICE, max_length=15)
    delivery = models.ForeignKey(
        DeliveryInfo, on_delete=models.SET_NULL, null=True, blank=True
    )
    ordered = models.BooleanField(default=False)
    payment_type = models.CharField(max_length=30, default="card")
    ordered_date = models.DateTimeField(auto_now_add=True)
    status_updated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    wallet_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refunded_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    wallet_refunded_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    card_refunded_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    shipping_snapshot = models.JSONField(default=dict, blank=True)
    items_snapshot = models.JSONField(default=list, blank=True)
    address_snapshot = models.JSONField(default=dict, blank=True)
    tax_snapshot = models.JSONField(default=dict, blank=True)
    buyer_email = models.EmailField(max_length=255, blank=True, default="")
    buyer_phone = models.CharField(max_length=50, blank=True, default="")
    checkout_key = models.UUIDField(null=True, blank=True, unique=True)
    stripe_session_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True
    )
    carrier = models.CharField(max_length=50, default="USPS", blank=True)
    tracking_number = models.CharField(max_length=100, blank=True, default="")
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    tracking_events = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    paid_total__gte=0, paid_total__lte=models.F("total")
                ),
                name="order_settlement_within_total",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    wallet_paid__gte=0, wallet_paid__lte=models.F("paid_total")
                ),
                name="order_wallet_within_settlement",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    refunded_total__gte=0, refunded_total__lte=models.F("paid_total")
                ),
                name="order_refund_within_settlement",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    wallet_refunded_total__gte=0,
                    wallet_refunded_total__lte=models.F("wallet_paid"),
                ),
                name="order_wallet_refund_within_paid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    card_refunded_total__gte=0,
                    card_refunded_total__lte=models.F("paid_total")
                    - models.F("wallet_paid"),
                ),
                name="order_card_refund_within_paid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    refunded_total=models.F("wallet_refunded_total")
                    + models.F("card_refunded_total")
                ),
                name="order_refund_parts_match_total",
            ),
        ]

    @property
    def tracking_url(self) -> str:
        if not self.tracking_number:
            return ""
        if self.carrier.upper() == "USPS":
            return f"https://tools.usps.com/go/TrackConfirmAction?tLabels={self.tracking_number}"
        from urllib.parse import quote

        number = quote(self.tracking_number, safe="")
        urls = {
            "UPS": f"https://www.ups.com/track?tracknum={number}",
            "FEDEX": f"https://www.fedex.com/fedextrack/?trknbr={number}",
            "DHL": f"https://www.dhl.com/us-en/home/tracking.html?tracking-id={number}",
        }
        return urls.get(self.carrier.upper(), "")

    def save(self, *args: Any, **kwargs: Any) -> None:
        from django.utils import timezone

        previous = (
            type(self)
            .objects.filter(pk=self.pk)
            .values_list("status", flat=True)
            .first()
            if self.pk
            else None
        )
        fields = kwargs.get("update_fields")
        if (fields is None or "status" in fields) and previous != self.status:
            self.status_updated_at = timezone.now()
            touched = {"status_updated_at", "updated"}
            if self.status == "cancelled":
                self.cancelled_at = self.status_updated_at
                touched.add("cancelled_at")
            if self.status == "refunded":
                self.refunded_at = self.status_updated_at
                touched.add("refunded_at")
            if fields is not None:
                kwargs["update_fields"] = set(fields) | touched
        if not self.orderId:
            self.orderId = self._generate_unique()
        super().save(*args, **kwargs)

    def _generate_unique(self, size: int = 15) -> str:
        order_id = generate(size=size)
        while Order.objects.filter(orderId=order_id).exists():
            order_id = generate(size=size)
        return order_id


class ShippingQuote(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cart_fingerprint = models.CharField(max_length=64)
    rate = models.JSONField(default=dict)


class CheckoutAttempt(DatesMixin):
    """Durable wallet reservation and Stripe compensation state."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    checkout_key = models.UUIDField(unique=True)
    session_id = models.CharField(max_length=255, unique=True)
    wallet_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=24, default="reserved", db_index=True)
    payment_intent = models.CharField(max_length=255, blank=True)
    failure_reason = models.TextField(blank=True)


class TaxJurisdiction(DatesMixin):
    country = models.CharField(max_length=2, default="US", db_index=True)
    state = models.CharField(max_length=50, db_index=True)
    postal_code = models.CharField(max_length=20, blank=True, db_index=True)
    name = models.CharField(max_length=150)
    rate = models.DecimalField(
        max_digits=7, decimal_places=5, default=Decimal("0.00000")
    )
    tax_shipping = models.BooleanField(default=False)
    tax_digital = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["country", "state", "postal_code"]
        indexes = [
            models.Index(fields=["country", "state"]),
            models.Index(fields=["country", "state", "postal_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({float(self.rate) * 100:.2f}%)"


class OrderFulfillment(DatesMixin):
    """Fulfillment owned by one store, independent of financial order status."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="fulfillments"
    )
    store = models.ForeignKey("store.Store", on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="confirmed")
    carrier = models.CharField(max_length=50, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "store"], name="unique_order_store_fulfillment"
            )
        ]


class WalletFundingAttempt(DatesMixin):
    """Unique funding receipt plus reserved deposit allowance and recovery state."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    session_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=24, default="reserved", db_index=True)
    failure_reason = models.TextField(blank=True)
