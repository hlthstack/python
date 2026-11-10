"""Upload a prescription for digitization (multipart) and wait for the result.

    python examples/api/upload_prescription.py prescription.pdf

Uses HLTHSTACK_USERNAME / HLTHSTACK_PASSWORD against staging (see client.py).
"""

import sys
import time
import uuid
from typing import Any

from client import api


def digitize_prescription(path: str, idempotency_key: str) -> dict[str, Any]:
    with open(path, "rb") as f:
        content = f.read()  # bytes, so the retry after a 401 can resend the file
    content_type = "application/pdf" if path.lower().endswith(".pdf") else "image/jpeg"
    accepted: dict[str, Any] = api(
        "POST",
        "/api/prescriptions/digitize",
        data={  # bracketed form field names, exactly one customer
            "customers[][name]": "Jane Doe",
            "customers[][api_customer_id]": "CUST1001",
            "customers[][mobile_number]": "9999999999",
            "customers[][gender]": "female",
            "customers[][dob]": "1990-08-24",
        },
        files=[("files[]", (path.rsplit("/", 1)[-1], content, content_type))],
        headers={"Idempotency-Key": idempotency_key},  # retries return the same request
    )
    return accepted  # 202 {"request_id": ..., "status": "pending"}


def wait_for_digitization(request_id: str) -> dict[str, Any]:
    while True:
        result: dict[str, Any] = api("GET", f"/api/prescriptions/digitize/{request_id}")
        if result["status"] in ("completed", "partial", "rejected", "failed"):
            return result
        time.sleep(10)  # or wait for the digitization_results webhook


def main() -> None:
    accepted = digitize_prescription(sys.argv[1], idempotency_key=str(uuid.uuid4()))
    result = wait_for_digitization(accepted["request_id"])
    print(result["status"], result.get("cart_id"), result.get("items"))


if __name__ == "__main__":
    main()
