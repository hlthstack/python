"""Fill a member's ePharmacy cart and place the order.

    python examples/api/pharmacy_order.py

Uses HLTHSTACK_USERNAME / HLTHSTACK_PASSWORD against staging (see client.py).
"""

from typing import Any

from client import api

CUSTOMER = {"api_customer_id": "CUST1001"}


def place_order(medicine_id: int) -> dict[str, Any]:
    cart = api(
        "PATCH",
        "/api/epharmacy/cart",
        json={
            "customer_details": CUSTOMER,
            "products": [{"id": medicine_id, "quantity": 1}],
            "address": {
                "line1": "1 Example Road",
                "line2": "Motera",
                "city": "Ahmedabad",
                "state": "Gujarat",
                "pincode": "380005",
            },
        },
    )["cart"]
    options = api(
        "GET",
        "/api/epharmacy/fulfillment_options",  # slow: typically 3-8 seconds
        params={
            "customer_details[api_customer_id]": CUSTOMER["api_customer_id"],
            "cart_id": cart["id"],
        },
    )
    delivery = options.get("delivery_options") or {}
    if not delivery.get("success") or "standard" not in delivery:  # HTTP 200 can still fail
        raise SystemExit(f"Standard delivery unavailable: {delivery.get('message')}")
    order: dict[str, Any] = api(
        "POST",
        "/api/epharmacy/orders",
        json={
            "customer_details": CUSTOMER,
            "cart_id": cart["id"],
            "delivery_option": "standard",
            "location_token": delivery["standard"]["location_token"],
        },
    )
    return order  # status: confirmed | payment_pending | partner_payment_pending


if __name__ == "__main__":
    medicines = api("GET", "/api/epharmacy/medicines/search", params={"name": "paracetamol"})
    order = place_order(medicines["medicines"][0]["id"])
    print(order["status"], order["user_prescription_details"]["unique_id"])
