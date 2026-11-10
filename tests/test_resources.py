import datetime as dt
import json
from typing import Any

import httpx
import respx

from hlthstack import Hlthstack
from hlthstack.types import BookingAddress, BookingCustomer, ConsultationCustomer

CUSTOMER: BookingCustomer = {
    "name": "Jane Doe",
    "dob": "1990-08-24",
    "gender": "female",
    "mobile_number": "9999999999",
    "api_customer_id": "CUST1001",
    "package_ids": [1001],
}
CONSULT_CUSTOMER: ConsultationCustomer = {
    "name": "Jane Doe",
    "dob": "1990-08-24",
    "gender": "female",
    "mobile_number": "9999999999",
    "api_customer_id": "CUST1001",
    "package_ids": [2001],
}
ADDRESS: BookingAddress = {
    "address_line_one": "1 Example Road",
    "address_line_two": "Kondapur",
    "city": "Hyderabad",
    "state": "Telangana",
    "country": "India",
    "pincode": "500084",
    "latitude": 17.47,
    "longitude": 78.35,
}


def body(route: respx.Route) -> Any:
    return json.loads(route.calls.last.request.content)


def params(route: respx.Route) -> dict[str, str]:
    return dict(route.calls.last.request.url.params)


# ----------------------------------------------------------------------------- appointments


def test_list_providers(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/providers").respond(json={"providers": [{"provider_id": 1001}]})
    result = client.appointments.list_providers(
        service_name="ahc",
        package_ids=[1001, 1002],
        latitude=17,
        longitude=78.386,
        auto_allocate_provider=True,
    )
    assert result["providers"][0]["provider_id"] == 1001
    assert params(route) == {
        "service_name": "ahc",
        "package_ids": "1001,1002",
        "latitude": "17.0",
        "longitude": "78.386",
        "auto_allocate_provider": "true",
    }


def test_list_slots(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/providers/1001/ahc/slots").respond(json={"booking_slots": []})
    client.appointments.list_slots(
        1001, "ahc", package_ids="1001", pincode="500081", booking_date=dt.date(2026, 1, 15)
    )
    assert params(route) == {
        "package_ids": "1001",
        "pincode": "500081",
        "booking_date": "2026-01-15",
    }
    route2 = router.get("/api/providers/2001/inclinic_consultation/slots").respond(json={})
    client.consultations.list_slots(2001, "inclinic_consultation", package_ids=[2001])
    assert route2.called


def test_create_appointment(router: respx.MockRouter, client: Hlthstack) -> None:
    response = {"booking_id": "EKI0000000001700000000", "provider_id": 1001, "customers": []}
    route = router.post("/api/appointments").respond(json=response)
    result = client.appointments.create(
        service_name="ahc",
        appointment_type="inclinic",
        provider_id=1001,
        appointment_date_time=dt.datetime(
            2026, 1, 15, 8, 0, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30))
        ),
        customers=[CUSTOMER],
    )
    assert result == response
    assert route.calls.last.request.headers["Content-Type"] == "application/json"
    assert body(route) == {
        "service_name": "ahc",
        "appointment_type": "inclinic",
        "provider_id": 1001,
        "appointment_date_time": "2026-01-15T02:30:00Z",
        "customers": [CUSTOMER],
    }


