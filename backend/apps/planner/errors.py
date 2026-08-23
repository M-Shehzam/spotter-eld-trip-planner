"""A single error shape for every failure the API can return.

The frontend renders whatever ``message`` it is given, so the wording here is
what a driver or dispatcher actually sees. ``code`` is what the frontend
branches on.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class PlannerError(Exception):
    """A failure that carries a message meant for the person using the app."""

    code = "planner_error"
    http_status = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


def error_payload(code: str, message: str, detail: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail or {}}}


def exception_handler(exc, context):
    if isinstance(exc, PlannerError):
        logger.info("%s: %s", exc.code, exc.message)
        return Response(
            error_payload(exc.code, exc.message, exc.detail), status=exc.http_status
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled error in %s", context.get("view"))
        return Response(
            error_payload(
                "internal_error",
                "Something went wrong while planning the trip. Please try again.",
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(response.data, dict) and "error" not in response.data:
        response.data = error_payload(
            "invalid_request",
            "Some of the trip details need fixing.",
            response.data,
        )
    return response
