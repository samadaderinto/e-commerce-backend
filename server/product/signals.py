from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from product.models import Product
from product.search import schedule_delete_product, schedule_index_product


@receiver(post_save, sender=Product)
def sync_product_to_search(sender, instance, **kwargs):
    schedule_index_product(instance.pk)


@receiver(post_delete, sender=Product)
def remove_product_from_search(sender, instance, **kwargs):
    schedule_delete_product(instance.pk)
