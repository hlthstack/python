"""Pre-register a member, wait for the outcome, then update and deactivate them.

    python examples/api/pre_registration.py

Uses HLTHSTACK_PREREG_USERNAME / HLTHSTACK_PREREG_PASSWORD (the pre-registration account,
not the booking API credentials) against staging (see client.py).
"""

import time
from typing import Any

from client import pre_registration_api

MAX_ROWS = 250  # employees + dependants per call

EMPLOYEE = {
    # Every required key must be present in every row, even when empty, or the row is
    # silently dropped.
    "employee_code": "EMP1001",
    "company_id": "1001",
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane.doe@example.com",
    "date_of_birth": "24-08-1990",  # DD-MM-YYYY
    "gender": "Female",
    "mobile_number": "9999999999",
    "vip": "No",
    "entity_name": "",
    "employee_office_location": "Hyderabad",
    "department": "Engineering",
    "grade": "B",
    "date_of_joining": "01-01-2026",
}


def submit(path: str, body: dict[str, list[Any]]) -> str:
    rows = sum(len(body.get(key, [])) for key in ("employees", "dependants"))
    if rows > MAX_ROWS:
        raise ValueError(f"at most {MAX_ROWS} rows per call, got {rows}")
    accepted = pre_registration_api("POST", path, json=body)
    return str(accepted["request_id"])


def wait_for(request_id: str) -> dict[str, Any]:
    while True:
        status: dict[str, Any] = pre_registration_api(
            "GET", f"/v1/corporate/pre_registrations/{request_id}/status"
        )
        if status["status"] == "completed":
            return status
        time.sleep(5)


def main() -> None:
    request_id = submit("/v1/corporate/pre_registrations", {"employees": [EMPLOYEE]})
    status = wait_for(request_id)
    for record in status["failure_records"]:
        print("failed:", record.get("email"), record["errors"])

    update = {"employees": [{"email": "jane.doe@example.com", "grade": "C"}]}
    wait_for(submit("/v1/corporate/pre_registrations/update", update))

    deactivate = {"employees": ["jane.doe@example.com"]}  # emails; dependants by mobile
    wait_for(submit("/v1/corporate/pre_registrations/deactivate", deactivate))


if __name__ == "__main__":
    main()
