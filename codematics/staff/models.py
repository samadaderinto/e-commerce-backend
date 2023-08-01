from django.db import models

# Create your models here.

from core.models import User
from taggit.managers import TaggableManager
# Create your models here.

class Post(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=300)
    tags = TaggableManager()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    
class Content(models.Model):
    blog_id = models.ForeignKey(Post, on_delete=models.CASCADE)
    content =  models.TextField()   
    
    
    