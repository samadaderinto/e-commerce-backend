from django.db import models
from django.conf import settings

from utils.mixins import DatesMixin
from phonenumber_field.modelfields import PhoneNumberField
from nanoid import generate


# Create your models here.


class Store(DatesMixin):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    username = models.CharField(max_length=17, unique=True)
    name = models.CharField(max_length=40)
    
    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self._generate_unique_username()
        super().save(*args, **kwargs)

    def _generate_unique_username(self, size=15):
        username = generate(size)
        while Store.objects.filter(username=username).exists():
            username = generate(size)
        return username



class Schedule(DatesMixin):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey('product.Product', on_delete=models.CASCADE)
    make_visible_at = models.DateTimeField()


class StoreInfo(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    bio = models.TextField()
    instagram = models.URLField()
    twitter = models.URLField()
    facebook = models.URLField()
    contact_email = models.EmailField(null=True, blank=True)
    phone1 = PhoneNumberField(null=True, blank=True)
    phone2 = PhoneNumberField(null=True, blank=True)
    phone1 = models.CharField(max_length=225)
    whatsapp1 = models.CharField(max_length=225)


class StoreAddress(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    address = models.TextField()
    zip = models.CharField(null=True, blank=True, max_length=10)
    country = models.CharField(max_length=30, null=False, blank=False)
    state = models.CharField(max_length=30, null=False, blank=False)
    city = models.CharField(max_length=100, null=False, blank=False)
    is_default = models.BooleanField()


class StoreImg(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    url = models.ImageField(upload_to='images', default='', null=True, blank=True)


class Withdrawal(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10000000000, decimal_places=2)
    withdrawed_on = models.DateTimeField(auto_now_add=True)


class Wallet(DatesMixin):
    store = models.ForeignKey('Store', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10000000000, decimal_places=2)
