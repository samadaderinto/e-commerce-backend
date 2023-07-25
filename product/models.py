from django.db import models

from django.core.validators import MinValueValidator, MaxValueValidator







# Create your models here.
from core.utilities import CATEGORIES_CHOICE, LABEL_CHOICE, USPS_SERVICE_CHOICE,DELIVERY_METHOD_CHOICE

from django.core.validators import MinValueValidator, MaxValueValidator
from nanoid import generate

from taggit.managers import TaggableManager



class Product(models.Model):
    store = models.ForeignKey('store.Store', on_delete=models.CASCADE)
    title = models.CharField(max_length=110, blank=False, null=False)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=15, decimal_places=2, blank=False, null=False)
    discount = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(50)])
    available = models.IntegerField(
        null=False, blank=False, validators=[MinValueValidator(0)])
    category = models.CharField(choices=CATEGORIES_CHOICE, max_length=4)
    label = models.CharField(choices=LABEL_CHOICE,
                             max_length=50, default="NEW")
    product_visibility = models.BooleanField(default=True)
    image = models.ImageField(
        upload_to="images", default="", null=True, blank=True)

    average_rating = models.DecimalField(max_digits=4, decimal_places=2, default=0.00, validators=[
                                         MinValueValidator(0), MaxValueValidator(5)])
    usps_delivery_date = models.IntegerField(
        default=0, blank=False, null=False)
    usps_service = models.CharField(choices=USPS_SERVICE_CHOICE, max_length=20)
    
    tags = TaggableManager()
    sponsored = models.BooleanField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def set_availability(self, quantity_bought: int):
        self.available -= quantity_bought
    
    def set_sponsorship(self,switch_to: bool):
            self.sponsored = switch_to
            
class ProductImg(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(
        upload_to="images", default="", null=True, blank=True)
    
                
class Specification(models.Model):
    product = models.ForeignKey(Product,on_delete=models.CASCADE)
    weight = models.DecimalField(decimal_places=2, max_digits=4)
    height = models.DecimalField(max_digits=4, decimal_places=2)
    width = models.DecimalField(max_digits=4, decimal_places=2)
    breadth = models.DecimalField(max_digits=4, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)            
    
    
class Cart(models.Model):
    id = models.CharField(max_length=15, default=generate(
        size=15), primary_key=True, editable=False, unique=True)
    userId = models.ForeignKey('core.User', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    ordered = models.BooleanField(default=False)


class CartItem(models.Model):
    cartId = models.ForeignKey(Cart, on_delete=models.CASCADE)
    productId = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0)], default=0)    
    
    
    
