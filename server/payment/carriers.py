"""Direct carrier rating adapters. Live failures never become invented rates."""
import base64
import os
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

CARRIERS = {'USPS', 'UPS', 'FEDEX', 'DHL'}


def env(name, default=''):
    return (os.environ.get(name) or default).strip()


def request_json(url, *, data=None, headers=None, form=False):
    response = requests.post(url, data=data if form else None, json=None if form else data,
                             headers=headers or {}, timeout=8)
    response.raise_for_status()
    return response.json()


def basic(key, secret):
    return 'Basic ' + base64.b64encode(f'{key}:{secret}'.encode()).decode()


def oauth(carrier, base, path):
    key, secret = env(f'{carrier}_CLIENT_ID'), env(f'{carrier}_CLIENT_SECRET')
    if not key or not secret:
        raise ValueError('Carrier credentials missing')
    if carrier == 'UPS':
        return request_json(base + path, data={'grant_type': 'client_credentials'},
                            headers={'Authorization': basic(key, secret)}, form=True)['access_token']
    if carrier == 'USPS':
        return request_json(base + path, data={'grant_type': 'client_credentials', 'client_id': key, 'client_secret': secret})['access_token']
    return request_json(base + path, data={'grant_type': 'client_credentials', 'client_id': key, 'client_secret': secret}, form=True)['access_token']


def option(carrier, code, name, amount, currency='USD', description='Carrier calculated rate'):
    price = Decimal(str(amount))
    if currency.upper() != 'USD' or not price.is_finite() or price < 0:
        raise ValueError('Unsupported carrier amount or currency')
    return {'carrier': carrier, 'service_id': f'{carrier.lower()}_{code}', 'name': name,
            'amount': str(price.quantize(Decimal('.01'))), 'currency': currency.upper(),
            'description': description, 'is_default': False, 'source': 'live'}

# Why hardcoded values dawg
def dimensions(package=None):
    package = package or {}
    return {key: float(package.get(key) or 1)
            for key in ('length', 'width', 'height')}


