import asyncio
from collections.abc import Mapping
from types import TracebackType
from typing import Any, Optional, Union, cast

import httpx

from ._async_resources import (
    AsyncAppointments,
    AsyncConsultations,
    AsyncPharmacy,
    AsyncPreRegistration,
    AsyncTesting,
    AsyncWallet,
)
from ._base_client import (
    DEFAULT_TIMEOUT,
    BaseClient,
    Params,
    Part,
    TokenSlot,
    parse_response,
)
from ._exceptions import APIConnectionError
from .types import AccessToken


class AsyncHlthstack(BaseClient):
    """Asynchronous client for the hlthstack partner API.

    Same surface as :class:`hlthstack.Hlthstack`, with ``async`` methods. Concurrent calls
    share one token refresh. Close it with ``await client.aclose()`` or use
    ``async with``.
    """

    def __init__(
        self,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        environment: str = "production",
        base_url: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        timeout: Union[float, httpx.Timeout] = DEFAULT_TIMEOUT,
        pre_registration_username: Optional[str] = None,
        pre_registration_password: Optional[str] = None,
    ) -> None:
        super().__init__(
            username=username,
            password=password,
            environment=environment,
            base_url=base_url,
            entity_id=entity_id,
            secret_key=secret_key,
            timeout=timeout,
            pre_registration_username=pre_registration_username,
            pre_registration_password=pre_registration_password,
        )
        self._http = httpx.AsyncClient(**self._http_options())
        # Created on first use, inside the running event loop (Python 3.9 binds locks to
        # the loop that is current when they are created).
        self._lock: Optional[asyncio.Lock] = None
        self.appointments = AsyncAppointments(self)
        """Health checkups, lab tests, dental, vision and vaccinations."""
        self.consultations = AsyncConsultations(self)
        """In-clinic and online specialist consultations."""
        self.pharmacy = AsyncPharmacy(self)
        """ePharmacy: medicines, prescription digitization, cart and orders."""
        self.wallet = AsyncWallet(self)
        """Member benefit wallets and plan subscriptions."""
        self.pre_registration = AsyncPreRegistration(self)
        """Bulk member and dependant registration (uses the pre-registration credentials)."""
        self.testing = AsyncTesting(self)
        """Staging-only lifecycle simulators. Not available in production."""

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get_access_token(self) -> AccessToken:
        """Fetch a new access token (``getAccessToken``) and cache it for later calls.

        You don't need to call this: the client fetches and refreshes tokens on its own.
        """
        return cast(AccessToken, await self._new_token(pre_registration=False))

    async def _new_token(self, *, pre_registration: bool) -> Any:
        async with self._get_lock():
            return await self._fetch_token(self._token_slot(pre_registration))

    async def _fetch_token(self, slot: TokenSlot) -> Any:
        credentials = slot.credentials()
        try:
            response = await self._http.get(slot.path, auth=credentials)
        except httpx.HTTPError as exc:
            raise APIConnectionError(f"Request failed: {exc}") from exc
        return self._store_token(slot, response)

    async def _access_token(self, slot: TokenSlot, stale: Optional[str] = None) -> str:
        token = self._cached_token(slot, stale)
        if token:
            return token
        async with self._get_lock():
            token = self._cached_token(slot, stale)
            if token:
                return token
            return str((await self._fetch_token(slot))["access_token"])

    async def _request(
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
        pre_registration: bool = False,
    ) -> Any:
        slot = self._token_slot(pre_registration)
        token = await self._access_token(slot)
        for attempt in range(2):
            try:
                response = await self._http.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    files=files,
                    headers=self._headers(token, entity_id, secret_key, headers, pre_registration),
                )
            except httpx.HTTPError as exc:
                raise APIConnectionError(f"Request failed: {exc}") from exc
            if response.status_code != 401 or attempt == 1:
                break
            token = await self._access_token(slot, stale=token)
        return parse_response(response, binary=binary)

    async def aclose(self) -> None:
        """Close the underlying HTTP connections."""
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncHlthstack":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.aclose()
