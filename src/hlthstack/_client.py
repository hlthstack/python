import threading
from collections.abc import Mapping
from types import TracebackType
from typing import Any, Optional, Union, cast

import httpx

from ._base_client import (
    DEFAULT_TIMEOUT,
    TOKEN_PATH,
    BaseClient,
    Params,
    Part,
    parse_response,
)
from ._exceptions import APIConnectionError
from ._sync_resources import Appointments, Consultations, Pharmacy, Testing, Wallet
from .types import AccessToken


class Hlthstack(BaseClient):
    """Synchronous client for the hlthstack partner API.

    Access tokens are fetched lazily, cached until shortly before they expire and refreshed
    once if a call returns 401. The client is thread-safe; reuse one instance and close it
    when done (or use it as a context manager).

    Args:
        username: API username issued by hlthstack.
        password: API password issued by hlthstack.
        environment: ``"production"`` (default) or ``"staging"``.
        base_url: Override the environment's base URL.
        entity_id: Multi-entity partners: act for this entity by default
            (sent as ``API-ENTITY-ID``). Every method also accepts ``entity_id=``.
        secret_key: API secret key, required with ``entity_id`` (sent as ``API-SECRET-KEY``).
        timeout: Request timeout in seconds, or an ``httpx.Timeout``.
    """

    def __init__(
        self,
        *,
        username: str,
        password: str,
        environment: str = "production",
        base_url: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        timeout: Union[float, httpx.Timeout] = DEFAULT_TIMEOUT,
    ) -> None:
        super().__init__(
            username=username,
            password=password,
            environment=environment,
            base_url=base_url,
            entity_id=entity_id,
            secret_key=secret_key,
            timeout=timeout,
        )
        self._http = httpx.Client(**self._http_options())
        self._lock = threading.Lock()
        self.appointments = Appointments(self)
        """Health checkups, lab tests, dental, vision and vaccinations."""
        self.consultations = Consultations(self)
        """In-clinic and online specialist consultations."""
        self.pharmacy = Pharmacy(self)
        """ePharmacy: medicines, prescription digitization, cart and orders."""
        self.wallet = Wallet(self)
        """Member benefit wallets and plan subscriptions."""
        self.testing = Testing(self)
        """Staging-only lifecycle simulators. Not available in production."""

    def get_access_token(self) -> AccessToken:
        """Fetch a new access token (``getAccessToken``) and cache it for later calls.

        You don't need to call this: the client fetches and refreshes tokens on its own.
        """
        with self._lock:
            return cast(AccessToken, self._fetch_token())

    def _fetch_token(self) -> Any:
        try:
            response = self._http.get(TOKEN_PATH, auth=self._auth)
        except httpx.HTTPError as exc:
            raise APIConnectionError(f"Request failed: {exc}") from exc
        return self._store_token(response)

    def _access_token(self, stale: Optional[str] = None) -> str:
        token = self._cached_token(stale)
        if token:
            return token
        with self._lock:
            token = self._cached_token(stale)
            if token:
                return token
            return str(self._fetch_token()["access_token"])

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Params] = None,
        json: Optional[Any] = None,
        files: Optional[list[Part]] = None,
        headers: Optional[Mapping[str, str]] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        binary: bool = False,
    ) -> Any:
        token = self._access_token()
        for attempt in range(2):
            try:
                response = self._http.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    files=files,
                    headers=self._headers(token, entity_id, secret_key, headers),
                )
            except httpx.HTTPError as exc:
                raise APIConnectionError(f"Request failed: {exc}") from exc
            if response.status_code != 401 or attempt == 1:
                break
            token = self._access_token(stale=token)
        return parse_response(response, binary=binary)

    def close(self) -> None:
        """Close the underlying HTTP connections."""
        self._http.close()

    def __enter__(self) -> "Hlthstack":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()
