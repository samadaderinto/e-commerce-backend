from django.db import models
from django.urls import reverse

from core.models import User
from product.models import Product
from nanoid import generate

# Create your models here.

class Marketer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    marketer_id = models.CharField(max_length=70, default=generate(size=15), unique=True,editable=False)
    name = models.CharField(max_length=70)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
   
class Url(models.Model):
    marketer = models.ForeignKey(Marketer, on_delete=models.CASCADE) 
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    # identifier can be any text inputted by the marketer on url generation
    identifier = models.CharField(max_length=120)
    abs_url = models.URLField()
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def set_refferal_link(self):
        domain = "http://localhost:8000/"
        identifier = self.identifier
        marketer = self.marketer.marketer_id
        product = self.product.pk
        self.abs_url = f"https://www.{domain}.com/{marketer}/{product}/{identifier}/"
        return self.abs_url
    
class Redirect(models.Model):   
    urlId = models.ForeignKey(Url, on_delete=models.CASCADE)
    product_url = models.URLField()
    refferal_url = models.CharField(max_length=15, unique=True, blank=True)
    click_rate = models.PositiveIntegerField(default=0)  
    created = models.DateTimeField(auto_now_add=True)
    

            
            
            


    
    
