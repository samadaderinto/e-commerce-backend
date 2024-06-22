from django.db import models
from utils.mixins import DatesMixin
from taggit.managers import TaggableManager
from django.conf import settings

# Create your models here.

class Post(DatesMixin):
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=300)
    tags = TaggableManager()
    
    
    
class Content(DatesMixin):
    blog_id = models.ForeignKey('Post', on_delete=models.CASCADE)
    content =  models.TextField()   

  

class Comment(DatesMixin):
    body = models.CharField(max_length=300,blank=False,null=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', on_delete=models.CASCADE)
    
    
    
    