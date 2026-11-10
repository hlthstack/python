"""Transport-independent pieces shared by the sync and async clients."""

import datetime as dt
import mimetypes
import os
import time
from collections.abc import Mapping, Sequence
from typing import IO, Any, Optional, Union
from urllib.parse import quote

import httpx

from ._exceptions import error_from_response
from ._version import __version__

ENVIRONMENTS = {
    "production": "https://api.hlthstack.io",
    "staging": "https://staging-api.hlthstack.io",
}
DEFAULT_TIMEOUT = 60.0
TOKEN_PATH = "/api/get-access-token"
# Tokens live 1 hour; refresh this many seconds before ``expires_at``.
TOKEN_REFRESH_MARGIN = 300.0
TOKEN_LIFETIME = 3600.0

FileContent = Union[bytes, IO[bytes]]
FileInput = Union[
    str,
    os.PathLike[str],
    bytes,
    IO[bytes],
    tuple[str, FileContent],
    tuple[str, FileContent, str],
]
"""A file to upload: a path, raw bytes, a binary file object, or a
``(filename, bytes_or_file)`` / ``(filename, bytes_or_file, content_type)`` tuple."""

Date = Union[str, dt.date]
DateTime = Union[str, dt.datetime]
PackageIds = Union[str, int, Sequence[Union[int, str]]]
Params = dict[str, Any]
Part = tuple[str, tuple[Optional[str], bytes, Optional[str]]]


class BaseClient:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        environment: str,
        base_url: Optional[str],
        entity_id: Optional[str],
        secret_key: Optional[str],
        timeout: Union[float, httpx.Timeout],
    ) -> None:
        if not username or not password:
            raise ValueError("username and password are required")
        if base_url is None:
            if environment not in ENVIRONMENTS:
                raise ValueError(
                    f"environment must be one of {sorted(ENVIRONMENTS)}, got {environment!r}"
                )
            base_url = ENVIRONMENTS[environment]
        if entity_id and not secret_key:
            raise ValueError("secret_key is required when entity_id is set")
        self.environment = environment
        self.base_url = base_url.rstrip("/")
        self.entity_id = entity_id
        self._auth = (username, password)
        self._secret_key = secret_key
        self._timeout = timeout
        self._token: Optional[str] = None
        self._token_refresh_at = 0.0

    def _http_options(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "timeout": self._timeout,
            "headers": {"User-Agent": f"hlthstack-python/{__version__}"},
        }

    # ------------------------------------------------------------------ auth

    def _cached_token(self, stale: Optional[str]) -> Optional[str]:
        """The cached token if it is fresh and is not the one that was just rejected."""
        if self._token and self._token != stale and time.time() < self._token_refresh_at:
            return self._token
        return None

    def _store_token(self, response: httpx.Response) -> Any:
        data = parse_response(response, binary=False)
        now = time.time()
        expires_at = now + TOKEN_LIFETIME
        try:
            parsed = dt.datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            expires_at = min(expires_at, parsed.timestamp())
        except (KeyError, ValueError):
            pass
        self._token = str(data["access_token"])
        self._token_refresh_at = expires_at - TOKEN_REFRESH_MARGIN
        return data

    def _headers(
        self,
        token: str,
        entity_id: Optional[str],
        secret_key: Optional[str],
        extra: Optional[Mapping[str, str]],
    ) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {token}"}
        entity_id = entity_id or self.entity_id
        if entity_id:
            secret_key = secret_key or self._secret_key
            if not secret_key:
                raise ValueError("secret_key is required when entity_id is set")
            headers["API-ENTITY-ID"] = entity_id
            headers["API-SECRET-KEY"] = secret_key
        if extra:
            headers.update(extra)
        return headers


def parse_response(response: httpx.Response, *, binary: bool) -> Any:
    if not response.is_success:
        raise error_from_response(response)
    if binary:
        return response.content
    if not response.content:
        return {}
    return response.json()


# ---------------------------------------------------------------------- request helpers


def path(template: str, *args: Union[str, int]) -> str:
    return template.format(*(quote(str(a), safe="") for a in args))


def compact(values: Mapping[str, Any]) -> dict[str, Any]:
    """Drop ``None`` values (omitted optional arguments)."""
    return {k: v for k, v in values.items() if v is not None}


def query(values: Mapping[str, Any]) -> Params:
    out = compact(values)
    for key, value in out.items():
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        elif isinstance(value, dt.date):
            out[key] = value.isoformat()
    return out


def join_ids(value: PackageIds) -> str:
    """Package ids are sent comma-separated."""
    if isinstance(value, (str, int)):
        return str(value)
    return ",".join(str(v) for v in value)


def coordinate(value: Optional[float]) -> Optional[str]:
    """Latitude/longitude must include a decimal point."""
    return None if value is None else repr(float(value))


def datetime_utc(value: Optional[DateTime]) -> Optional[str]:
    """ISO 8601 in UTC. Strings pass through; datetimes must be timezone-aware."""
    if value is None or isinstance(value, str):
        return value
    if value.tzinfo is None:
        raise ValueError("datetime values must be timezone-aware (for example UTC)")
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def text_part(name: str, value: str) -> Part:
    return (name, (None, value.encode(), None))


def file_part(name: str, value: FileInput) -> Part:
    """Read a file input fully so the request can be re-sent after a token refresh."""
    content_type: Optional[str] = None
    if isinstance(value, tuple):
        filename, content = value[0], value[1]
        if len(value) == 3:
            content_type = value[2]
        data = content if isinstance(content, bytes) else content.read()
    elif isinstance(value, bytes):
        filename, data = "file", value
    elif isinstance(value, (str, os.PathLike)):
        filename = os.path.basename(os.fspath(value))
        with open(value, "rb") as f:
            data = f.read()
    else:
        filename = os.path.basename(str(getattr(value, "name", "file")))
        data = value.read()
    if not isinstance(data, bytes):
        raise TypeError("file content must be bytes; open files in binary mode ('rb')")
    if content_type is None:
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return (name, (filename, data, content_type))


def file_parts(name: str, values: Sequence[FileInput]) -> list[Part]:
    if isinstance(values, (str, bytes, os.PathLike)):
        raise TypeError(f"{name}: pass a list of files, not a single file")
    return [file_part(name, v) for v in values]
