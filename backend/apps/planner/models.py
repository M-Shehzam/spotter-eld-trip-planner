"""Persistence for planned trips.

A plan is a pure function of its inputs, so the computed result is stored as
one JSON document rather than shredded across tables. That keeps a trip
retrievable by id, which is what makes a plan shareable by URL.
"""

from __future__ import annotations

import uuid

from django.db import models


class Trip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    current_location = models.CharField(max_length=200)
    pickup_location = models.CharField(max_length=200)
    dropoff_location = models.CharField(max_length=200)
    current_cycle_used_hours = models.FloatField()

    start_datetime = models.DateTimeField()
    driver_name = models.CharField(max_length=120, blank=True)
    carrier_name = models.CharField(max_length=120, blank=True)
    truck_number = models.CharField(max_length=60, blank=True)

    plan = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.pickup_location} to {self.dropoff_location} ({self.id})"
