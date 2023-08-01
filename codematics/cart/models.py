from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from nanoid import generate

from product.models import Product

# Create your models here.
class Cart(models.Model):
    id = models.CharField(
        max_length=15,
        default=generate(size=15),
        primary_key=True,
        editable=False,
        unique=True,
    )
    userId = models.ForeignKey("core.User", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    ordered = models.BooleanField(default=False)


class CartItem(models.Model):
    cartId = models.ForeignKey(Cart, on_delete=models.CASCADE)
    productId = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0)], default=0
    )
