from django.db import models

from django.core.validators import MinValueValidator, MaxValueValidator


# Create your models here.
from utils.mixins import DatesMixin
from core.utilities import (
    CATEGORIES_CHOICE,
    LABEL_CHOICE,
    USPS_SERVICE_CHOICE,
    DELIVERY_METHOD_CHOICE,
)

from nanoid import generate

from taggit.managers import TaggableManager


class Product(DatesMixin):
    store = models.ForeignKey("Store", on_delete=models.CASCADE)
    title = models.CharField(max_length=225, blank=False, null=False)
    description = models.TextField(null=False, blank=False)
    price = models.DecimalField(max_digits=15, decimal_places=2, blank=False, null=False)
    discount = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(60)])
    available = models.IntegerField(null=False, blank=False, validators=[MinValueValidator(0)])
    category = models.CharField(choices=CATEGORIES_CHOICE, max_length=15)
    label = models.CharField(choices=LABEL_CHOICE, max_length=50, default="NEW")
    visibility = models.BooleanField(default=True)
    average_rating = models.DecimalField(max_digits=4,decimal_places=2,default=0.00,validators=[MinValueValidator(0), MaxValueValidator(5)])
    tags = TaggableManager()
    sales = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    sponsored = models.BooleanField(default=False)

    @property
    def sale_price(self):
        return "%.2f" % (float(self.price) * self.discount / 100)

    def set_availability(self, quantity_bought: int):
        self.available -= quantity_bought

    def set_sponsorship(self, switch_to: bool):
        self.sponsored = switch_to


class ProductImg(DatesMixin):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="images", default="", null=True, blank=True)


class Specification(DatesMixin):
    product = models.OneToOneField('Product', on_delete=models.CASCADE)
    serial = models.CharField(max_length=25, unique=True)
    attributes = models.CharField(max_length=250)
    height = models.DecimalField(max_digits=4, decimal_places=2)
    width = models.DecimalField(max_digits=4, decimal_places=2)
    breadth = models.DecimalField(max_digits=4, decimal_places=2)
    weight = models.DecimalField(decimal_places=2, max_digits=4)
    color = models.CharField(max_length=25)
