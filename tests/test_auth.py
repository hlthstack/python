import base64
import threading
import time

import httpx
import pytest
import respx

from hlthstack import AuthenticationError, Hlthstack
from hlthstack._base_client import TOKEN_REFRESH_MARGIN

from .conftest import PASSWORD, USERNAME, token_response

BOOKING = {"booking_id": "EKI0000000001700000000", "appointments": []}


def test_environment_base_urls() -> None:
    assert Hlthstack(username="u", password="p").base_url == "https://api.hlthstack.io"
    assert (
        Hlthstack(username="u", password="p", environment="staging").base_url
        == "https://staging-api.hlthstack.io"
    )
    custom = Hlthstack(username="u", password="p", base_url="http://localhost:3000/")
    assert custom.base_url == "http://localhost:3000"
    with pytest.raises(ValueError):
        Hlthstack(username="u", password="p", environment="sandbox")
    with pytest.raises(ValueError):
        Hlthstack(username="u", password="p", entity_id="1002")


def test_token_fetched_lazily_with_basic_auth_and_cached(
    router: respx.MockRouter, client: Hlthstack
) -> None:
    route = router.get("/api/appointments").respond(json=BOOKING)
    assert router["token"].call_count == 0

    client.appointments.get("EKI0000000001700000000")
    client.appointments.get("EKI0000000001700000000")

    assert router["token"].call_count == 1
    token_request = router["token"].calls[0].request
    expected = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    assert token_request.headers["Authorization"] == f"Basic {expected}"
    assert "API-ENTITY-ID" not in token_request.headers
    for call in route.calls:
        assert call.request.headers["Authorization"] == "Bearer token-1"


def test_token_refreshed_shortly_before_expiry(
    router: respx.MockRouter, client: Hlthstack, monkeypatch: pytest.MonkeyPatch
) -> None:
    route = router.get("/api/appointments").respond(json=BOOKING)
    client.appointments.get("EKI0000000001700000000")

    real_time = time.time
    # Still more than the margin left: cached.
    monkeypatch.setattr(time, "time", lambda: real_time() + 3600 - TOKEN_REFRESH_MARGIN - 60)
    client.appointments.get("EKI0000000001700000000")
    assert router["token"].call_count == 1
    # Inside the margin: refreshed.
    monkeypatch.setattr(time, "time", lambda: real_time() + 3600 - TOKEN_REFRESH_MARGIN + 1)
    client.appointments.get("EKI0000000001700000000")
    assert router["token"].call_count == 2
    assert route.calls.last.request.headers["Authorization"] == "Bearer token-2"


def test_401_refreshes_token_and_retries_once(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/appointments").mock(
        side_effect=[
            httpx.Response(401, text="HTTP Token: Access denied."),
            httpx.Response(200, json=BOOKING),
        ]
    )
    assert client.appointments.get("EKI0000000001700000000") == BOOKING
    assert router["token"].call_count == 2
    assert [c.request.headers["Authorization"] for c in route.calls] == [
        "Bearer token-1",
        "Bearer token-2",
    ]


def test_persistent_401_raises_after_one_retry(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/appointments").respond(401, text="HTTP Token: Access denied.")
    with pytest.raises(AuthenticationError) as info:
        client.appointments.get("EKI0000000001700000000")
    assert route.call_count == 2
    assert router["token"].call_count == 2
    assert info.value.status_code == 401
    assert info.value.body == "HTTP Token: Access denied."


def test_wrong_credentials() -> None:
    with respx.mock(base_url="https://api.hlthstack.io") as mock:
        mock.get("/api/get-access-token").respond(401, json={"message": "Wrong credentials"})
        client = Hlthstack(username="u", password="wrong")
        with pytest.raises(AuthenticationError) as info:
            client.wallet.list_customer_plans("example-co", api_customer_id="CUST1001")
        assert info.value.messages == ["Wrong credentials"]


def test_get_access_token_returns_and_caches(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/appointments").respond(json=BOOKING)
    token = client.get_access_token()
    assert token["access_token"] == "token-1"
    client.appointments.get("EKI0000000001700000000")
    assert router["token"].call_count == 1
    assert route.calls.last.request.headers["Authorization"] == "Bearer token-1"


def test_concurrent_threads_share_one_token_fetch(client: Hlthstack) -> None:
    with respx.mock(base_url=client.base_url) as mock:

        def slow_token(request: httpx.Request) -> httpx.Response:
            time.sleep(0.05)
            return token_response("token-shared")

        token_route = mock.get("/api/get-access-token").mock(side_effect=slow_token)
        mock.get("/api/appointments").respond(json=BOOKING)
        threads = [
            threading.Thread(target=client.appointments.get, args=("EKI0000000001700000000",))
            for _ in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert token_route.call_count == 1


def test_entity_headers_default_and_per_call_override(router: respx.MockRouter) -> None:
    route = router.get("/api/appointments").respond(json=BOOKING)
    with Hlthstack(
        username=USERNAME,
        password=PASSWORD,
        environment="staging",
        entity_id="1001",
        secret_key="test-secret-key",
    ) as client:
        client.appointments.get("EKI0000000001700000000")
        client.appointments.get("EKI0000000001700000000", entity_id="1002")

    first, second = (c.request.headers for c in route.calls)
    assert first["API-ENTITY-ID"] == "1001"
    assert first["API-SECRET-KEY"] == "test-secret-key"
    assert second["API-ENTITY-ID"] == "1002"
    assert second["API-SECRET-KEY"] == "test-secret-key"
    assert "API-ENTITY-ID" not in router["token"].calls[0].request.headers


def test_no_entity_headers_by_default(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/appointments").respond(json=BOOKING)
    client.appointments.get("EKI0000000001700000000")
    assert "API-ENTITY-ID" not in route.calls.last.request.headers
    assert "API-SECRET-KEY" not in route.calls.last.request.headers


def test_per_call_entity_requires_secret_key(router: respx.MockRouter, client: Hlthstack) -> None:
    router.get("/api/appointments").respond(json=BOOKING)
    with pytest.raises(ValueError):
        client.appointments.get("EKI0000000001700000000", entity_id="1002")
    client.appointments.get("EKI0000000001700000000", entity_id="1002", secret_key="test-key")
