import asyncio
import io
import json

import httpx
import pytest
import respx

from hlthstack import AsyncHlthstack, AuthenticationError, NotFoundError
from hlthstack.types import BookingCustomer

from .conftest import token_response
from .test_multipart import parse_multipart

pytestmark = pytest.mark.anyio

CUSTOMER: BookingCustomer = {
    "name": "Jane Doe",
    "dob": "1990-08-24",
    "gender": "female",
    "mobile_number": "9999999999",
    "api_customer_id": "CUST1001",
    "package_ids": [1001],
}


async def test_quickstart_flow(router: respx.MockRouter, async_client: AsyncHlthstack) -> None:
    providers = router.get("/api/providers").respond(json={"providers": [{"provider_id": 1001}]})
    create = router.post("/api/appointments").respond(
        json={"booking_id": "EKI0000000001700000000", "provider_id": 1001, "customers": []}
    )
    get = router.get("/api/appointments").respond(
        json={"booking_id": "EKI0000000001700000000", "appointments": [{"status": "confirmed"}]}
    )
    async with async_client as client:
        result = await client.appointments.list_providers(
            service_name="ahc", package_ids=[1001], pincode="500081"
        )
        booking = await client.appointments.create(
            service_name="ahc",
            appointment_type="inclinic",
            provider_id=result["providers"][0]["provider_id"],
            appointment_date_time="2026-01-15T02:30:00Z",
            customers=[CUSTOMER],
        )
        details = await client.appointments.get(booking["booking_id"])

    assert details["appointments"][0]["status"] == "confirmed"
    assert dict(providers.calls.last.request.url.params)["package_ids"] == "1001"
    assert json.loads(create.calls.last.request.content)["customers"] == [CUSTOMER]
    assert dict(get.calls.last.request.url.params) == {"booking_id": "EKI0000000001700000000"}
    assert router["token"].call_count == 1


async def test_concurrent_calls_share_one_token_fetch(async_client: AsyncHlthstack) -> None:
    async def slow_token(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return token_response("token-shared")

    with respx.mock(base_url=async_client.base_url) as mock:
        token = mock.get("/api/get-access-token").mock(side_effect=slow_token)
        route = mock.get("/api/epharmacy/medicines/search").respond(json={"medicines": []})
        async with async_client as client:
            await asyncio.gather(
                *(client.pharmacy.search_medicines(name="paracetamol") for _ in range(8))
            )
    assert token.call_count == 1
    assert route.call_count == 8
    assert all(c.request.headers["Authorization"] == "Bearer token-shared" for c in route.calls)


async def test_401_retry_and_entity_headers(router: respx.MockRouter) -> None:
    route = router.get("/api/example-co/customers/plans").mock(
        side_effect=[
            httpx.Response(401, text="HTTP Token: Access denied."),
            httpx.Response(200, json={"status": "success", "data": {"customer_plans": []}}),
        ]
    )
    async with AsyncHlthstack(
        username="test-user",
        password="test-password",
        environment="staging",
        entity_id="1001",
        secret_key="test-secret-key",
    ) as client:
        await client.wallet.list_customer_plans("example-co", api_customer_id="CUST1001")
    assert route.call_count == 2
    assert router["token"].call_count == 2
    second = route.calls.last.request.headers
    assert second["Authorization"] == "Bearer token-2"
    assert second["API-ENTITY-ID"] == "1001"
    assert second["API-SECRET-KEY"] == "test-secret-key"


async def test_errors_and_binary(router: respx.MockRouter, async_client: AsyncHlthstack) -> None:
    router.get("/api/epharmacy/orders/EPO0").respond(
        404, json={"success": False, "message": "Order not found"}
    )
    router.get("/api/consultations/APT1A2B3C4D5/voucher").respond(content=b"%PDF")
    router.get("/api/appointments/APT1A2B3C4D5/lab_results").respond(
        401, json={"errors": {"messages": ["Unauthorised"]}}
    )
    async with async_client as client:
        with pytest.raises(NotFoundError):
            await client.pharmacy.get_order("EPO0", api_customer_id="CUST1001")
        assert await client.consultations.get_voucher("APT1A2B3C4D5") == b"%PDF"
        with pytest.raises(AuthenticationError):
            await client.appointments.get_lab_results("APT1A2B3C4D5")


async def test_async_multipart(router: respx.MockRouter, async_client: AsyncHlthstack) -> None:
    route = router.post("/api/consultations/APT1A2B3C4D5/upload_documents").respond(
        json={"message": "Document uploaded successfully"}
    )
    async with async_client as client:
        await client.consultations.upload_documents(
            "APT1A2B3C4D5", [("Report", ("report.pdf", io.BytesIO(b"%PDF")))]
        )
    parts = parse_multipart(route.calls.last.request)
    assert [(p.name, p.data) for p in parts] == [
        ("files[][name]", b"Report"),
        ("files[][value]", b"%PDF"),
    ]


async def test_get_access_token(router: respx.MockRouter, async_client: AsyncHlthstack) -> None:
    async with async_client as client:
        token = await client.get_access_token()
    assert token["access_token"] == "token-1"
