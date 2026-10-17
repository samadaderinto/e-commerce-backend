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


class PlatformCommissionWithdrawal(DatesMixin):
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = ((STATUS_PENDING, 'pending'), (STATUS_COMPLETED, 'completed'), (STATUS_FAILED, 'failed'))
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payout_method = models.CharField(max_length=50)
    account_details = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='commission_withdrawals')
    reference = models.CharField(max_length=40, unique=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='processed_commission_withdrawals',
    )
    processing_note = models.TextField(blank=True, default='')
