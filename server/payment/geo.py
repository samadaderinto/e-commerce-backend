"""Military postal address consistency and supported carrier policy."""
import re
from typing import Any
from rest_framework.exceptions import ValidationError

MILITARY_STATES = {
    'AA': 'AA', 'AE': 'AE', 'AP': 'AP',
    'ARMED FORCES AMERICAS': 'AA',
    'ARMED FORCES EUROPE / AFRICA / MIDDLE EAST': 'AE',
    'ARMED FORCES PACIFIC': 'AP',
}
MILITARY_CITIES = {'APO', 'FPO', 'DPO'}


def military_zip_region(zipcode: str) -> str | None:
    if not re.fullmatch(r'\d{5}(?:-\d{4})?', str(zipcode).strip()):
        return None
    prefix = int(str(zipcode).strip()[:3])
    if 90 <= prefix <= 98:
        return 'AE'
    if prefix == 340:
        return 'AA'
    if 962 <= prefix <= 966:
        return 'AP'
    return None


def is_military_address(address: Any) -> bool:
    return bool(address and (
        str(address.state or '').strip().upper() in MILITARY_STATES
        or str(address.city or '').strip().upper() in MILITARY_CITIES
        or military_zip_region(str(address.zip or ''))
    ))


def validate_military_address(city: str, state: str, zipcode: str, country: str) -> None:
    region = MILITARY_STATES.get(state.strip().upper())
    military_city = city.strip().upper() in MILITARY_CITIES
    us_country = ''.join(c for c in country.lower() if c.isalnum()) in {'us', 'usa', 'unitedstates', 'unitedstatesofamerica'}
    zip_region = military_zip_region(zipcode) if us_country else None
    if not (region or military_city or zip_region):
        return
    if ''.join(c for c in country.lower() if c.isalnum()) not in {'us', 'usa', 'unitedstates', 'unitedstatesofamerica'}:
        raise ValidationError({'country': 'Use United States for APO/FPO/DPO military postal addresses.'})
    if not military_city:
        raise ValidationError({'city': 'Military addresses must use APO, FPO or DPO as the city.'})
    if not region:
        raise ValidationError({'state': 'Military addresses must use AA, AE or AP as the state.'})
    if zip_region != region:
        raise ValidationError({'zip': 'Military ZIP must match the region: AA 340xx, AE 090xx–098xx, AP 962xx–966xx.'})


def validate_military_carrier(address: Any, carrier: str) -> None:
    if is_military_address(address) and carrier.upper() != 'USPS':
        raise ValidationError({'carrier': 'APO/FPO/DPO military addresses require USPS with our supported shipping services.'})