def live_rates(carrier, origin, destination, weight, package=None):
    sandbox = env('SHIPPING_SANDBOX', 'true').lower() == 'true'
    dims = dimensions(package)
    if carrier == 'USPS':
        base = 'https://apis-tem.usps.com' if sandbox else 'https://apis.usps.com'
        token = oauth(carrier, base, '/oauth2/v3/token')
        rates = []
        for code, mail_class, name in [('ground_advantage', 'USPS_GROUND_ADVANTAGE', 'USPS Ground Advantage'),
                                      ('priority_mail', 'PRIORITY_MAIL', 'USPS Priority Mail'),
                                      ('priority_express', 'PRIORITY_MAIL_EXPRESS', 'USPS Priority Mail Express')]:
            result = request_json(base + '/prices/v3/base-rates/search', headers={'Authorization': f'Bearer {token}'},
                                  data={'originZIPCode': origin, 'destinationZIPCode': destination,
                                        'weight': float(weight), **dims, 'mailClass': mail_class,
                                        'processingCategory': 'MACHINABLE', 'destinationEntryFacilityType': 'NONE',
                                        'rateIndicator': 'DR', 'priceType': 'RETAIL', 'mailingDate': timezone.now().date().isoformat()})
            rates.append(option(carrier, code, name, result['totalBasePrice']))
        return rates
    if carrier == 'UPS':
        base = 'https://wwwcie.ups.com' if sandbox else 'https://onlinetools.ups.com'
        token = oauth(carrier, base, '/security/v1/oauth/token')
        address = lambda zipcode: {'Address': {'PostalCode': zipcode, 'CountryCode': 'US'}}
        shipper = {**address(origin), 'ShipperNumber': env('UPS_ACCOUNT_NUMBER')}
        if not shipper['ShipperNumber']:
            raise ValueError('UPS account missing')
        result = request_json(base + '/api/rating/v2409/Shop', headers={'Authorization': f'Bearer {token}'},
                              data={'RateRequest': {'Request': {'RequestOption': 'Shop'}, 'Shipment': {
                                  'Shipper': shipper, 'ShipFrom': address(origin), 'ShipTo': address(destination),
                                  'Package': [{'PackagingType': {'Code': '02'},
                                               'Dimensions': {'UnitOfMeasurement': {'Code': 'IN'}, **{k.title(): str(v) for k, v in dims.items()}},
                                               'PackageWeight': {'UnitOfMeasurement': {'Code': 'LBS'}, 'Weight': str(weight)}}]}}})
        rows = result['RateResponse']['RatedShipment']
        rows = rows if isinstance(rows, list) else [rows]
        names = {'03': 'UPS Ground', '02': 'UPS 2nd Day Air', '01': 'UPS Next Day Air', '12': 'UPS 3 Day Select'}
        descriptions = {'03': '3–5 business days', '02': '2 business days', '01': 'Next business day by 10:30 AM / 12:00 PM', '12': '3 business days'}
        return [option(carrier, row['Service']['Code'], names.get(row['Service']['Code'], 'UPS ' + row['Service']['Code']),
                       row['TotalCharges']['MonetaryValue'], row['TotalCharges']['CurrencyCode'],
                       description=descriptions.get(row['Service']['Code'], 'Carrier calculated rate')) for row in rows]
    if carrier == 'FEDEX':
        base = 'https://apis-sandbox.fedex.com' if sandbox else 'https://apis.fedex.com'
        token = oauth(carrier, base, '/oauth/token')
        account = env('FEDEX_ACCOUNT_NUMBER')
        if not account:
            raise ValueError('FedEx account missing')
        result = request_json(base + '/rate/v1/rates/quotes', headers={'Authorization': f'Bearer {token}'},
                              data={'accountNumber': {'value': account}, 'requestedShipment': {
                                  'shipper': {'address': {'postalCode': origin, 'countryCode': 'US'}},
                                  'recipient': {'address': {'postalCode': destination, 'countryCode': 'US'}},
                                  'pickupType': 'DROPOFF_AT_FEDEX_LOCATION', 'rateRequestType': ['ACCOUNT'],
                                  'requestedPackageLineItems': [{'weight': {'units': 'LB', 'value': float(weight)},
                                                                 'dimensions': {**{k: int(v) for k, v in dims.items()}, 'units': 'IN'}}]}})
        names = {'FEDEX_GROUND': 'FedEx Ground', 'FEDEX_2_DAY': 'FedEx 2Day', 'PRIORITY_OVERNIGHT': 'FedEx Priority Overnight', 'STANDARD_OVERNIGHT': 'FedEx Standard Overnight'}
        descriptions = {'FEDEX_GROUND': '1–5 business days', 'FEDEX_2_DAY': '2 business days', 'PRIORITY_OVERNIGHT': 'Next business day morning delivery', 'STANDARD_OVERNIGHT': 'Next business day by 3:00 PM'}
        rates = []
        for row in result['output']['rateReplyDetails']:
            amount = row['ratedShipmentDetails'][0]['totalNetCharge']
            if isinstance(amount, dict):
                currency, amount = amount['currency'], amount['amount']
            else:
                currency = row['ratedShipmentDetails'][0].get('currency', 'USD')
            svc_type = row['serviceType']
            name = names.get(svc_type, row.get('serviceName', svc_type))
            desc = descriptions.get(svc_type, 'Carrier calculated rate')
            rates.append(option(carrier, svc_type, name, amount, currency, description=desc))
        return rates
    
    username, password, account = env('DHL_API_KEY'), env('DHL_API_SECRET'), env('DHL_ACCOUNT_NUMBER')
    if not all([username, password, account]):
        raise ValueError('DHL credentials missing')
    base = 'https://express.api.dhl.com/mydhlapi' + ('/test' if sandbox else '')
    result = request_json(base + '/rates', headers={'Authorization': basic(username, password)}, data={
        'customerDetails': {'shipperDetails': {'postalCode': origin, 'countryCode': 'US'},
                            'receiverDetails': {'postalCode': destination, 'countryCode': 'US'}},
        'accounts': [{'typeCode': 'shipper', 'number': account}],
        'plannedShippingDateAndTime': (timezone.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SGMT+00:00"),
        'unitOfMeasurement': 'imperial', 'isCustomsDeclarable': False,
        'packages': [{'weight': float(weight), 'dimensions': dims}]})
    names = {'H': 'DHL Economy Select', 'T': 'DHL Express 12:00', 'D': 'DHL Express Worldwide', 'P': 'DHL Express Worldwide', 'N': 'DHL Express Domestic'}
    descriptions = {'H': '2–5 business days', 'T': 'Next business day by 12:00 PM', 'D': '1–3 business days', 'P': '1–3 business days', 'N': 'Next business day'}
    rates = []
    for row in result.get('products', []):
        price = next((p for p in row.get('totalPrice', []) if p.get('currencyType') == 'BILLC'), None)
        if not price or 'price' not in price or 'priceCurrency' not in price:
            continue
        code = row.get('productCode', '')
        raw_name = str(row.get('productName', '')).strip()
        # Strictly ignore partner/last-mile USPS products returned by DHL API so USPS never mixes with DHL
        if 'usps' in raw_name.lower() or 'usps' in str(code).lower():
            continue
        name = names.get(code)
        if not name:
            if not raw_name.upper().startswith('DHL '):
                name = f'DHL {raw_name}' if raw_name else 'DHL Economy Select'
            else:
                name = raw_name
        desc = descriptions.get(code, 'Carrier calculated rate')
        rates.append(option(carrier, code, name, price['price'], price['priceCurrency'], description=desc))
    return rates


def calculate_carrier_rates(carrier, origin, destination, weight, subtotal, physical, package=None):
    carrier = carrier.upper()
    if carrier not in CARRIERS:
        raise ValidationError({'carrier': 'Choose USPS, UPS, FEDEX, or DHL.'})
    if not physical:
        return [{**option('DIGITAL', 'delivery', 'Digital Delivery', '0.00'), 'service_id': 'digital_delivery', 'is_default': True}]
    from payment.geo import military_zip_region
    if military_zip_region(destination) and carrier != 'USPS':
        raise ValidationError({'carrier': 'APO/FPO/DPO military addresses require USPS with our supported shipping services.'})
    mode = env('SHIPPING_RATE_MODE', getattr(settings, 'SHIPPING_RATE_MODE', 'demo' if settings.DEBUG else 'live'))
    if mode == 'demo':
        # Explicit development fixtures; never silently used when a live carrier fails.
        from payment.usps import _calculate_standard_usps_rates
        if carrier == 'USPS':
            rates = [{**row, 'carrier': carrier, 'currency': 'USD', 'source': 'demo'} for row in _calculate_standard_usps_rates(weight)]
        else:
            services = {
                'UPS': [
                    ('03', 'UPS Ground', '8.00', '3–5 business days'),
                    ('02', 'UPS 2nd Day Air', '22.00', '2 business days'),
                    ('01', 'UPS Next Day Air', '35.00', 'Next business day by 10:30 AM / 12:00 PM'),
                ],
                'FEDEX': [
                    ('FEDEX_GROUND', 'FedEx Ground', '9.00', '1–5 business days'),
                    ('FEDEX_2_DAY', 'FedEx 2Day', '24.00', '2 business days'),
                    ('PRIORITY_OVERNIGHT', 'FedEx Priority Overnight', '38.00', 'Next business day morning delivery'),
                ],
                'DHL': [
                    ('ECONOMY_SELECT', 'DHL Economy Select', '18.00', '2–5 business days'),
                    ('EXPRESS_1200', 'DHL Express 12:00', '32.00', 'Next business day by 12:00 PM'),
                    ('EXPRESS_WORLDWIDE', 'DHL Express Worldwide', '42.00', '1–3 business days'),
                ],
            }[carrier]
            rates = [{**option(carrier, code, name, amount, description=desc), 'source': 'demo'} for code, name, amount, desc in services]
    elif mode == 'live':
        try:
            rates = live_rates(carrier, origin, destination, weight, package)
        except (requests.RequestException, ValueError, KeyError, TypeError, StopIteration, ArithmeticError):
            raise ValidationError({'carrier': f'{carrier} rates are unavailable. Choose another carrier or retry.'})
    else:
        raise ValidationError({'carrier': 'Shipping rate configuration is invalid.'})
    rates.sort(key=lambda row: Decimal(row['amount']))
    if not rates:
        raise ValidationError({'carrier': 'No eligible services for this shipment.'})
    rates[0]['is_default'] = True
    if subtotal >= getattr(settings, 'FREE_SHIPPING_THRESHOLD', Decimal('100000')):
        rates[0]['amount'] = '0.00'
    return rates
