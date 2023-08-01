from django.db import models

from phonenumber_field.modelfields import PhoneNumberField
from product.models import Product
from nanoid import generate



# Create your models here.

class Store(models.Model):
    user = models.ForeignKey('core.User', on_delete=models.CASCADE)
    username = models.CharField(max_length=17,unique=True,default=generate(size=15))
    name = models.CharField(max_length=40)
    phone1 = PhoneNumberField(region="US")
    phone2 = PhoneNumberField(region="US")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)   

class Schedule(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    productId = models.ForeignKey(Product, on_delete=models.CASCADE)
    make_visible_at = models.DateTimeField()
    
    
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
    
 
       