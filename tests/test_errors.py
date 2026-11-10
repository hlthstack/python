from typing import Any

import httpx
import pytest
import respx

from hlthstack import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    Hlthstack,
    HlthstackError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
    UnprocessableEntityError,
)


@pytest.mark.parametrize(
    ("status", "body", "error", "messages"),
    [
        (
            400,
            {"errors": {"package_ids": ["should be an integer array"]}},
            BadRequestError,
            ["package_ids: should be an integer array"],
        ),
        (
            400,
            {"errors": {"messages": ["This booking cannot be rescheduled"]}},
            BadRequestError,
            ["This booking cannot be rescheduled"],
        ),
        (400, {"message": "Required details are missing"}, BadRequestError, None),
        (400, {"msg": "Booking failed", "recall": False}, BadRequestError, ["Booking failed"]),
        (
            403,
            {"error": "Invalid company slug for authenticated partner."},
            PermissionDeniedError,
            None,
        ),
        (404, {"success": False, "message": "Order not found"}, NotFoundError, ["Order not found"]),
        (
            409,
            {"success": False, "status": "transaction_locked", "errors": {"base": "locked"}},
            ConflictError,
            ["locked"],
        ),
        (422, {"errors": ["Invalid status"]}, UnprocessableEntityError, ["Invalid status"]),
        (
            422,
            {"success": False, "errors": {"msg": "Out of stock", "recall": True}},
            UnprocessableEntityError,
            ["Out of stock"],
        ),
        (500, {"errors": {"messages": ["boom"]}}, ServerError, ["boom"]),
        (503, "Service Unavailable", ServerError, ["Service Unavailable"]),
        (418, {}, HlthstackError, []),
    ],
)
def test_error_mapping(
    router: respx.MockRouter,
    client: Hlthstack,
    status: int,
    body: Any,
    error: type[HlthstackError],
    messages: Any,
) -> None:
    response = (
        httpx.Response(status, text=body)
        if isinstance(body, str)
        else httpx.Response(status, json=body, headers={"X-Request-Id": "req-1"})
    )
    router.get("/api/epharmacy/orders/EPO000000000001").mock(return_value=response)
    with pytest.raises(error) as info:
        client.pharmacy.get_order("EPO000000000001", api_customer_id="CUST1001")
    exc = info.value
    assert type(exc) is error
    assert exc.status_code == status
    assert exc.body == body
    assert exc.headers is not None
    if not isinstance(body, str):
        assert exc.headers["X-Request-Id"] == "req-1"
    expected = messages if messages is not None else [next(iter(body.values()))]
    assert exc.messages == expected
    assert str(status) in str(exc)


def test_unauthorised_lab_results_is_authentication_error(
    router: respx.MockRouter, client: Hlthstack
) -> None:
    router.get("/api/appointments/APT1A2B3C4D5/lab_results").respond(
        401, json={"errors": {"messages": ["Unauthorised"]}}
    )
    with pytest.raises(AuthenticationError) as info:
        client.appointments.get_lab_results("APT1A2B3C4D5")
    assert info.value.messages == ["Unauthorised"]


def test_network_error(router: respx.MockRouter, client: Hlthstack) -> None:
    router.get("/api/epharmacy/medicines/search").mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(APIConnectionError) as info:
        client.pharmacy.search_medicines(name="paracetamol")
    assert info.value.status_code is None
    assert isinstance(info.value.__cause__, httpx.ConnectTimeout)
