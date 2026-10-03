from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from cart.models import Cart, CartItem
from core.models import Address, User
from payment.models import DeliveryInfo, Order
from product.models import Product
from store.models import Store, StoreAddress, StoreInfo
from storefront.serializers import unit_price


PRODUCTS = [
    ('Studio wireless headphones', 'Soundform', 'electronics', '68500', 20, '1546435770-a3e426bf472b', 'Immersive sound. A little more quiet. Soft over-ear cushions, wireless listening and an adjustable fit for your everyday soundtrack.'),
    ('Everyday canvas backpack', 'Daytrip', 'outwear', '24500', 10, '1553062407-98eeb64c6a62', 'A place for everything you carry. A roomy main compartment, padded straps and clean everyday styling.'),
    ('Classic analogue watch', 'Nord', 'electronics', '42000', 15, '1523275335684-37898b6baf30', 'Keep things timeless. A minimal dial and comfortable strap, made for days that turn into evenings.'),
    ('Air runner sneakers', 'Stride', 'sports', '56000', 25, '1542291026-7eec264c27ff', 'Find your everyday pace with a lightweight feel, breathable upper and cushioned sole.'),
    ('Compact mirrorless camera', 'Focus', 'electronics', '485000', 8, '1516035069371-29a1b244cc32', 'For the moments worth keeping. A compact camera for creative photography at home and on the move.'),
    ('Ultralight notebook 14-inch', 'Form', 'computing', '720000', 12, '1496181133206-80ce9b88a853', 'Your work, wherever life takes you. A slim notebook with a generous display and comfortable keyboard.'),
    ('Portable wireless speaker', 'Soundform', 'electronics', '38000', 15, '1608043152269-423dbba4e7e1', 'Take your favourite playlists along. Compact wireless audio for the kitchen, desk or weekend bag.'),
    ('Everyday smartphone', 'Connect', 'phones', '215000', 5, '1511707171634-5f897ff02aa9', 'Stay connected to your day with a bright display, modern design and a comfortable grip.'),
    ('Essential cotton tee', 'Everyday', 'outwear', '12500', 0, '1521572163474-6864f9cf17ab', 'The foundation of a good wardrobe. A soft cotton feel with an easy, relaxed silhouette.'),
    ('Weekend leather sneakers', 'Stride', 'sports', '49500', 10, '1549298916-b41d501d3772', 'An everyday staple. Clean lines and a comfortable fit for relaxed days out.'),
    ('Desk companion headphones', 'Soundform', 'electronics', '32500', 0, '1505740420928-5e560c06d30e', 'Set the mood for focused work or an easy afternoon with comfortable over-ear headphones.'),
    ('Everyday reading collection', 'Chapter', 'books', '18000', 5, '1512820790803-83ca734da794', 'Make a little room for a good read. A thoughtfully selected collection for your next quiet afternoon.'),
]


class Command(BaseCommand):
    help = 'Create an idempotent local sample catalog and customer/seller accounts.'

    def add_arguments(self, parser):
        parser.add_argument('--password', required=True)

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo seeding is disabled outside development.')
        if len(options['password']) < 12:
            raise CommandError('Use a demo password with at least 12 characters.')
        users = []
        for email, first in [('shopper@proace.local', 'Alex'), ('seller@proace.local', 'Jordan')]:
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(email=email, password=options['password'], first_name=first, last_name='Demo', phone1='+2348012345678')
            users.append(user)
        buyer, seller = users
        store, _ = Store.objects.get_or_create(username='proace-select', defaults={'user': seller, 'name': 'Proace Select'})
        StoreInfo.objects.get_or_create(store=store, defaults={'email': 'seller@proace.local', 'bio': 'Considered essentials for everyday life.'})
        StoreAddress.objects.get_or_create(store=store, is_default=True, defaults={'address': '401 E Jackson Street', 'city': 'Tampa', 'state': 'Florida', 'country': 'United States', 'zip': '33602'})
        address, _ = Address.objects.get_or_create(user=buyer, address='100 N Tampa Street', defaults={'city': 'Tampa', 'state': 'Florida', 'country': 'United States', 'zip': '33602'})
        products = []
        for index, (title, brand, category, price, discount, image, description) in enumerate(PRODUCTS):
            product, _ = Product.objects.get_or_create(store=store, title=title, defaults={
                'brand': brand, 'category': category, 'price': Decimal(price), 'discount': discount,
                'description': description, 'available': 3 if index == 4 else 18 + index,
                'visibility': True, 'image_url': f'https://images.unsplash.com/photo-{image}?auto=format&fit=crop&w=900&q=85',
            })
            products.append(product)
        for index in range(12):
            reference = f'DEMO-{index + 1:05}'
            if Order.objects.filter(orderId=reference).exists():
                continue
            product = products[index % len(products)]
            quantity = index % 3 + 1
            cart = Cart.objects.create(user=buyer, ordered=True)
            CartItem.objects.create(cart=cart, product=product, quantity=quantity)
            delivery = DeliveryInfo.objects.create(user=buyer, address=address, method='home delivery', delivery_type='standard', total=2500)
            subtotal = unit_price(product) * quantity
            order = Order.objects.create(user=buyer, cart=cart, delivery=delivery, orderId=reference,
                ordered=True, status=['delivered', 'shipped', 'confirmed'][index % 3],
                payment_type='cash_on_delivery', subtotal=subtotal, total=subtotal + 2500,
                items_snapshot=[{'product': product.pk, 'store': store.pk, 'title': product.title, 'image': product.image_url, 'quantity': quantity, 'unit_price': str(unit_price(product))}],
                address_snapshot={'address': address.address, 'city': address.city, 'state': address.state, 'country': address.country, 'zip': address.zip})
            Order.objects.filter(pk=order.pk).update(created=timezone.now() - timedelta(days=index * 2))
        self.stdout.write(self.style.SUCCESS('Local sample catalog ready. Accounts: shopper@proace.local and seller@proace.local.'))
