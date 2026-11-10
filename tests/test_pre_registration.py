import base64
import datetime as dt
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx

from hlthstack import AsyncHlthstack, AuthenticationError, BadRequestError, Hlthstack
from hlthstack.types import PreRegistrationDependant, PreRegistrationEmployee

from .conftest import PASSWORD, USERNAME

PREREG_USERNAME = "hr@example.com"
PREREG_PASSWORD = "test-prereg-password"
REQUEST_ID = "3f2b8c1e-0d4a-4c5e-9b7a-2e6f1d8c9a01"
ACCEPTED = {"message": "Request has been accepted", "request_id": REQUEST_ID}
EMPLOYEE: PreRegistrationEmployee = {
    "employee_code": "EMP1001",
    "company_id": "1001",
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane.doe@example.com",
    "date_of_birth": "24-08-1990",
    "gender": "Female",
    "mobile_number": "9999999999",
    "vip": "No",
    "entity_name": "",
    "employee_office_location": "Hyderabad",
    "department": "Engineering",
    "grade": "B",
    "date_of_joining": "01-01-2026",
    "voluntary_plan_ids": [
        "EXAMPLE_PLAN",
        {"plan_id": "EXAMPLE_TOPUP", "additional": True, "subscription_id": "ORD-0001"},
    ],
}
DEPENDANT: PreRegistrationDependant = {
    "guardian_email": "jane.doe@example.com",
    "dependent_code": "DEP-001",
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "10-02-1960",
    "gender": "Male",
    "mobile_number": "9999999998",
    "relation": "Father",
}


@pytest.fixture
def client() -> Iterator[Hlthstack]:
    with Hlthstack(
        username=USERNAME,
        password=PASSWORD,
        pre_registration_username=PREREG_USERNAME,
        pre_registration_password=PREREG_PASSWORD,
        environment="staging",
        entity_id="1001",
        secret_key="test-secret-key",
    ) as c:
        yield c


def body(route: respx.Route) -> Any:
    return json.loads(route.calls.last.request.content)


