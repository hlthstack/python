"""Plain-HTTP helpers for the hlthstack API, using requests (no SDK).

Configuration comes from environment variables:

    HLTHSTACK_BASE_URL         default https://staging-api.hlthstack.io
    HLTHSTACK_USERNAME         API username
    HLTHSTACK_PASSWORD         API password
    HLTHSTACK_ENTITY_ID        optional, multi-entity partners: entity to act for
    HLTHSTACK_SECRET_KEY       required with HLTHSTACK_ENTITY_ID
    HLTHSTACK_PREREG_USERNAME  pre-registration account email
    HLTHSTACK_PREREG_PASSWORD  pre-registration password

See docs/api-integration.md.
"""

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import requests

BASE_URL = os.environ.get("HLTHSTACK_BASE_URL", "https://staging-api.hlthstack.io")
TIMEOUT = 60  # seconds; create, reschedule and cancel calls can take a few seconds
REFRESH_MARGIN = 300  # request a new token 5 minutes before the current one expires

session = requests.Session()


class APIError(Exception):
    """A non-2xx response. ``body`` is the parsed JSON, or the text."""

    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        self.messages = error_messages(body)
        super().__init__(f"HTTP {status_code}: {'; '.join(self.messages) or body!r}")


def error_messages(body: Any) -> list[str]:
    """Pull the human-readable messages out of any of the API's error shapes."""
    if isinstance(body, str):
        return [body] if body.strip() else []
    if not isinstance(body, dict):
        return []
    messages: list[str] = []
    errors = body.get("errors")
    if isinstance(errors, list):  # {"errors": ["..."]}
        messages += [str(error) for error in errors]
    elif isinstance(errors, dict):  # {"errors": {"messages": [...]}} / {"errors": {"field": [...]}}
        for field, value in errors.items():
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, bool):  # {"errors": {"msg": "...", "recall": false}}
                    continue
                generic = field in ("messages", "base", "msg")
                messages.append(str(item) if generic else f"{field}: {item}")
    for key in ("message", "msg", "error"):  # {"message": ...}, {"msg": ...}, {"error": ...}
        if isinstance(body.get(key), str):
            messages.append(body[key])
    return messages


def _parse_body(response: requests.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def _parse_expires_at(value: str) -> float:
    if value.endswith(" UTC"):  # pre-registration: "2026-01-15 07:16:21 UTC"
        expires = datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC")
    else:  # ISO 8601: "2026-01-15T07:16:21Z"
        expires = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires.timestamp()


class AccessToken:
    """Fetches a token with HTTP Basic auth and caches it until shortly before it expires."""

    def __init__(self, path: str, username: str, password: str) -> None:
        self.path = path
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get(self, force_refresh: bool = False) -> str:
        with self._lock:  # one refresh at a time, shared by all threads
            if force_refresh or self._token is None or time.time() >= self._expires_at:
                response = session.get(
                    BASE_URL + self.path, auth=(self.username, self.password), timeout=TIMEOUT
                )
                if not response.ok:
                    raise APIError(response.status_code, _parse_body(response))
                data = response.json()
                self._token = str(data["access_token"])
                self._expires_at = _parse_expires_at(data["expires_at"]) - REFRESH_MARGIN
            return self._token


token = AccessToken(
    "/api/get-access-token",
    os.environ.get("HLTHSTACK_USERNAME", ""),
    os.environ.get("HLTHSTACK_PASSWORD", ""),
)


def _entity_headers() -> dict[str, str]:
    entity_id = os.environ.get("HLTHSTACK_ENTITY_ID")
    if not entity_id:
        return {}  # act for the entity tied to the credentials
    return {"API-ENTITY-ID": entity_id, "API-SECRET-KEY": os.environ["HLTHSTACK_SECRET_KEY"]}


def _send(
    auth_headers: Callable[[str], dict[str, str]],
    access_token: AccessToken,
    method: str,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    json: Any = None,
    data: Optional[dict[str, Any]] = None,
    files: Any = None,
    headers: Optional[dict[str, str]] = None,
) -> Any:
    for attempt in (1, 2):
        response = session.request(
            method,
            BASE_URL + path,
            params=params,
            json=json,
            data=data,
            files=files,
            headers={
                **auth_headers(access_token.get(force_refresh=attempt == 2)),
                **(headers or {}),
            },
            timeout=TIMEOUT,
        )
        if response.status_code == 401 and attempt == 1:
            continue  # token expired or revoked: get a new one and retry once
        if not response.ok:
            raise APIError(response.status_code, _parse_body(response))
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return response.json()
        return response.content  # vouchers are PDF bytes
    raise AssertionError("unreachable")


def api(method: str, path: str, **kwargs: Any) -> Any:
    """Call the booking API with ``Authorization: Bearer``.

    Keyword arguments: ``params`` (query), ``json`` (JSON body), ``data`` + ``files``
    (multipart) and ``headers`` (extra headers, for example per-call entity headers).
    Returns the parsed JSON, or the raw bytes for non-JSON responses. Raises ``APIError``.
    Pass upload contents as bytes, not open files, so the retry after a 401 can resend them.
    """
    return _send(
        lambda value: {"Authorization": f"Bearer {value}", **_entity_headers()},
        token,
        method,
        path,
        **kwargs,
    )


pre_registration_token = AccessToken(
    "/api/pre_registration/access-token",
    os.environ.get("HLTHSTACK_PREREG_USERNAME", ""),
    os.environ.get("HLTHSTACK_PREREG_PASSWORD", ""),
)


def pre_registration_api(method: str, path: str, **kwargs: Any) -> Any:
    """Call a pre-registration endpoint: the raw token in ``X-EKINCARE-KEY``, no Bearer."""
    return _send(
        lambda value: {"X-EKINCARE-KEY": value},
        pre_registration_token,
        method,
        path,
        **kwargs,
    )
