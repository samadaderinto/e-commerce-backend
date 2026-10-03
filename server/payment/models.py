from django.db import models
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
    ("failed", "failed"))
    
    
    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)
    amount = models.FloatField()
    status = models.CharField(choices=PAYMENT_STATUS_CHOICE, max_length=50, default='pending')


class Coupon(DatesMixin):
    ORDER_TOTAL = 'order_total'
    PRODUCT = 'product'
    PRODUCT_QUANTITY = 'product_quantity'
    CATEGORY = 'category'
    TYPE_CHOICES = (
        (ORDER_TOTAL, 'Order total'),
        (PRODUCT, 'Product'),
        (PRODUCT_QUANTITY, 'Product quantity'),
        (CATEGORY, 'Category'),
    )
    code = models.CharField(max_length=50, unique=True, blank=False, null=False)
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_to = models.DateTimeField()
    discount = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    num_available = models.IntegerField(validators=[MinValueValidator(0)])
    num_used = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    active = models.BooleanField(default=True)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=ORDER_TOTAL)
    product = models.ForeignKey('product.Product', null=True, blank=True, on_delete=models.CASCADE, related_name='coupons')
    category = models.CharField(max_length=100, blank=True, default='')
    minimum_quantity = models.PositiveIntegerField(default=1)

    def can_use(self) -> bool:
        from django.utils import timezone
        now = timezone.now()
        is_active = self.active
        is_usable = self.num_used < self.num_available
        is_valid_date = self.valid_to >= now
        return is_active and is_usable and is_valid_date

    def used(self) -> None:
        self.num_used += 1
        if self.num_used >= self.num_available:
            self.active = False
        self.save()



class CouponRedemption(DatesMixin):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='redemptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coupon_redemptions')
    order = models.OneToOneField('Order', null=True, blank=True, on_delete=models.SET_NULL, related_name='coupon_redemption')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['coupon', 'user'], name='unique_coupon_redemption_per_user')]


class DeliveryInfo(DatesMixin):
    DELIVERY_TYPE_CHOICES = (
        ("standard", "Standard"),
        ("express", "Express"),
    )

    DELIVERY_METHOD_CHOICE = (
    ("pick up", "pick up"),
    ("home delivery", "home delivery"))
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    method = models.CharField(choices=DELIVERY_METHOD_CHOICE, max_length=150)
    address = models.ForeignKey('core.Address', on_delete=models.CASCADE)
    total = models.IntegerField(default=0, blank=False, null=False)
    delivery_type = models.CharField(choices=DELIVERY_TYPE_CHOICES, max_length=150)

    def get_delivery_info(self) -> tuple:
        full_delivery_address = '%s, %s %s, %s' % (
            self.address.address,
            self.address.state,
            self.address.country,
            self.address.zip
        )
        return (
            self.user,
            full_delivery_address,
            self.method,
            self.delivery_type,
            self.total
        )


class Order(DatesMixin):
    
    ORDER_STATUS_CHOICE = (
        ("pending", "pending"),
        ("cancelled", "cancelled"),
        ("refunded", "refunded"),
        ("delivered", "delivered"),
        ("shipped", "shipped"),
        ("picked up", "picked up"),
        ("confirmed", "confirmed")
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    orderId = models.CharField(max_length=15, default=generate_order_reference, unique=True, editable=False)
    coupon_code = models.CharField(max_length=50)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(choices=ORDER_STATUS_CHOICE, max_length=15)
    delivery = models.ForeignKey(DeliveryInfo, on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    payment_type = models.CharField(max_length=30, default='card')
    ordered_date = models.DateTimeField(auto_now=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    items_snapshot = models.JSONField(default=list, blank=True)
    address_snapshot = models.JSONField(default=dict, blank=True)
    checkout_key = models.UUIDField(null=True, blank=True, unique=True)
    stripe_session_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    
    def save(self, *args, **kwargs) -> None:
        if not self.orderId:
            self.orderId = self._generate_unique()
        super().save(*args, **kwargs)

    def _generate_unique(self, size: int = 15) -> str:
        order_id = generate(size=size)
        while Order.objects.filter(orderId=order_id).exists():
            order_id = generate(size=size)
        return order_id

