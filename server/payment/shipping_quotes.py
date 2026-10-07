"""Shipping selections bound to shopper, cart, destination, and expiry."""
import hashlib
import json
from decimal import Decimal
from django.core import signing
from rest_framework.exceptions import ValidationError
from payment.models import ShippingQuote


def fingerprint(cart, address):
    from storefront.serializers import AddressSerializer, unit_price
    rows = [(item.product_id, item.quantity, str(unit_price(item.product)),
             str(item.product.weight), item.product.is_digital, item.product.store_id)
            for item in cart.cart_items.select_related('product').order_by('product_id')]
    payload = {'cart': cart.pk, 'rows': rows, 'address': AddressSerializer(address).data if address else None}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def issue_quote(rate, user, cart, address):
    quote = ShippingQuote.objects.create(user=user, rate=rate, cart_fingerprint=fingerprint(cart, address))
    # Short enough for Stripe metadata even when the rate describes multiple shipments.
    return signing.dumps({'id': quote.pk}, salt='shipping-quote')


def verify_quote(token, user, cart, address, service, *, paid=False):
    try:
        payload = signing.loads(token, salt='shipping-quote', max_age=604800 if paid else 900)
        quote = ShippingQuote.objects.get(pk=payload['id'], user=user)
        rate = quote.rate
        if quote.cart_fingerprint != fingerprint(cart, address) or rate['service_id'] != service:
            raise ValueError()
        amount = Decimal(rate['amount'])
        if not amount.is_finite() or amount < 0:
            raise ValueError()
        return rate
    except (ShippingQuote.DoesNotExist, signing.BadSignature, KeyError, TypeError, ValueError, ArithmeticError):
        raise ValidationError({'shipping_quote': 'Shipping quote expired or cart/address changed. Fetch rates again.'})


def cart_rates(carrier, cart, address):
    from store.models import StoreAddress
    from storefront.serializers import unit_price
    from payment.carriers import calculate_carrier_rates
    groups = {}
    subtotal = Decimal('0')
    for item in cart.cart_items.select_related('product__store'):
        subtotal += unit_price(item.product) * item.quantity
        if not item.product.is_digital:
            origin = StoreAddress.objects.filter(store=item.product.store, is_default=True).first()
            zipcode = origin.zip if origin and origin.zip else '33602'
            group = groups.setdefault(zipcode, {'weight': Decimal('0'), 'package': {}})
            group['weight'] += Decimal(str(item.product.weight or '1')) * item.quantity
            for field in ('length', 'width', 'height'):
                value = getattr(item.product, field, None)
                if value:
                    group['package'][field] = max(Decimal(str(value)), Decimal(str(group['package'].get(field, '0'))))
    if not groups:
        return calculate_carrier_rates(carrier, '', '', Decimal('0'), subtotal, False)
    combined = None
    for origin, group in groups.items():
        options = calculate_carrier_rates(carrier, origin, address.zip, group['weight'], Decimal('0'), True, group['package'])
        by_service = {row['service_id']: {**row, 'shipments': [{'origin_zip': origin, 'weight_lbs': str(group['weight']), 'amount': row['amount']}]} for row in options}
        if combined is None:
            combined = by_service
        else:
            for service in list(combined):
                if service not in by_service:
                    del combined[service]
                    continue
                row = by_service[service]
                combined[service]['amount'] = str(Decimal(combined[service]['amount']) + Decimal(row['amount']))
                combined[service]['shipments'] += row['shipments']
    rates = sorted(combined.values(), key=lambda row: Decimal(row['amount']))
    rates = [r for r in rates if r.get('carrier') == carrier]
    if not rates:
        raise ValidationError({'carrier': 'No service covers every shipment in this cart.'})
    from django.conf import settings
    if subtotal >= getattr(settings, 'FREE_SHIPPING_THRESHOLD', Decimal('100000')):
        rates[0]['amount'] = '0.00'
    for i, rate in enumerate(rates):
        rate['is_default'] = i == 0
    return rates
