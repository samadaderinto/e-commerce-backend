from __future__ import annotations

import logging
from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger("codematics.api")


def _stringify_details(detail: Any) -> Any:
    if isinstance(detail, ErrorDetail):
        return str(detail)
    if isinstance(detail, list):
        return [_stringify_details(item) for item in detail]
    if isinstance(detail, dict):
        return {key: _stringify_details(value) for key, value in detail.items()}
    return detail


def _default_message(details: Any) -> str:
    if isinstance(details, dict):
        detail = details.get("detail")
        if detail:
            return str(detail)
        return "Request validation failed."
    if isinstance(details, list):
        return "Request validation failed."
    return str(details)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:

    response = exception_handler(exc, context)
    request = context.get("request")
    view = context.get("view")
    view_name = view.__class__.__name__ if view else None

    if response is None:
        logger.error(
            "Unhandled API exception",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={
                "path": getattr(request, "path", None),
                "method": getattr(request, "method", None),
                "view": view_name,
                "user_id": getattr(getattr(request, "user", None), "pk", None),
            },
        )
        return Response(
            {
                "error": {
                    "code": "server_error",
                    "message": "An unexpected error occurred.",
                    "details": None,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    details = _stringify_details(response.data)
    code = "not_found" if isinstance(exc, Http404) else "api_error"
    if isinstance(exc, APIException):
        code = exc.default_code

    if response.status_code >= 500:
        logger.error(
            "API server error",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={
                "path": getattr(request, "path", None),
                "method": getattr(request, "method", None),
                "view": view_name,
                "user_id": getattr(getattr(request, "user", None), "pk", None),
            },
        )
    elif response.status_code >= 400:
        logger.warning(
            "API client error",
            extra={
                "path": getattr(request, "path", None),
                "method": getattr(request, "method", None),
                "view": view_name,
                "status_code": response.status_code,
                "user_id": getattr(getattr(request, "user", None), "pk", None),
            },
        )

    response.data = {
        "error": {
            "code": str(code),
            "message": _default_message(details),
            "details": details,
        }
    }
    return response
