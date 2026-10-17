"""Shipping selections bound to shopper, cart, destination, and expiry."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any
from django.core import signing
from rest_framework.exceptions import ValidationError
from cart.models import Cart
from core.models import Address
from store.models import StoreAddress
from payment.models import ShippingQuote


def fingerprint(cart: Cart, address: Address | None) -> str:
    from storefront.serializers import AddressSerializer, unit_price
    items = list(cart.cart_items.select_related('product').order_by('product_id', 'variant', 'pk'))
    has_physical = any(not item.product.is_digital for item in items)
    rows = [(item.product_id, item.variant, item.quantity, str(unit_price(item.product, item.variant)),
             str(item.product.weight), item.product.is_digital, item.product.store_id,
             *(str(getattr(item.product, field)) for field in ('length', 'width', 'height')))
            for item in items]
    store_ids = {item.product.store_id for item in items if not item.product.is_digital}
    origins = list(StoreAddress.objects.filter(
        store_id__in=store_ids, is_default=True,
    ).order_by('store_id', 'pk').values('store_id', 'address', 'city', 'state', 'country', 'zip'))
    payload = {'cart': cart.pk, 'rows': rows, 'origins': origins, 'address': AddressSerializer(address).data if (address and has_physical) else None}
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
    from store.services import has_store_address
    from storefront.serializers import unit_price
    from payment.carriers import calculate_carrier_rates
    from payment.geo import validate_military_address, validate_military_carrier
    if address:
        validate_military_address(address.city, address.state, address.zip, address.country)
        validate_military_carrier(address, carrier)
    groups = {}
    subtotal = Decimal('0')
    for item in cart.cart_items.select_related('product__store'):
        subtotal += unit_price(item.product, item.variant) * item.quantity
        if not item.product.is_digital:
            origin = StoreAddress.objects.filter(store=item.product.store, is_default=True).first()
            if not has_store_address(item.product.store):
                raise ValidationError({'store_address': f'Store {item.product.store.name} must configure its default address before shipping can be quoted.'})
            zipcode = origin.zip
            group = groups.setdefault(item.product.store_id, {'origin_zip': zipcode, 'weight': Decimal('0'), 'package': {}})
            group['weight'] += Decimal(str(item.product.weight or '1')) * item.quantity
            for field in ('length', 'width', 'height'):
                value = getattr(item.product, field, None)
                if value:
                    group['package'][field] = max(Decimal(str(value)), Decimal(str(group['package'].get(field, '0'))))
    if not groups:
        return calculate_carrier_rates(carrier, '', '', Decimal('0'), subtotal, False)
    combined = None
    for group in groups.values():
        origin = group['origin_zip']
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
        for shipment in rates[0].get('shipments', []):
            shipment['amount'] = '0.00'
    for i, rate in enumerate(rates):
        rate['is_default'] = i == 0
    return rates