def test_create_sends_its_own_token_header(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.post("/v1/corporate/pre_registrations").respond(json=ACCEPTED)

    assert client.pre_registration.create(employees=[EMPLOYEE], dependants=[DEPENDANT]) == ACCEPTED

    assert router["token"].call_count == 0
    token_request = router["pre_registration_token"].calls[0].request
    expected = base64.b64encode(f"{PREREG_USERNAME}:{PREREG_PASSWORD}".encode()).decode()
    assert token_request.headers["Authorization"] == f"Basic {expected}"
    headers = route.calls.last.request.headers
    assert headers["X-EKINCARE-KEY"] == "prereg-token-1"
    assert "Authorization" not in headers
    assert "API-ENTITY-ID" not in headers
    assert "API-SECRET-KEY" not in headers
    assert body(route) == {"employees": [EMPLOYEE], "dependants": [DEPENDANT]}


def test_update_deactivate_and_status(router: respx.MockRouter, client: Hlthstack) -> None:
    update = router.post("/v1/corporate/pre_registrations/update").respond(json=ACCEPTED)
    deactivate = router.post("/v1/corporate/pre_registrations/deactivate").respond(json=ACCEPTED)
    status = {
        "request_id": REQUEST_ID,
        "status": "completed",
        "success_records": [],
        "failure_records": [{"errors": ["employee with email: a@example.com not found"]}],
        "created_at": "2026-01-15T06:16:21Z",
    }
    get = router.get(f"/v1/corporate/pre_registrations/{REQUEST_ID}/status").respond(json=status)

    client.pre_registration.update(
        employees=[{"email": "jane.doe@example.com", "department": "Finance"}]
    )
    assert body(update) == {
        "employees": [{"email": "jane.doe@example.com", "department": "Finance"}]
    }
    client.pre_registration.deactivate(
        employees=["jane.doe@example.com"], dependants=["9999999998"]
    )
    assert body(deactivate) == {
        "employees": ["jane.doe@example.com"],
        "dependants": ["9999999998"],
    }
    assert client.pre_registration.get_status(REQUEST_ID) == status
    assert get.calls.last.request.headers["X-EKINCARE-KEY"] == "prereg-token-1"
    assert router["pre_registration_token"].call_count == 1


def test_partner_and_pre_registration_tokens_are_separate(
    router: respx.MockRouter, client: Hlthstack
) -> None:
    plans = router.get("/api/example-co/customers/plans").respond(
        json={"status": "success", "data": {"customer_plans": []}}
    )
    router.post("/v1/corporate/pre_registrations/deactivate").respond(json=ACCEPTED)
    client.wallet.list_customer_plans("example-co", api_customer_id="CUST1001")
    client.pre_registration.deactivate(employees=["jane.doe@example.com"])
    assert plans.calls.last.request.headers["Authorization"] == "Bearer token-1"
    assert "X-EKINCARE-KEY" not in plans.calls.last.request.headers
    assert client.pre_registration.get_access_token()["access_token"] == "prereg-token-2"
    assert client.get_access_token()["access_token"] == "token-2"


def test_401_refreshes_pre_registration_token_once(
    router: respx.MockRouter, client: Hlthstack
) -> None:
    route = router.get(f"/v1/corporate/pre_registrations/{REQUEST_ID}/status").mock(
        side_effect=[httpx.Response(401), httpx.Response(401)]
    )
    with pytest.raises(AuthenticationError) as info:
        client.pre_registration.get_status(REQUEST_ID)
    assert info.value.status_code == 401
    assert [c.request.headers["X-EKINCARE-KEY"] for c in route.calls] == [
        "prereg-token-1",
        "prereg-token-2",
    ]
    assert router["token"].call_count == 0


def test_expires_at_in_pre_registration_format_is_parsed(client: Hlthstack) -> None:
    def expires_in(minutes: int) -> str:
        at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
        return at.strftime("%Y-%m-%d %H:%M:%S UTC")

    with respx.mock(base_url=client.base_url) as mock:
        token = mock.get("/api/pre_registration/access-token").mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "a", "expires_at": expires_in(4)}),
                httpx.Response(200, json={"access_token": "b", "expires_at": expires_in(60)}),
            ]
        )
        route = mock.post("/v1/corporate/pre_registrations/deactivate").respond(json=ACCEPTED)
        client.pre_registration.deactivate(employees=["jane.doe@example.com"])
        # "a" expires within the refresh margin, so the next call fetches "b".
        client.pre_registration.deactivate(employees=["jane.doe@example.com"])
        client.pre_registration.deactivate(employees=["jane.doe@example.com"])
    assert token.call_count == 2
    assert [c.request.headers["X-EKINCARE-KEY"] for c in route.calls] == ["a", "b", "b"]


def test_errors(router: respx.MockRouter, client: Hlthstack) -> None:
    router.post("/v1/corporate/pre_registrations").respond(
        400, json={"message": "Request is too large"}
    )
    with pytest.raises(BadRequestError) as info:
        client.pre_registration.create(employees=[EMPLOYEE])
    assert info.value.messages == ["Request is too large"]


def test_credentials() -> None:
    only_prereg = Hlthstack(
        pre_registration_username=PREREG_USERNAME, pre_registration_password=PREREG_PASSWORD
    )
    with pytest.raises(ValueError, match="username and password"):
        only_prereg.wallet.list_customer_plans("example-co", api_customer_id="CUST1001")
    only_prereg.close()
    only_partner = Hlthstack(username=USERNAME, password=PASSWORD)
    with pytest.raises(ValueError, match="pre_registration_username"):
        only_partner.pre_registration.get_status(REQUEST_ID)
    only_partner.close()
    with pytest.raises(ValueError):
        Hlthstack()


@pytest.mark.anyio
async def test_async_pre_registration(router: respx.MockRouter) -> None:
    route = router.post("/v1/corporate/pre_registrations").respond(json=ACCEPTED)
    async with AsyncHlthstack(
        pre_registration_username=PREREG_USERNAME,
        pre_registration_password=PREREG_PASSWORD,
        environment="staging",
    ) as client:
        assert await client.pre_registration.create(employees=[EMPLOYEE]) == ACCEPTED
        token = await client.pre_registration.get_access_token()
    assert token["access_token"] == "prereg-token-2"
    assert route.calls.last.request.headers["X-EKINCARE-KEY"] == "prereg-token-1"
    assert body(route) == {"employees": [EMPLOYEE]}
