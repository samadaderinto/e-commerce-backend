from django.db import models

from phonenumber_field.modelfields import PhoneNumberField

from nanoid import generate



# Create your models here.

class Store(models.Model):
    user = models.ForeignKey('core.User', on_delete=models.CASCADE)
    username = models.CharField(max_length=17,unique=True,default=generate(size=15))
    name = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)   

class Schedule(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    productId = models.ForeignKey('product.Product', on_delete=models.CASCADE)
    make_visible_at = models.DateTimeField()
    
    
class StoreInfo(models.Model):
    storeId = models.ForeignKey(Store, on_delete=models.CASCADE)
    about = models.TextField()
    site = models.URLField()
    contact_email = models.EmailField(null=True,blank=True)
    tel1 = PhoneNumberField(region="US",null=True, blank=True)
    tel2 = PhoneNumberField(region="US",null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True) 
    
    
class StoreAddress(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    address = models.TextField()
    zip = models.CharField(null=True, blank=True, max_length=10)
    country = models.CharField(max_length=30, null=False, blank=False)
    state = models.CharField(max_length=30, null=False, blank=False)
    city = models.CharField(max_length=100,null=False, blank=False)
    is_default = models.BooleanField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)   
    
    
class StoreImg(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    url = models.ImageField(
        upload_to="images", default="", null=True, blank=True)    
    
    
    
class Withdrawal(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10000000000, decimal_places=2)
    withdrawed_on  = models.DateTimeField(auto_now_add=True)
    
    
class Wallet(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10000000000, decimal_places=2)
  
    
 
       