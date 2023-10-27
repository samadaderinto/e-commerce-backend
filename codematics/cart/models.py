from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from nanoid import generate
from core.models import User

from product.models import Product

# Create your models here.


class Cart(models.Model):
    userId = models.ForeignKey(User, on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)], default=1)
