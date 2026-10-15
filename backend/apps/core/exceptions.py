"""Every API error uses the contract's `Error` shape: {"code": str, "message": str, "fields"?: {...}}.

DRF's default error bodies vary by exception ({"detail": ...}, {"field": [...]}, simplejwt's
{"detail", "code", "messages"}). The PWA should only have to handle one shape, so this handler
(REST_FRAMEWORK.EXCEPTION_HANDLER) rewrites them all. Status codes and headers such as Retry-After are
left as DRF set them.
"""

from rest_framework import exceptions, status
from rest_framework.views import exception_handler as drf_exception_handler


class ServiceUnavailable(exceptions.APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The service is temporarily unavailable. Please try again shortly."
    default_code = "service_unavailable"


def _flatten(detail):
    """Turn DRF's nested ErrorDetail lists/dicts into plain lists of strings, per field."""
    if isinstance(detail, dict):
        return {key: [str(m) for m in (v if isinstance(v, list) else [v])] for key, v in detail.items()}
    return {"non_field_errors": [str(m) for m in detail]}


def _first_code(detail):
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), [])
    if isinstance(detail, list):
        detail = detail[0] if detail else None
    return getattr(detail, "code", None)


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # unhandled: Django returns a 500 and Sentry records it

    if isinstance(exc, exceptions.ValidationError):
        fields = _flatten(exc.detail)
        code = _first_code(exc.detail) if len(fields) == 1 else None
        response.data = {
            "code": (
                code if code and code not in {"invalid", "required", "blank", "null"} else "validation_error"
            ),
            "message": "Some fields are invalid. See fields for details.",
            "fields": fields,
        }
        return response

    detail = exc.detail if isinstance(exc, exceptions.APIException) else None
    if isinstance(detail, dict) and "detail" in detail:  # simplejwt's InvalidToken and friends
        response.data = {"code": str(detail.get("code", exc.default_code)), "message": str(detail["detail"])}
    elif isinstance(exc, exceptions.Throttled):
        response.data = {"code": "rate_limited", "message": str(detail)}
    else:
        code = getattr(detail, "code", None) or getattr(exc, "default_code", "error")
        response.data = {"code": str(code), "message": str(detail)}
    return response
