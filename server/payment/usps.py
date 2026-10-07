"""Development USPS cart estimates and tracking links. Live rating uses carriers.py."""
from decimal import Decimal, ROUND_HALF_UP
import urllib.parse

from django.conf import settings


def _normalize_zip(zip_code: str) -> str:
    """Extract standard 5-digit US ZIP code."""
    cleaned = ''.join(c for c in str(zip_code or '') if c.isdigit())
    return cleaned[:5] if len(cleaned) >= 5 else '33602'


def calculate_usps_rates(
    origin_zip: str,
    destination_zip: str,
    total_weight_lbs: Decimal,
    subtotal: Decimal,
    has_physical_items: bool,
) -> list[dict]:
    """Calculate domestic USPS shipping options for a given cart and destination address."""
    if not has_physical_items:
        return [
            {
                'service_id': 'digital_delivery',
                'name': 'Digital Delivery',
                'description': 'Instant online access & direct download link',
                'amount': '0.00',
                'is_default': True,
            }
        ]

    weight = max(Decimal('0.10'), total_weight_lbs)
    weight_int_lbs = int(weight)
    weight_oz = int((weight - Decimal(weight_int_lbs)) * 16)
    if weight_oz == 0 and weight_int_lbs == 0:
        weight_oz = 2

    origin = _normalize_zip(origin_zip)
    destination = _normalize_zip(destination_zip)
    free_threshold = getattr(settings, 'FREE_SHIPPING_THRESHOLD', Decimal('100000'))
    is_free_eligible = subtotal >= free_threshold

    options = _calculate_standard_usps_rates(weight)

    # Apply free shipping discount if eligible
    if is_free_eligible and options:
        # Lowest cost service becomes free
        options[0]['amount'] = '0.00'
        options[0]['description'] += ' (Free shipping applied)'

    return options


def _calculate_standard_usps_rates(weight_lbs: Decimal) -> list[dict]:
    """Standard commercial base rate table for domestic USPS services."""
    extra_weight = max(Decimal('0'), weight_lbs - Decimal('1.00'))

    ground_rate = (Decimal('5.40') + extra_weight * Decimal('1.25')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    priority_rate = (Decimal('9.80') + extra_weight * Decimal('1.85')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    express_rate = (Decimal('28.50') + extra_weight * Decimal('3.50')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return [
        {
            'service_id': 'usps_ground_advantage',
            'name': 'USPS Ground Advantage',
            'description': '2–5 business days',
            'amount': str(ground_rate),
            'is_default': True,
        },
        {
            'service_id': 'usps_priority_mail',
            'name': 'USPS Priority Mail',
            'description': '1–3 business days with tracking',
            'amount': str(priority_rate),
            'is_default': False,
        },
        {
            'service_id': 'usps_priority_express',
            'name': 'USPS Priority Mail Express',
            'description': '1–2 business days guaranteed',
            'amount': str(express_rate),
            'is_default': False,
        },
    ]


def get_usps_tracking_url(tracking_number: str) -> str:
    """Generate official USPS tracking URL."""
    clean_number = str(tracking_number or '').strip()
    return f"https://tools.usps.com/go/TrackConfirmAction?tLabels={urllib.parse.quote(clean_number)}" if clean_number else ""


def track_usps_shipment(tracking_number: str) -> dict:
    """Return an official tracking link; never fabricate carrier scan events."""
    return {'status': 'unknown', 'summary': 'View the carrier website for current scans.',
            'tracking_number': str(tracking_number or '').strip(),
            'tracking_url': get_usps_tracking_url(tracking_number), 'events': []}
