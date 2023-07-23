from django.db import models
from core.models import User
from taggit.managers import TaggableManager
# Create your models here.

class BlogPost(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(User, on_delete=models.CASCADE)
    tags = TaggableManager()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    

    
    
