from typing import Any, Optional

import httpx

__all__ = [
    "APIConnectionError",
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "HlthstackError",
    "NotFoundError",
    "PermissionDeniedError",
    "ServerError",
    "UnprocessableEntityError",
    "WebhookVerificationError",
]


class HlthstackError(Exception):
    """Base class for every error raised by this library.

    For HTTP errors, ``status_code``, ``body`` (parsed JSON, or the raw text when the body
    is not JSON), ``headers`` and ``messages`` (human-readable messages pulled out of the
    body, whatever its shape) are set. They are ``None``/empty for other errors.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        body: Any = None,
        headers: Optional[httpx.Headers] = None,
        messages: Optional[list[str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.body = body
        self.headers = headers
        self.messages: list[str] = messages or []


class BadRequestError(HlthstackError):
    """400: invalid parameters, plan/subscription, entity headers, or action not allowed."""


class AuthenticationError(HlthstackError):
    """401: wrong credentials, or an access token that was still rejected after a refresh."""


class PermissionDeniedError(HlthstackError):
    """403: the booking isn't yours, the service isn't enabled, or the company slug differs."""


class NotFoundError(HlthstackError):
    """404: member, cart or order not found, or a staging-only route called in production."""


class ConflictError(HlthstackError):
    """409: concurrent partner-payment confirmation. Safe to retry."""


class UnprocessableEntityError(HlthstackError):
    """422: business-rule or processing failure, or an unexpected server-side error."""


class ServerError(HlthstackError):
    """5xx: server error, or a provider's system could not be reached."""


class APIConnectionError(HlthstackError):
    """The request did not get a response (network error or timeout)."""


class WebhookVerificationError(HlthstackError):
    """A webhook's ``Signature`` JWT, ids or timestamp did not verify."""


_STATUS_ERRORS = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: UnprocessableEntityError,
}


def _extract_messages(body: Any) -> list[str]:
    """Pull readable messages out of any of the API's error body shapes (see errors.md)."""
    if isinstance(body, str):
        return [body.strip()] if body.strip() else []
    if not isinstance(body, dict):
        return []
    messages: list[str] = []
    errors = body.get("errors")
    if isinstance(errors, list):  # {"errors": ["Invalid status"]}
        messages.extend(str(e) for e in errors)
    elif isinstance(errors, dict):
        # {"errors": {"messages": [...]}}, {"errors": {"field": [...]}},
        # {"errors": {"msg": "...", "recall": false}}, {"errors": {"base": "..."}}
        for key, value in errors.items():
            values = value if isinstance(value, list) else [value]
            for item in values:
                if not isinstance(item, str):
                    continue
                plain = key in ("messages", "base", "msg")
                messages.append(item if plain else f"{key}: {item}")
    for key in ("message", "msg", "error"):
        if isinstance(body.get(key), str):
            messages.append(body[key])
    return messages


def error_from_response(response: httpx.Response) -> HlthstackError:
    body: Any
    try:
        body = response.json()
    except ValueError:
        body = response.text
    messages = _extract_messages(body)
    status = response.status_code
    detail = "; ".join(messages) if messages else response.reason_phrase
    cls = _STATUS_ERRORS.get(status, ServerError if status >= 500 else HlthstackError)
    return cls(
        f"{status}: {detail}",
        status_code=status,
        body=body,
        headers=response.headers,
        messages=messages,
    )
