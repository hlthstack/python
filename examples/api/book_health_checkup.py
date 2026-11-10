"""Book, reschedule, confirm (staging), download the voucher for, and cancel a health checkup.

    python examples/api/book_health_checkup.py

Uses HLTHSTACK_USERNAME / HLTHSTACK_PASSWORD against staging (see client.py). Set
HLTHSTACK_PACKAGE_ID to a package id shared with you for staging.
"""

import os
from typing import Any

from client import APIError, api

PACKAGE_ID = int(os.environ.get("HLTHSTACK_PACKAGE_ID", "1001"))
PINCODE = "500081"


def list_providers() -> list[dict[str, Any]]:
    response = api(
        "GET",
        "/api/providers",
        params={"service_name": "ahc", "package_ids": str(PACKAGE_ID), "pincode": PINCODE},
    )
    providers: list[dict[str, Any]] = response["providers"]
    return providers


def available_slots(provider_id: int) -> list[str]:
    # No booking_date: up to 14 days of slots, from the provider's first bookable date.
    response = api(
        "GET",
        f"/api/providers/{provider_id}/ahc/slots",
        params={"package_ids": str(PACKAGE_ID), "pincode": PINCODE},
    )
    return [
        slot["utc_slot_time"]
        for day in response["booking_slots"]
        for slot in day["slots"]
        if slot["available"]
    ]


def create_booking(provider_id: int, slot_time: str) -> dict[str, Any]:
    booking: dict[str, Any] = api(
        "POST",
        "/api/appointments",
        json={
            "service_name": "ahc",
            "appointment_type": "inclinic",
            "provider_id": provider_id,
            "appointment_date_time": slot_time,  # a slot's utc_slot_time
            "customers": [
                {
                    "name": "Jane Doe",
                    "dob": "1990-08-24",
                    "gender": "female",
                    "mobile_number": "9999999999",
                    "api_customer_id": "CUST1001",
                    "package_ids": [PACKAGE_ID],
                }
            ],
        },
    )
    return booking


def get_booking(booking_id: str) -> dict[str, Any]:
    details: dict[str, Any] = api("GET", "/api/appointments", params={"booking_id": booking_id})
    return details


def reschedule(appointment_id: str, slot_time: str) -> None:
    api(
        "PATCH",
        f"/api/appointments/{appointment_id}/reschedule",
        json={"appointment_date_time": slot_time},
    )


def cancel(appointment_id: str) -> None:
    api("PATCH", f"/api/appointments/{appointment_id}/cancel")


def download_voucher(appointment_id: str, path: str) -> None:
    pdf: bytes = api("GET", f"/api/appointments/{appointment_id}/voucher")
    with open(path, "wb") as f:
        f.write(pdf)


def simulate_confirmation(appointment_id: str) -> None:
    """Staging only: confirm the appointment as the provider would."""
    api("POST", f"/api/appointments/{appointment_id}/update_status", json={"status": "confirm"})


def main() -> None:
    providers = list_providers()
    if not providers:
        raise SystemExit("No provider serves this package near this pincode.")
    provider_id = providers[0]["provider_id"]

    slots = available_slots(provider_id)
    if len(slots) < 2:
        raise SystemExit("Not enough free slots at this provider.")

    try:
        booking = create_booking(provider_id, slots[0])
    except APIError as e:
        # Don't blindly retry: the booking may have been created. Check first.
        raise SystemExit(f"Booking failed: {e.messages}") from e
    print("booking", booking["booking_id"], booking.get("status"))
    appointment_id = booking["customers"][0]["appointment_id"]

    for appointment in get_booking(booking["booking_id"])["appointments"]:
        print(appointment["appointment_id"], appointment["status"])

    reschedule(appointment_id, slots[1])
    simulate_confirmation(appointment_id)
    download_voucher(appointment_id, "voucher.pdf")
    cancel(appointment_id)
    print("rescheduled, confirmed, voucher saved to voucher.pdf, cancelled")


if __name__ == "__main__":
    main()
