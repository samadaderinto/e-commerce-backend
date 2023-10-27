from django.db import models


from django.core.validators import MinValueValidator, MaxValueValidator
from nanoid import generate
from store.models import StoreAddress
from core.models import Address, User

from core.utilities import ORDER_STATUS_CHOICE, PAYMENT_STATUS_CHOICE,  DELIVERY_METHOD_CHOICE, USPS_SERVICE_CHOICE


# Create your models here.
class Payment(models.Model):
    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(
        'core.User', on_delete=models.CASCADE, blank=True, null=True)
    amount = models.FloatField()
    status = models.CharField(
        choices=PAYMENT_STATUS_CHOICE, max_length=50, default="pending"
    )
    created = models.DateTimeField(auto_now_add=True)


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True,
                            blank=False, null=False)
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_to = models.DateTimeField()
    discount = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(60)]
    )
    num_available = models.IntegerField(validators=[MinValueValidator(0)])
    num_used = models.IntegerField(
        validators=[MinValueValidator(0)], default=0)

    active = models.BooleanField(default=True)

    def can_use(self):
        is_active = self.active
        is_usable = self.num_used <= self.num_available
        return is_active and is_usable

    def used(self):
        self.num_used += 1
        if self.num_available >= self.num_used:
            self.active = False
            self.save()
            
            
class DeliveryInfo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    method = models.CharField(choices=DELIVERY_METHOD_CHOICE, max_length=150)
    address = models.ForeignKey(Address, on_delete=models.CASCADE)
   
    total = models.IntegerField(default=0, blank=False, null=False)
    delivery_type = models.CharField(choices=USPS_SERVICE_CHOICE, max_length=150)

    def get_delivery_info(self):
        full_delivery_address = "%s, %s %s, %s" % (
            self.address.address,
            self.address.state,
            self.address.country,
            self.address.zip,
        )
        return (
            self.user,
            full_delivery_address,
            self.method,
            self.delivery_type,
            self.total,
        )

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cartId = models.ForeignKey('cart.Cart', on_delete=models.CASCADE)
    orderId = models.CharField(
        max_length=15,
        default=generate(size=13),
        unique=True,
        editable=False,
    )
    coupon_code = models.CharField(max_length=50)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(choices=ORDER_STATUS_CHOICE, max_length=15)
    delivery = models.ForeignKey(DeliveryInfo, on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    payment_type = models.CharField(max_length=30, default="card")
    ordered_date = models.DateTimeField(auto_now=True)

    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)





class DeliveryEstimates(models.Model):
    usps_service = models.CharField(choices=USPS_SERVICE_CHOICE, max_length=20)
    usps_delivery_date = models.IntegerField(
        default=0, blank=False, null=False)
    destination_zip = models.ForeignKey(Address, on_delete=models.CASCADE)
    origin_zip = models.ForeignKey(StoreAddress, on_delete=models.CASCADE)
    pick_up = models.IntegerField(default=25, blank=False, null=False)
    standard_delivery = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, blank=False, null=False
    )
    express_delivery = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, blank=False, null=False
    )
