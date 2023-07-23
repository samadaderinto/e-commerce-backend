from django.db import models

# Create your models here.

from core.models import User
from cart.models import Product
# Create your models here.

class Store(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=70, default="official store")
    created = models.DateTimeField(auto_now_add=True)


class StoreInfo(models.Model):
    storeId = models.ForeignKey(Store, on_delete=models.CASCADE)
    about = models.TextField()
    phone = models.CharField(max_length=30)
    site = models.URLField()
    created = models.DateTimeField(auto_now_add=True)
    
    
class StoreAddress(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    address = models.TextField()
    zip = models.CharField(null=True, blank=True, max_length=10)
    country = models.CharField(max_length=30, null=True, blank=True)
    state = models.CharField(max_length=30, null=True, blank=True)
    city = models.CharField(max_length=100)
    is_default = models.BooleanField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)    
    
    

class StoreImg(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    url = models.ImageField(
        upload_to="images", default="", null=True, blank=True)    
    
    
class Schedule(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    productId = models.ForeignKey(Product, on_delete=models.CASCADE)
    make_visible_at = models.DateTimeField()       