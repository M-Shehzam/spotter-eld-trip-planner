"""Request validation.

The four fields the brief names are required. The rest exist because a log
sheet has boxes for them and an empty box looks unfinished, so they are
optional and default to nothing.

Error messages here are read by a driver, not a developer, so they say what
to do rather than which constraint failed.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework import serializers


class TripRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(
        max_length=200,
        trim_whitespace=True,
        error_messages={
            "blank": "Enter where the driver is now.",
            "required": "Enter where the driver is now.",
        },
    )
    pickup_location = serializers.CharField(
        max_length=200,
        trim_whitespace=True,
        error_messages={
            "blank": "Enter the pickup location.",
            "required": "Enter the pickup location.",
        },
    )
    dropoff_location = serializers.CharField(
        max_length=200,
        trim_whitespace=True,
        error_messages={
            "blank": "Enter the dropoff location.",
            "required": "Enter the dropoff location.",
        },
    )
    current_cycle_used_hours = serializers.FloatField(
        min_value=0.0,
        error_messages={
            "required": "Enter the hours already used in the current cycle.",
            "invalid": "Cycle hours must be a number.",
            "min_value": "Cycle hours cannot be negative.",
        },
    )

    start_datetime = serializers.DateTimeField(required=False, allow_null=True)
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=64)
    driver_name = serializers.CharField(
        required=False, allow_blank=True, max_length=120
    )
    carrier_name = serializers.CharField(
        required=False, allow_blank=True, max_length=120
    )
    truck_number = serializers.CharField(required=False, allow_blank=True, max_length=60)

    def validate_current_cycle_used_hours(self, value: float) -> float:
        limit = settings.HOS_CYCLE_LIMIT_HOURS
        if value > limit:
            raise serializers.ValidationError(
                f"A driver cannot have used more than {limit:g} hours of a "
                f"{limit:g}-hour cycle. Enter {limit:g} if the cycle is already spent."
            )
        return value
