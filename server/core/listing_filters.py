"""Validated collection criteria applied before pagination and serialization."""
from datetime import datetime, time, timedelta, timezone
from typing import Any, Mapping, TypeVar

from django.db.models import Model, Q, QuerySet
from rest_framework import serializers

Record = TypeVar("Record", bound=Model)


class ListingQuerySerializer(serializers.Serializer):
    status = serializers.CharField(required=False, allow_blank=True)
    payout_method = serializers.CharField(required=False, allow_blank=True)
    entry_type = serializers.CharField(required=False, allow_blank=True)
    source = serializers.CharField(required=False, allow_blank=True)
    transaction_type = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    is_official = serializers.BooleanField(required=False)
    staff_email_verified = serializers.BooleanField(required=False)
    is_digital = serializers.BooleanField(required=False)
    product_type = serializers.CharField(required=False, allow_blank=True)
    type = serializers.CharField(required=False, allow_blank=True)
    validity = serializers.ChoiceField(choices=["", "current", "expired", "upcoming"], required=False)
    created_by = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    min_amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0, required=False)
    max_amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0, required=False)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)
    offset = serializers.IntegerField(min_value=0, default=0)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        for lower, upper in [("start_date", "end_date"), ("min_amount", "max_amount")]:
            if lower in attrs and upper in attrs and attrs[lower] > attrs[upper]:
                raise serializers.ValidationError({upper: "Must be at least the lower bound."})
        return attrs


def filter_records(
    records: QuerySet[Record],
    params: Mapping[str, str],
    *,
    search_fields: tuple[str, ...] = (),
    fields: Mapping[str, str] | None = None,
    date_field: str = "created",
    amount_field: str | None = None,
) -> QuerySet[Record]:
    query = ListingQuerySerializer(data=params)
    query.is_valid(raise_exception=True)
    criteria = query.validated_data
    search = criteria["search"].strip()
    if search and search_fields:
        condition = Q()
        for field in search_fields:
            condition |= Q(**{f"{field}__icontains": search})
        records = records.filter(condition).distinct()
    for parameter, field in (fields or {}).items():
        value = params.get(parameter, "")
        if value:
            model_field = records.model._meta.get_field(field) if "__" not in field else None
            if model_field and model_field.choices:
                value = serializers.ChoiceField(choices=model_field.choices).run_validation(value)
            elif model_field and model_field.get_internal_type() == "BooleanField":
                value = serializers.BooleanField().run_validation(value)
            records = records.filter(**{field: value})
    if criteria.get("start_date"):
        records = records.filter(**{f"{date_field}__gte": datetime.combine(criteria["start_date"], time.min, timezone.utc)})
    if criteria.get("end_date"):
        records = records.filter(**{f"{date_field}__lt": datetime.combine(criteria["end_date"] + timedelta(days=1), time.min, timezone.utc)})
    if amount_field:
        for parameter, comparison in [("min_amount", "gte"), ("max_amount", "lte")]:
            if parameter in criteria:
                records = records.filter(**{f"{amount_field}__{comparison}": criteria[parameter]})
    return records


def record_page(records: QuerySet[Record], params: Mapping[str, str]) -> tuple[int, QuerySet[Record]]:
    query = ListingQuerySerializer(data=params)
    query.is_valid(raise_exception=True)
    offset = query.validated_data["offset"]
    limit = query.validated_data["limit"]
    return records.count(), records[offset:offset + limit]
