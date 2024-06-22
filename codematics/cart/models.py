from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings

from product.models import Product
from utils.mixins import DatesMixin





class Cart(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
 

class CartItem(DatesMixin):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)], default=1)
