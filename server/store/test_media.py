from django.core.files.base import ContentFile
from django.db import transaction
from django.test import TestCase

from core.models import User
from product.models import Product, ProductImg
from store.models import Store, StoreImg


class MediaLifecycleTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email='media@example.com', password='test-password')
        self.store = Store.objects.create(user=user, name='Media shop')
        self.product = Product.objects.create(
            store=self.store, title='Photo', description='Photo', price='10',
            discount=0, available=1, category='electronics',
        )

    def test_upload_replace_and_delete(self):
        image = ProductImg.objects.create(product=self.product, image=ContentFile(b'first', name='first.png'))
        storage, original = image.image.storage, image.image.name
        self.assertEqual(storage.open(original).read(), b'first')
        with self.captureOnCommitCallbacks(execute=True):
            image.image = ContentFile(b'second', name='second.png')
            image.save()
        self.assertFalse(storage.exists(original))
        replacement = image.image.name
        self.assertTrue(storage.exists(replacement))
        with self.captureOnCommitCallbacks(execute=True):
            image.delete()
        self.assertFalse(storage.exists(replacement))

    def test_parent_cascade_deletes_product_and_store_images(self):
        product_image = ProductImg.objects.create(product=self.product, image=ContentFile(b'p', name='product.png'))
        store_image = StoreImg.objects.create(store=self.store, url=ContentFile(b's', name='store.png'))
        files = [(field.storage, field.name) for field in [product_image.image, store_image.url]]
        with self.captureOnCommitCallbacks(execute=True):
            self.store.delete()
        for storage, name in files:
            self.assertFalse(storage.exists(name))

    def test_rollback_keeps_image(self):
        image = ProductImg.objects.create(product=self.product, image=ContentFile(b'keep', name='keep.png'))
        storage, name, pk = image.image.storage, image.image.name, image.pk
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    image.delete()
                    raise ValueError('rollback')
            except ValueError:
                pass
        self.assertTrue(ProductImg.objects.filter(pk=pk).exists())
        self.assertTrue(storage.exists(name))
