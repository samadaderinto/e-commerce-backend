from django.db import models


from django.core.validators import MinValueValidator, MaxValueValidator
from nanoid import generate


from cart.models import Cart
from core.utilities import ORDER_STATUS_CHOICE, PAYMENT_STATUS_CHOICE
from core.models import DeliveryInfo, User


# Create your models here.
class Payment(models.Model):
    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    amount = models.FloatField()
    status = models.CharField(
        choices=PAYMENT_STATUS_CHOICE, max_length=50, default="PND"
    )
    created = models.DateTimeField(auto_now_add=True)


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True, blank=False, null=False)
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_to = models.DateTimeField()
    discount = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    num_available = models.IntegerField(validators=[MinValueValidator(0)])
    num_used = models.IntegerField(validators=[MinValueValidator(0)], default=0)

    active = models.BooleanField(default=True)

    def can_use(self):
        is_active = self.active
        is_usable = self.num_used <= self.num_available
        return is_active and is_usable

    def used(self):
        self.num_used += 1
        if self.num_available == self.num_used:
            self.active = False


class Order(models.Model):
    cartId = models.ForeignKey(Cart, on_delete=models.CASCADE)
    orderId = models.CharField(
        max_length=15,
        default=generate(size=10),
        unique=True,
        editable=False,
    )
    coupon_used = models.CharField(max_length=50)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(choices=ORDER_STATUS_CHOICE, max_length=3)
    delivery = models.ForeignKey(DeliveryInfo, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ordered_date = models.DateTimeField(auto_now=True)
    ordered = models.BooleanField(False)
    payment_type = models.CharField(max_length=30, default="card")

    def save_orderId(self, *args, **kwargs):
        if not self.orderId:
            value = self.cartId.pk
            self.orderId = value
        super().save(*args, **kwargs)

    def get_totals(self, *args, **kwargs):
        self.subtotal = round(self.total + self.tax)