def test_get_appointment(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/appointments").respond(json={"appointments": []})
    client.appointments.get("EKI0000000001700000000", appointment_id="APT1A2B3C4D5")
    assert params(route) == {
        "booking_id": "EKI0000000001700000000",
        "appointment_id": "APT1A2B3C4D5",
    }


def test_reschedule_and_cancel_booking(router: respx.MockRouter, client: Hlthstack) -> None:
    resched = router.patch("/api/bookings/EKI0000000001700000000/reschedule").respond(
        json={"message": "ok", "success": "APT1", "failed": ""}
    )
    cancel = router.patch("/api/appointments/APT1A2B3C4D5/cancel").respond(
        json={"message": "Appointment cancelled"}
    )
    result = client.appointments.reschedule_booking(
        "EKI0000000001700000000", appointment_date_time="2026-01-16T02:30:00Z", provider_id=1002
    )
    assert result["success"] == "APT1"
    assert body(resched) == {"appointment_date_time": "2026-01-16T02:30:00Z", "provider_id": 1002}
    client.appointments.cancel("APT1A2B3C4D5")
    assert cancel.calls.last.request.content == b""


def test_path_parameters_are_escaped(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/appointments/APT%2F..%2Fx/reports").respond(json={"reports": []})
    client.appointments.get_reports("APT/../x")
    assert route.called


def test_voucher_returns_bytes(router: respx.MockRouter, client: Hlthstack) -> None:
    pdf = b"%PDF-1.4 example"
    router.get("/api/appointments/APT1A2B3C4D5/voucher").respond(
        content=pdf, headers={"Content-Type": "application/pdf"}
    )
    router.get("/api/consultations/APT1A2B3C4D5/voucher").respond(
        content=pdf, headers={"Content-Type": "application/pdf"}
    )
    assert client.appointments.get_voucher("APT1A2B3C4D5") == pdf
    assert client.consultations.get_voucher("APT1A2B3C4D5") == pdf


# ----------------------------------------------------------------------------- consultations


def test_create_inclinic_consultation(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.post("/api/consultations/inclinic_consultation").respond(
        json={"booking_id": "EKI0000000001700000000", "provider_id": 2001, "customers": []}
    )
    client.consultations.create_inclinic(
        provider_id=2001,
        appointment_date_time="2026-01-15T04:30:00.000Z",
        service_mode="at_provider_location",
        customers=[CONSULT_CUSTOMER],
        address=ADDRESS,
    )
    sent = body(route)
    assert sent["service_mode"] == "at_provider_location"
    assert sent["address"] == ADDRESS
    assert sent["appointment_date_time"] == "2026-01-15T04:30:00.000Z"


def test_specialist_consultation_flow(router: respx.MockRouter, client: Hlthstack) -> None:
    providers = router.get("/api/consultations/specialist_consultation/providers").respond(
        json={"providers": []}
    )
    create = router.post("/api/consultations/specialist_consultation").respond(json={})
    cancel = router.patch("/api/consultations/APT1A2B3C4D5/cancel").respond(
        json={"msg": "Appointment cancelled"}
    )
    client.consultations.list_specialist_providers(package_ids=[3001], default_provider=True)
    assert params(providers) == {"package_ids": "3001", "default_provider": "true"}
    client.consultations.create_specialist(
        provider_id=3001, customers=[CONSULT_CUSTOMER], priority_consultation=True
    )
    assert body(create) == {
        "provider_id": 3001,
        "customers": [CONSULT_CUSTOMER],
        "priority_consultation": True,
    }
    assert client.consultations.cancel("APT1A2B3C4D5") == {"msg": "Appointment cancelled"}
    assert cancel.called


# ----------------------------------------------------------------------------- pharmacy


def test_cart_query_uses_bracketed_customer_details(
    router: respx.MockRouter, client: Hlthstack
) -> None:
    route = router.get("/api/epharmacy/cart").respond(json={"success": True, "cart": {"id": 701}})
    result = client.pharmacy.get_cart(api_customer_id="CUST1001", plan_id="EXAMPLE_PLAN")
    assert result["cart"]["id"] == 701
    assert params(route) == {
        "customer_details[api_customer_id]": "CUST1001",
        "plan_id": "EXAMPLE_PLAN",
    }


def test_update_cart_json(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.patch("/api/epharmacy/cart").respond(json={"success": True, "cart": {}})
    client.pharmacy.update_cart(
        customer_details={"api_customer_id": "CUST1001", "name": "Jane Doe"},
        products=[{"id": 50001, "quantity": 2}, {"id": 50002, "quantity": 0}],
    )
    assert body(route) == {
        "customer_details": {"api_customer_id": "CUST1001", "name": "Jane Doe"},
        "products": [{"id": 50001, "quantity": 2}, {"id": 50002, "quantity": 0}],
    }


def test_create_order_and_confirm(router: respx.MockRouter, client: Hlthstack) -> None:
    create = router.post("/api/epharmacy/orders").respond(
        json={"success": True, "status": "partner_payment_pending", "booking_id": 1}
    )
    confirm = router.post("/api/epharmacy/orders/EPO000000000001/confirm").respond(
        json={"success": True, "status": "confirmed", "order_id": "EPO000000000001"}
    )
    client.pharmacy.create_order(
        api_customer_id="CUST1001",
        cart_id=701,
        delivery_option="standard",
        location_token="example-location-token",
    )
    assert body(create) == {
        "customer_details": {"api_customer_id": "CUST1001"},
        "cart_id": 701,
        "delivery_option": "standard",
        "location_token": "example-location-token",
    }
    client.pharmacy.confirm_order(
        "EPO000000000001",
        api_customer_id="CUST1001",
        partner_collected_amount="1200.00",
        partner_payment_reference="PAY-0001",
    )
    assert body(confirm) == {
        "customer_details": {"api_customer_id": "CUST1001"},
        "partner_collected_amount": "1200.00",
        "partner_payment_reference": "PAY-0001",
    }


def test_get_order(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.get("/api/epharmacy/orders/EPO000000000001").respond(
        json={"success": True, "order": {"unique_id": "EPO000000000001"}}
    )
    result = client.pharmacy.get_order("EPO000000000001", api_customer_id="CUST1001")
    assert result["order"]["unique_id"] == "EPO000000000001"
    assert params(route) == {"customer_details[api_customer_id]": "CUST1001"}


# ----------------------------------------------------------------------------- wallet


def test_wallet(router: respx.MockRouter, client: Hlthstack) -> None:
    wallet = router.get("/api/example-co/customers/wallet").respond(
        json={"status": "success", "data": {"members": []}}
    )
    plans = router.get("/api/example-co/customers/plans").respond(
        json={"status": "success", "data": {"customer_plans": []}}
    )
    client.wallet.get_customer_wallet("example-co", api_customer_id="CUST1001", customer_plan_id=7)
    assert params(wallet) == {"api_customer_id": "CUST1001", "customer_plan_id": "7"}
    client.wallet.list_customer_plans("example-co", customer_id="EKI000000001")
    assert params(plans) == {"customer_id": "EKI000000001"}


# ----------------------------------------------------------------------------- testing


def test_testing_simulators(router: respx.MockRouter, client: Hlthstack) -> None:
    appt = router.post("/api/appointments/APT1A2B3C4D5/update_status").respond(
        json={"messages": ["Appointment status updated successfully"]}
    )
    consult = router.patch("/api/consultations/APT1A2B3C4D5/update_status").respond(
        json={"messages": ["ok"]}
    )
    order = router.patch("/api/epharmacy/orders/EPO000000000001/update_status").respond(
        json={"success": True}
    )
    client.testing.simulate_appointment_status("APT1A2B3C4D5", status="confirm")
    assert body(appt) == {"status": "confirm"}
    client.testing.simulate_consultation_status(
        "APT1A2B3C4D5", status="reschedule", reschedule_time="2026-01-16T04:30:00Z"
    )
    assert body(consult) == {"status": "reschedule", "reschedule_time": "2026-01-16T04:30:00Z"}
    client.testing.simulate_order_status(
        "EPO000000000001", api_customer_id="CUST1001", status="in_progress"
    )
    assert body(order) == {
        "customer_details": {"api_customer_id": "CUST1001"},
        "status": "in_progress",
    }


def test_empty_success_body_returns_empty_dict(router: respx.MockRouter, client: Hlthstack) -> None:
    router.patch("/api/bookings/EKI0000000001700000000/cancel").mock(
        return_value=httpx.Response(200)
    )
    assert client.appointments.cancel_booking("EKI0000000001700000000") == {}
