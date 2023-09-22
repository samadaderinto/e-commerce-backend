from django.db import models
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

  

class Comment(models.Model):
    body = models.CharField(max_length=300,blank=False,null=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    
    