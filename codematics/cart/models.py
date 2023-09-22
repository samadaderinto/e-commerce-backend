from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from nanoid import generate
from core.models import User

from product.models import Product

# Create your models here.


class Cart(models.Model):
    cart_id = models.CharField(
        max_length=15,
        default=generate(size=15),
        primary_key=True,
        editable=False,
        unique=True,
    )
    userId = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    ordered = models.BooleanField(default=False)


class CartItem(models.Model):
    cart_id = models.OneToOneField(Cart,on_delete=models.CASCADE,primary_key=True)
    productId = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)], default=0
    )
