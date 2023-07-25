from django.db import models
from core.utilities import generate_marketer_code

from core.models import User
from product.models import Product

# Create your models here.

class Marketer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    marketer_id = models.CharField(max_length=70, default=generate_marketer_code(), unique=True,editable=False)
    name = models.CharField(max_length=70)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
   
class Url(models.Model):
    marketer = models.ForeignKey(Marketer, on_delete=models.CASCADE) 
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    identifier = models.CharField(max_length=120)
    abs_url = models.URLField()
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    
    
    
    
    
            
            
            
            
            


    
    
