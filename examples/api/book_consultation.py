"""Book an in-clinic doctor consultation.

    python examples/api/book_consultation.py

Uses HLTHSTACK_USERNAME / HLTHSTACK_PASSWORD against staging (see client.py). Set
HLTHSTACK_CONSULTATION_PACKAGE_ID to a consultation package id shared with you for staging.
"""

import os
from typing import Any

from client import api

PACKAGE_ID = int(os.environ.get("HLTHSTACK_CONSULTATION_PACKAGE_ID", "2001"))


def book_inclinic_consultation() -> dict[str, Any]:
    doctors = api(
        "GET",
        "/api/consultations/inclinic_consultation/providers",
        params={"package_ids": str(PACKAGE_ID), "pincode": "500084", "sort_by": "distance"},
    )["providers"]
    provider_id = doctors[0]["provider_id"]
    slots = api(
        "GET",
        f"/api/providers/{provider_id}/inclinic_consultation/slots",
        params={"package_ids": str(PACKAGE_ID)},
    )
    slot_time = next(
        slot["utc_slot_time"]
        for day in slots["booking_slots"]
        for slot in day["slots"]
        if slot["available"]
    )
    booking: dict[str, Any] = api(
        "POST",
        "/api/consultations/inclinic_consultation",
        json={
            "appointment_date_time": slot_time,  # must be in the future
            "service_mode": "at_provider_location",
            "provider_id": provider_id,
            "customers": [
                {
                    "name": "Jane Doe",
                    "dob": "1990-08-24",
                    "mobile_number": "9999999999",
                    "api_customer_id": "CUST1001",
                    "gender": "female",
                    "package_ids": [PACKAGE_ID],
                }
            ],
            "address": {  # the member's address; pincode is required here
                "address_line_one": "1 Example Road",
                "address_line_two": "Kondapur",
                "city": "Hyderabad",
                "state": "Telangana",
                "country": "India",
                "pincode": "500084",
                "latitude": 17.47,
                "longitude": 78.35,
            },
        },
    )
    return booking


if __name__ == "__main__":
    booking = book_inclinic_consultation()
    print(booking["booking_id"], booking["customers"][0]["appointment_id"])
