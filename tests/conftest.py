import datetime as dt
import itertools
from collections.abc import Iterator

import httpx
import pytest
import respx

from hlthstack import AsyncHlthstack, Hlthstack

BASE_URL = "https://staging-api.hlthstack.io"
USERNAME = "test-user"
PASSWORD = "test-password"


def token_response(token: str, lifetime: float = 3600) -> httpx.Response:
    expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=lifetime)
    return httpx.Response(
        200, json={"access_token": token, "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ")}
    )


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        counter = itertools.count(1)
        mock.get("/api/get-access-token", name="token").mock(
            side_effect=lambda request: token_response(f"token-{next(counter)}")
        )
        pre_registration_counter = itertools.count(1)
        mock.get("/api/pre_registration/access-token", name="pre_registration_token").mock(
            side_effect=lambda request: token_response(
                f"prereg-token-{next(pre_registration_counter)}"
            )
        )
        yield mock


@pytest.fixture
def client() -> Iterator[Hlthstack]:
    with Hlthstack(username=USERNAME, password=PASSWORD, environment="staging") as c:
        yield c


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def async_client() -> AsyncHlthstack:
    return AsyncHlthstack(username=USERNAME, password=PASSWORD, environment="staging")
