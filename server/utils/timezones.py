"""Validated display timezones; persisted instants always remain UTC."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from rest_framework import serializers


class TimeZoneField(serializers.CharField):
    def to_internal_value(self, data: object) -> str:
        value = super().to_internal_value(data)
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError('Choose a valid IANA timezone, such as America/Los_Angeles.')
        return value
