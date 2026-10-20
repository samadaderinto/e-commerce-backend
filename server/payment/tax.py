"""
Enterprise Hybrid Tax Calculation Engine for ProAce Commerce.

Option C Architecture (Hybrid / Enterprise Standard):
- Local Database & Memory Table Engine by default:
    Fast, resilient, offline-safe, zero external network dependencies.
    Resolves destination-based jurisdictions (state, zip prefix), physical vs digital taxability,
    and shipping fee taxability.
- Stripe Tax Provider (optional pluggable external API):
    Delegates to Stripe Tax API when TAX_PROVIDER='stripe' and STRIPE_TAX_ENABLED=True.
    Automatically degrades gracefully to LocalTaxProvider if offline, unconfigured, or on API error.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Protocol, Sequence

from django.conf import settings

logger = logging.getLogger(__name__)

# Standard US 2-letter state code mapping
US_STATE_MAP: Dict[str, str] = {
    "alabama": "AL",
    "al": "AL",
    "alaska": "AK",
    "ak": "AK",
    "arizona": "AZ",
    "az": "AZ",
    "arkansas": "AR",
    "ar": "AR",
    "california": "CA",
    "ca": "CA",
    "colorado": "CO",
    "co": "CO",
    "connecticut": "CT",
    "ct": "CT",
    "delaware": "DE",
    "de": "DE",
    "district of columbia": "DC",
    "dc": "DC",
    "washington dc": "DC",
    "florida": "FL",
    "fl": "FL",
    "georgia": "GA",
    "ga": "GA",
    "hawaii": "HI",
    "hi": "HI",
    "idaho": "ID",
    "id": "ID",
    "illinois": "IL",
    "il": "IL",
    "indiana": "IN",
    "ind": "IN",
    "iowa": "IA",
    "ia": "IA",
    "kansas": "KS",
    "ks": "KS",
    "kentucky": "KY",
    "ky": "KY",
    "louisiana": "LA",
    "la": "LA",
    "maine": "ME",
    "me": "ME",
    "maryland": "MD",
    "md": "MD",
    "massachusetts": "MA",
    "ma": "MA",
    "michigan": "MI",
    "mi": "MI",
    "minnesota": "MN",
    "mn": "MN",
    "mississippi": "MS",
    "ms": "MS",
    "missouri": "MO",
    "mo": "MO",
    "montana": "MT",
    "mt": "MT",
    "nebraska": "NE",
    "ne": "NE",
    "nevada": "NV",
    "nv": "NV",
    "new hampshire": "NH",
    "nh": "NH",
    "new jersey": "NJ",
    "nj": "NJ",
    "new mexico": "NM",
    "nm": "NM",
    "new york": "NY",
    "ny": "NY",
    "north carolina": "NC",
    "nc": "NC",
    "north dakota": "ND",
    "nd": "ND",
    "ohio": "OH",
    "oh": "OH",
    "oklahoma": "OK",
    "ok": "OK",
    "oregon": "OR",
    "or": "OR",
    "pennsylvania": "PA",
    "pa": "PA",
    "rhode island": "RI",
    "ri": "RI",
    "south carolina": "SC",
    "sc": "SC",
    "south dakota": "SD",
    "sd": "SD",
    "tennessee": "TN",
    "tn": "TN",
    "texas": "TX",
    "tx": "TX",
    "utah": "UT",
    "ut": "UT",
    "vermont": "VT",
    "vt": "VT",
    "virginia": "VA",
    "va": "VA",
    "washington": "WA",
    "wa": "WA",
    "west virginia": "WV",
    "wv": "WV",
    "wisconsin": "WI",
    "wi": "WI",
    "wyoming": "WY",
    "wy": "WY",
}

# Standard statutory/average combined rates for all 50 states + DC
DEFAULT_US_JURISDICTIONS: List[Dict[str, Any]] = [
    {
        "state": "AL",
        "name": "Alabama (State + Avg Local)",
        "rate": Decimal("0.0929"),
        "tax_shipping": False,
        "tax_digital": True,
    },
    {
        "state": "AK",
        "name": "Alaska (Local Only)",
        "rate": Decimal("0.0182"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "AZ",
        "name": "Arizona (State + Avg Local)",
        "rate": Decimal("0.0837"),
        "tax_shipping": False,
        "tax_digital": True,
    },
    {
        "state": "AR",
        "name": "Arkansas (State + Avg Local)",
        "rate": Decimal("0.0944"),
        "tax_shipping": True,
        "tax_digital": False,
    },
    {
        "state": "CA",
        "name": "California (State + Avg Local)",
        "rate": Decimal("0.0885"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "CO",
        "name": "Colorado (State + Avg Local)",
        "rate": Decimal("0.0781"),
        "tax_shipping": False,
        "tax_digital": True,
    },
    {
        "state": "CT",
        "name": "Connecticut (State Rate)",
        "rate": Decimal("0.0635"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "DE",
        "name": "Delaware (Tax-Free)",
        "rate": Decimal("0.0000"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "DC",
        "name": "District of Columbia",
        "rate": Decimal("0.0600"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "FL",
        "name": "Florida (State + Avg Local)",
        "rate": Decimal("0.0700"),
        "tax_shipping": True,
        "tax_digital": False,
    },
    {
        "state": "GA",
        "name": "Georgia (State + Avg Local)",
        "rate": Decimal("0.0741"),
        "tax_shipping": True,
        "tax_digital": False,
    },
    {
        "state": "HI",
        "name": "Hawaii (General Excise)",
        "rate": Decimal("0.0450"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "ID",
        "name": "Idaho (State + Avg Local)",
        "rate": Decimal("0.0602"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "IL",
        "name": "Illinois (State + Avg Local)",
        "rate": Decimal("0.0886"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "IN",
        "name": "Indiana (State Rate)",
        "rate": Decimal("0.0700"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "IA",
        "name": "Iowa (State + Avg Local)",
        "rate": Decimal("0.0694"),
        "tax_shipping": False,
        "tax_digital": True,
    },
    {
        "state": "KS",
        "name": "Kansas (State + Avg Local)",
        "rate": Decimal("0.0871"),
        "tax_shipping": True,
        "tax_digital": False,
    },
    {
        "state": "KY",
        "name": "Kentucky (State Rate)",
        "rate": Decimal("0.0600"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "LA",
        "name": "Louisiana (State + Avg Local)",
        "rate": Decimal("0.0956"),
        "tax_shipping": False,
        "tax_digital": True,
    },
    {
        "state": "ME",
        "name": "Maine (State Rate)",
        "rate": Decimal("0.0550"),
        "tax_shipping": False,
        "tax_digital": True,
    },
    {
        "state": "MD",
        "name": "Maryland (State Rate)",
        "rate": Decimal("0.0600"),
        "tax_shipping": False,
        "tax_digital": True,
    },
    {
        "state": "MA",
        "name": "Massachusetts (State Rate)",
        "rate": Decimal("0.0625"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "MI",
        "name": "Michigan (State Rate)",
        "rate": Decimal("0.0600"),
        "tax_shipping": True,
        "tax_digital": False,
    },
    {
        "state": "MN",
        "name": "Minnesota (State + Avg Local)",
        "rate": Decimal("0.0804"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "MS",
        "name": "Mississippi (State Rate)",
        "rate": Decimal("0.0707"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "MO",
        "name": "Missouri (State + Avg Local)",
        "rate": Decimal("0.0839"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "MT",
        "name": "Montana (Tax-Free)",
        "rate": Decimal("0.0000"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "NE",
        "name": "Nebraska (State + Avg Local)",
        "rate": Decimal("0.0697"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "NV",
        "name": "Nevada (State + Avg Local)",
        "rate": Decimal("0.0824"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "NH",
        "name": "New Hampshire (Tax-Free)",
        "rate": Decimal("0.0000"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "NJ",
        "name": "New Jersey (State Rate)",
        "rate": Decimal("0.0660"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "NM",
        "name": "New Mexico (Gross Receipts)",
        "rate": Decimal("0.0772"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "NY",
        "name": "New York (State + Avg Local)",
        "rate": Decimal("0.0852"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "NC",
        "name": "North Carolina (State + Avg Local)",
        "rate": Decimal("0.0700"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "ND",
        "name": "North Dakota (State + Avg Local)",
        "rate": Decimal("0.0697"),
        "tax_shipping": True,
        "tax_digital": False,
    },
    {
        "state": "OH",
        "name": "Ohio (State + Avg Local)",
        "rate": Decimal("0.0724"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "OK",
        "name": "Oklahoma (State + Avg Local)",
        "rate": Decimal("0.0899"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "OR",
        "name": "Oregon (Tax-Free)",
        "rate": Decimal("0.0000"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "PA",
        "name": "Pennsylvania (State + Avg Local)",
        "rate": Decimal("0.0634"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "RI",
        "name": "Rhode Island (State Rate)",
        "rate": Decimal("0.0700"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "SC",
        "name": "South Carolina (State + Avg Local)",
        "rate": Decimal("0.0744"),
        "tax_shipping": True,
        "tax_digital": False,
    },
    {
        "state": "SD",
        "name": "South Dakota (State + Avg Local)",
        "rate": Decimal("0.0420"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "TN",
        "name": "Tennessee (State + Avg Local)",
        "rate": Decimal("0.0955"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "TX",
        "name": "Texas (State + Avg Local)",
        "rate": Decimal("0.0820"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "UT",
        "name": "Utah (State + Avg Local)",
        "rate": Decimal("0.0725"),
        "tax_shipping": False,
        "tax_digital": True,
    },
    {
        "state": "VT",
        "name": "Vermont (State Rate)",
        "rate": Decimal("0.0636"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "VA",
        "name": "Virginia (State + Avg Local)",
        "rate": Decimal("0.0577"),
        "tax_shipping": False,
        "tax_digital": False,
    },
    {
        "state": "WA",
        "name": "Washington (State + Avg Local)",
        "rate": Decimal("0.0938"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "WV",
        "name": "West Virginia (State Rate)",
        "rate": Decimal("0.0657"),
        "tax_shipping": True,
        "tax_digital": False,
    },
    {
        "state": "WI",
        "name": "Wisconsin (State + Avg Local)",
        "rate": Decimal("0.0572"),
        "tax_shipping": True,
        "tax_digital": True,
    },
    {
        "state": "WY",
        "name": "Wyoming (State + Avg Local)",
        "rate": Decimal("0.0544"),
        "tax_shipping": True,
        "tax_digital": True,
    },
]

DEFAULT_JURISDICTIONS_DICT: Dict[str, Dict[str, Any]] = {
    j["state"]: j for j in DEFAULT_US_JURISDICTIONS
}


def normalize_us_state(state_raw: str) -> str:
    """Normalize any state representation to 2-letter uppercase postal code."""
    cleaned = "".join(
        c for c in str(state_raw).strip().lower() if c.isalnum() or c.isspace()
    )
    return US_STATE_MAP.get(cleaned, str(state_raw).strip().upper())


@dataclass
class TaxBreakdown:
    """Itemized tax calculation result with full regulatory audit fields."""

    amount: Decimal
    rate: Decimal
    jurisdiction: str
    country: str
    state: str
    postal_code: str
    taxable_merchandise: Decimal
    taxable_shipping: Decimal
    shipping_tax: Decimal
    provider: str
    is_exempt: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "amount": str(self.amount),
            "rate": str(self.rate),
            "jurisdiction": self.jurisdiction,
            "country": self.country,
            "state": self.state,
            "postal_code": self.postal_code,
            "taxable_merchandise": str(self.taxable_merchandise),
            "taxable_shipping": str(self.taxable_shipping),
            "shipping_tax": str(self.shipping_tax),
            "provider": self.provider,
            "is_exempt": self.is_exempt,
            "details": self.details,
        }


class TaxProvider(Protocol):
    """Protocol interface for tax calculation providers."""

    def calculate_tax(
        self,
        items: Sequence[Any],
        subtotal: Decimal,
        shipping_fee: Decimal,
        address: Optional[Any],
    ) -> TaxBreakdown: ...


def normalized_tax_lines(
    items: Sequence[Any], subtotal: Decimal
) -> list[dict[str, Any]]:
    """Normalize model/cart lines and preserve explicitly allocated discounts."""
    from payment.accounting import allocate_amount
    from storefront.serializers import unit_price

    rows: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            amount = Decimal(
                str(
                    item.get(
                        "net_total",
                        item.get(
                            "total",
                            Decimal(str(item.get("unit_price", "0")))
                            * int(item.get("quantity", 1)),
                        ),
                    )
                )
            )
            rows.append({"is_digital": bool(item.get("is_digital")), "amount": amount})
        elif hasattr(item, "product"):
            rows.append(
                {
                    "is_digital": bool(item.product.is_digital),
                    "amount": unit_price(item.product, getattr(item, "variant", ""))
                    * item.quantity,
                }
            )
        else:
            rows.append(
                {
                    "is_digital": bool(getattr(item, "is_digital", False)),
                    "amount": Decimal(str(getattr(item, "total", "0"))),
                }
            )
    gross = sum((row["amount"] for row in rows), Decimal("0"))
    if subtotal < gross:
        amounts = allocate_amount(
            max(Decimal("0"), subtotal), [row["amount"] for row in rows]
        )
        rows = [{**row, "amount": amount} for row, amount in zip(rows, amounts)]
    return rows


class LocalTaxProvider:
    """
    Local Database & Memory Table Tax Provider.

    1. Looks up TaxJurisdiction in DB by country/state/ZIP prefix.
    2. Falls back to static US state defaults if not in DB.
    3. Respects product digital status and shipping taxability.
    4. Falls back to settings.CHECKOUT_TAX_RATE when applicable.
    """

    def calculate_tax(
        self,
        items: Sequence[Any],
        subtotal: Decimal,
        shipping_fee: Decimal,
        address: Optional[Any],
    ) -> TaxBreakdown:
        configured_rate = Decimal(
            str(getattr(settings, "CHECKOUT_TAX_RATE", "0") or "0")
        )

        # If no address is provided (e.g., initial cart state or digital order without address)
        if not address:
            # Check if all items are digital
            is_all_digital = bool(items) and all(
                getattr(getattr(item, "product", item), "is_digital", False)
                if hasattr(item, "product") or hasattr(item, "is_digital")
                else (isinstance(item, dict) and item.get("is_digital", False))
                for item in items
            )
            from payment.accounting import allocate_amount

            rows = normalized_tax_lines(items, subtotal)
            rate = configured_rate
            tax_amt = (max(Decimal("0.00"), subtotal) * rate).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
            return TaxBreakdown(
                amount=tax_amt,
                rate=rate,
                jurisdiction="Worldwide Digital"
                if is_all_digital
                else "Estimated Standard Tax",
                country="US",
                state="",
                postal_code="",
                taxable_merchandise=max(Decimal("0.00"), subtotal),
                taxable_shipping=Decimal("0.00"),
                shipping_tax=Decimal("0.00"),
                provider="local",
                is_exempt=(rate == Decimal("0.00")),
            )

        # Extract address fields whether Model instance or dictionary snapshot
        country_raw = (
            getattr(address, "country", None)
            or (address.get("country") if isinstance(address, dict) else "")
            or "US"
        )
        state_raw = (
            getattr(address, "state", None)
            or (address.get("state") if isinstance(address, dict) else "")
            or ""
        )
        zip_raw = (
            getattr(address, "zip", None)
            or (address.get("zip") if isinstance(address, dict) else "")
            or ""
        )

        country_clean = "".join(c for c in str(country_raw).lower() if c.isalnum())
        is_us = country_clean in {"us", "usa", "unitedstates", "unitedstatesofamerica"}

        # Physical products currently ship only in US; foreign destination has 0 domestic tax
        if not is_us:
            return TaxBreakdown(
                amount=Decimal("0.00"),
                rate=Decimal("0.00"),
                jurisdiction="International (Zero-Rated)",
                country=str(country_raw).upper(),
                state=str(state_raw),
                postal_code=str(zip_raw),
                taxable_merchandise=Decimal("0.00"),
                taxable_shipping=Decimal("0.00"),
                shipping_tax=Decimal("0.00"),
                provider="local",
                is_exempt=True,
            )

        state_code = normalize_us_state(state_raw)
        zip_prefix = str(zip_raw).strip()[:5]

        # 2. Check database TaxJurisdiction table
        from payment.models import TaxJurisdiction

        jurisdiction_record = None
        has_db_jurisdictions = TaxJurisdiction.objects.filter(is_active=True).exists()

        if has_db_jurisdictions:
            if zip_prefix:
                postal_prefixes: list[str] = [
                    zip_prefix[:length] for length in range(1, len(zip_prefix) + 1)
                ]
                jurisdiction_record = TaxJurisdiction.objects.filter(
                    country="US",
                    state=state_code,
                    postal_code__in=postal_prefixes,
                    is_active=True,
                ).order_by('-postal_code', 'pk').first()
            if not jurisdiction_record:
                jurisdiction_record = TaxJurisdiction.objects.filter(
                    country="US", state=state_code, postal_code="", is_active=True
                ).first()

        tax_shipping = False
        tax_digital = True
        jurisdiction_name = f"{state_code} Sales Tax"
        rate = configured_rate

        if not jurisdiction_record and state_code in {"AK", "DE", "MT", "NH", "OR"}:
            rate = Decimal("0.00")
            tax_shipping = False
            tax_digital = False
            jurisdiction_name = f"{state_code} (Sales Tax Free)"
        elif jurisdiction_record:
            rate = Decimal(str(jurisdiction_record.rate))
            tax_shipping = jurisdiction_record.tax_shipping
            tax_digital = jurisdiction_record.tax_digital
            jurisdiction_name = jurisdiction_record.name
        elif has_db_jurisdictions and state_code in DEFAULT_JURISDICTIONS_DICT:
            default_data = DEFAULT_JURISDICTIONS_DICT[state_code]
            rate = default_data["rate"]
            tax_shipping = default_data["tax_shipping"]
            tax_digital = default_data["tax_digital"]
            jurisdiction_name = default_data["name"]
        else:
            # When no database tax rules are configured, fall back to configured CHECKOUT_TAX_RATE.
            # Generic fallback does not tax shipping.
            rate = configured_rate
            tax_shipping = False
            tax_digital = True
            jurisdiction_name = (
                f"{state_code} (Configured Rate)"
                if (state_code and rate > 0)
                else "Standard Tax"
            )

        from payment.accounting import allocate_amount

        rows = normalized_tax_lines(items, subtotal)
        weights = [
            row["amount"] if not row["is_digital"] or tax_digital else Decimal("0")
            for row in rows
        ]
        taxable_merchandise = sum(weights, Decimal("0"))
        merchandise_tax = (taxable_merchandise * rate).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )
        line_taxes = allocate_amount(merchandise_tax, weights)

        # Shipping taxability
        taxable_shipping = Decimal("0.00")
        shipping_tax = Decimal("0.00")
        if tax_shipping and shipping_fee > Decimal("0.00"):
            taxable_shipping = shipping_fee
            shipping_tax = (taxable_shipping * rate).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )

        total_tax = merchandise_tax + shipping_tax

        return TaxBreakdown(
            amount=total_tax,
            rate=rate,
            jurisdiction=jurisdiction_name,
            country="US",
            state=state_code,
            postal_code=zip_prefix,
            taxable_merchandise=taxable_merchandise,
            taxable_shipping=taxable_shipping,
            shipping_tax=shipping_tax,
            provider="local",
            is_exempt=(total_tax == Decimal("0.00")),
            details={
                "tax_shipping": tax_shipping,
                "tax_digital": tax_digital,
                "merchandise_tax": str(merchandise_tax),
                "line_taxes": [str(amount) for amount in line_taxes],
            },
        )


class StripeTaxProvider:
    """
    Stripe Tax External Provider.

    Calls stripe.tax.Calculation.create when configured.
    Falls back cleanly to LocalTaxProvider if disabled, offline, or upon error.
    """

    def __init__(self) -> None:
        self.fallback_provider = LocalTaxProvider()

    def calculate_tax(
        self,
        items: Sequence[Any],
        subtotal: Decimal,
        shipping_fee: Decimal,
        address: Optional[Any],
    ) -> TaxBreakdown:
        stripe_secret = str(getattr(settings, "STRIPE_SECRET", "") or "").strip()
        stripe_tax_enabled = bool(getattr(settings, "STRIPE_TAX_ENABLED", False))

        if not stripe_tax_enabled or not stripe_secret or not address:
            return self.fallback_provider.calculate_tax(
                items, subtotal, shipping_fee, address
            )

        try:
            import stripe

            stripe.api_key = stripe_secret

            country_raw = (
                getattr(address, "country", None)
                or (address.get("country") if isinstance(address, dict) else "")
                or "US"
            )
            state_raw = (
                getattr(address, "state", None)
                or (address.get("state") if isinstance(address, dict) else "")
                or ""
            )
            zip_raw = (
                getattr(address, "zip", None)
                or (address.get("zip") if isinstance(address, dict) else "")
                or ""
            )
            city_raw = (
                getattr(address, "city", None)
                or (address.get("city") if isinstance(address, dict) else "")
                or ""
            )
            street_raw = (
                getattr(address, "address", None)
                or (address.get("address") if isinstance(address, dict) else "")
                or ""
            )

            country_clean = "".join(
                character
                for character in str(country_raw).lower()
                if character.isalnum()
            )
            if country_clean not in {
                "us",
                "usa",
                "unitedstates",
                "unitedstatesofamerica",
            }:
                return self.fallback_provider.calculate_tax(
                    items, subtotal, shipping_fee, address
                )
            state_code = normalize_us_state(state_raw)
            clean_subtotal = max(Decimal("0.00"), subtotal)

            calc_params: Dict[str, Any] = {
                "currency": str(getattr(settings, "STRIPE_CURRENCY", "usd")).lower(),
                "expand": ["line_items"],
                "line_items": [
                    {
                        "amount": int(row["amount"] * 100),
                        "reference": f"line_{index}",
                        "tax_behavior": "exclusive",
                    }
                    for index, row in enumerate(
                        normalized_tax_lines(items, clean_subtotal)
                    )
                    if row["amount"] > 0
                ],
                "customer_details": {
                    "address": {
                        "country": "US",
                        "state": state_code,
                        "postal_code": str(zip_raw).strip()[:10],
                        "city": str(city_raw).strip()[:100],
                        "line1": str(street_raw).strip()[:100],
                    },
                    "address_source": "shipping",
                },
            }

            if shipping_fee > Decimal("0.00"):
                calc_params["shipping_cost"] = {
                    "amount": int(shipping_fee * 100),
                    "tax_behavior": "exclusive",
                }

            calculation = stripe.tax.Calculation.create(**calc_params)

            exclusive_cents = int(getattr(calculation, "tax_amount_exclusive", 0) or 0)
            amount = (Decimal(exclusive_cents) / Decimal(100)).quantize(Decimal(".01"))

            from payment.accounting import allocate_amount

            rows = normalized_tax_lines(items, clean_subtotal)
            shipping_cost = getattr(calculation, "shipping_cost", None)
            raw_shipping_tax = (
                getattr(shipping_cost, "amount_tax", 0) if shipping_cost else 0
            )
            shipping_tax = (
                Decimal(raw_shipping_tax) / 100
                if isinstance(raw_shipping_tax, (int, str))
                else Decimal("0")
            )
            line_taxes = allocate_amount(
                max(Decimal("0"), amount - shipping_tax),
                [row["amount"] for row in rows],
            )
            expanded = getattr(calculation, "line_items", None)
            expanded_rows = getattr(expanded, "data", []) if expanded else []
            if isinstance(expanded_rows, list) and expanded_rows:
                exact_taxes = [Decimal("0") for _ in rows]
                for line in expanded_rows:
                    index = int(line.reference.removeprefix("line_"))
                    exact_taxes[index] = Decimal(line.amount_tax) / 100
                if sum(exact_taxes, Decimal("0")) + shipping_tax != amount:
                    raise ValueError("Tax calculation line totals are inconsistent.")
                line_taxes = exact_taxes
            effective_rate = (
                (amount / (clean_subtotal + shipping_fee)).quantize(Decimal(".0001"))
                if (clean_subtotal + shipping_fee) > 0
                else Decimal("0.0000")
            )

            jurisdiction = f"{state_code} (Stripe Tax)"
            breakdown_list = getattr(calculation, "tax_breakdown", []) or []
            if breakdown_list and hasattr(breakdown_list[0], "jurisdiction"):
                jur_obj = getattr(breakdown_list[0], "jurisdiction", None)
                if jur_obj and hasattr(jur_obj, "display_name"):
                    jurisdiction = jur_obj.display_name

            return TaxBreakdown(
                amount=amount,
                rate=effective_rate,
                jurisdiction=jurisdiction,
                country="US",
                state=state_code,
                postal_code=str(zip_raw),
                taxable_merchandise=clean_subtotal,
                taxable_shipping=shipping_fee,
                shipping_tax=shipping_tax,
                provider="stripe",
                is_exempt=(amount == Decimal("0.00")),
                details={
                    "stripe_calculation_id": getattr(calculation, "id", ""),
                    "line_taxes": [str(value) for value in line_taxes],
                },
            )

        except Exception as exc:
            logger.warning(
                "Stripe Tax calculation failed: %s; falling back to LocalTaxProvider",
                exc,
            )
            return self.fallback_provider.calculate_tax(
                items, subtotal, shipping_fee, address
            )


def get_tax_provider() -> TaxProvider:
    """Factory function returning the configured tax provider."""
    provider_name = str(getattr(settings, "TAX_PROVIDER", "local")).lower().strip()
    if provider_name == "stripe" and getattr(settings, "STRIPE_TAX_ENABLED", False):
        return StripeTaxProvider()
    return LocalTaxProvider()


def calculate_tax(
    items: Sequence[Any],
    subtotal: Decimal,
    shipping_fee: Decimal = Decimal("0.00"),
    address: Optional[Any] = None,
) -> TaxBreakdown:
    """
    Public entry point for calculating sales tax.
    Delegates to the active hybrid tax provider.
    """
    provider = get_tax_provider()
    return provider.calculate_tax(items, subtotal, shipping_fee, address)
