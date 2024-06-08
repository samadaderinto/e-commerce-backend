from django.db import models
from django.core.validators import MinValueValidator

from utils.mixins import DatesMixin
from nanoid import generate




class Cart(DatesMixin):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
 


class CartItem(DatesMixin):
    cart = models.ForeignKey('Cart', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)], default=1)
