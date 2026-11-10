# hlthstack Python SDK

The official Python client for the [hlthstack](https://www.hlthstack.io/) partner REST API:
book health checkups and lab tests, in-clinic and online doctor consultations and ePharmacy
orders for your members, read their benefit wallets, and verify the webhooks hlthstack
sends you.

- Sync (`Hlthstack`) and async (`AsyncHlthstack`) clients with the same methods
- Access tokens fetched, cached and refreshed for you
- One method per API operation, with `TypedDict` types for requests and responses
- Webhook signature verification with the standard library only
- Python 3.9+, one dependency ([httpx](https://www.python-httpx.org/))

REST API reference and guides: https://github.com/hlthstack/integration-guide

## Install

```bash
pip install hlthstack
```

## Quickstart

```python
import os
from hlthstack import Hlthstack

client = Hlthstack(
    username=os.environ["HLTHSTACK_USERNAME"],
    password=os.environ["HLTHSTACK_PASSWORD"],
    environment="staging",
)

# 1. Find providers for a health-check package near a pincode
providers = client.appointments.list_providers(
    service_name="ahc", package_ids=[1001], pincode="500081"
)
provider = providers["providers"][0]

# 2. Pick a slot
slots = client.appointments.list_slots(
    provider["provider_id"],
    "ahc",
    package_ids=[1001],
    pincode="500081",
    booking_date="2026-01-15",
)
slot = next(s for day in slots["booking_slots"] for s in day["slots"] if s["available"])

# 3. Book it
booking = client.appointments.create(
    service_name="ahc",
    appointment_type="inclinic",
    provider_id=provider["provider_id"],
    appointment_date_time=slot["utc_slot_time"],
    customers=[
        {
            "name": "Jane Doe",
            "dob": "1990-08-24",
            "gender": "female",
            "mobile_number": "9999999999",
            "api_customer_id": "CUST1001",
            "package_ids": [1001],
        }
    ],
)

# 4. Get the booking
details = client.appointments.get(booking["booking_id"])
for appointment in details["appointments"]:
    print(appointment["appointment_id"], appointment["status"])

client.close()
```

### Async

```python
import asyncio
import os
from hlthstack import AsyncHlthstack


async def main() -> None:
    async with AsyncHlthstack(
        username=os.environ["HLTHSTACK_USERNAME"],
        password=os.environ["HLTHSTACK_PASSWORD"],
        environment="staging",
    ) as client:
        providers = await client.appointments.list_providers(
            service_name="ahc", package_ids=[1001], pincode="500081"
        )
        provider_id = providers["providers"][0]["provider_id"]
        booking = await client.appointments.create(
            service_name="ahc",
            appointment_type="inclinic",
            provider_id=provider_id,
            appointment_date_time="2026-01-15T02:30:00Z",
            customers=[
                {
                    "name": "Jane Doe",
                    "dob": "1990-08-24",
                    "gender": "female",
                    "mobile_number": "9999999999",
                    "api_customer_id": "CUST1001",
                    "package_ids": [1001],
                }
            ],
        )
        details = await client.appointments.get(booking["booking_id"])
        print(details["appointments"][0]["status"])


asyncio.run(main())
```

## Configuration

```python
Hlthstack(
    username="...",  # API username issued by hlthstack
    password="...",  # API password issued by hlthstack
    environment="production",  # or "staging"
    base_url=None,  # override the environment's URL
    entity_id=None,  # multi-entity partners: default entity to act for
    secret_key=None,  # API secret key; required with entity_id
    timeout=60.0,  # seconds, or an httpx.Timeout
)
```

Use one client per set of credentials and reuse it: it keeps a connection pool and the
access token. Close it with `client.close()` (`await client.aclose()` for the async
client), or use it as a context manager. Credentials, the entity secret key and webhook
secrets are server-side secrets: never ship them in a browser or mobile app.

### Environments

| `environment` | Base URL |
|---|---|
| `"production"` (default) | `https://api.hlthstack.io` |
| `"staging"` | `https://staging-api.hlthstack.io` |

Credentials, package ids, plan ids, entity ids and webhook secrets differ per environment.

### Authentication

You never handle tokens yourself. On the first call the client requests an access token
(`GET /api/get-access-token` with HTTP Basic auth), caches it, and requests a new one five
minutes before it expires (tokens last one hour). If a call still returns 401, the client
fetches a new token and retries that call once. Token refreshes are shared between threads
(sync client) or tasks (async client). `client.get_access_token()` fetches a token
explicitly if you need one.

### Multi-entity partners

Pass `entity_id` and `secret_key` to act for another entity on every call; the client sends
them as `API-ENTITY-ID` and `API-SECRET-KEY` (never on the token request). Override the
entity for a single call with `entity_id=`:

```python
client = Hlthstack(username="...", password="...", entity_id="1001", secret_key="...")
client.appointments.get("EKI0000000001700000000", entity_id="1002")
```

Without `entity_id`, calls act for the entity tied to your credentials.

## API surface

Methods map one-to-one to the operations in the
[OpenAPI spec](https://github.com/hlthstack/integration-guide/blob/main/openapi/openapi.yaml).
Path parameters are positional; everything else is a keyword argument named as in the
spec. Optional arguments left as `None` are not sent. Every method also takes `entity_id=`
and `secret_key=`.

| Namespace | Methods (operationId) |
|---|---|
| `client` | `get_access_token` (getAccessToken) |
| `client.appointments` | `list_providers` (listProviders), `list_slots` (listSlots), `create` (createAppointment), `get` (getAppointment), `list_customer_appointments` (listCustomerAppointments), `get_payment_details` (getAppointmentPaymentDetails), `reschedule_booking` (rescheduleBooking), `cancel_booking` (cancelBooking), `reschedule` (rescheduleAppointment), `cancel` (cancelAppointment), `get_voucher` (getAppointmentVoucher), `get_reports` (getAppointmentReports), `get_lab_results` (getAppointmentLabResults) |
| `client.consultations` | `list_inclinic_providers` (listInclinicConsultationProviders), `list_specialist_providers` (listSpecialistConsultationProviders), `list_slots` (listSlots), `create_inclinic` (createInclinicConsultation), `create_specialist` (createSpecialistConsultation), `get_inclinic` (getInclinicConsultation), `get_specialist` (getSpecialistConsultation), `reschedule` (rescheduleConsultation), `cancel` (cancelConsultation), `get_summary_and_prescription` (getConsultationSummaryAndPrescription), `get_voucher` (getConsultationVoucher), `upload_documents` (uploadConsultationDocuments) |
| `client.pharmacy` | `search_medicines` (searchMedicines), `digitize_prescription` (digitizePrescription), `get_prescription_digitization` (getPrescriptionDigitization), `get_cart` (getCart), `update_cart` (updateCart), `get_fulfillment_options` (getFulfillmentOptions), `get_order_payment_details` (getOrderPaymentDetails), `create_order` (createOrder), `list_orders` (listOrders), `get_order` (getOrder), `cancel_order` (cancelOrder), `confirm_order` (confirmOrder) |
| `client.wallet` | `get_customer_wallet` (getCustomerWallet), `list_customer_plans` (listCustomerPlans) |
| `client.testing` | **Staging only.** `simulate_appointment_status` (simulateAppointmentStatus), `simulate_consultation_status` (simulateConsultationStatus), `simulate_order_status` (simulateOrderStatus) |

A few conveniences on top of the raw API:

- `package_ids` accepts a list (`[1001, 1002]`) or the comma-separated string.
- Date and date-time arguments accept strings or `datetime.date` / timezone-aware
  `datetime.datetime` objects (sent as UTC, `2026-01-15T02:30:00Z`).
- Where the API wraps the member id as `customer_details[api_customer_id]` (query) or
  `{"customer_details": {"api_customer_id": ...}}` (body) and nothing else, the method takes
  `api_customer_id=` directly. `update_cart` takes the full `customer_details` dict.
- `digitize_prescription` takes a single `customer` (the API accepts exactly one).

Responses are the parsed JSON `dict`s, typed with the `TypedDict`s in `hlthstack.types`.
Many keys are present only in some states; read them with `.get()`.

### Files

Uploads accept a path, `bytes`, a binary file object, or a
`(filename, content)` / `(filename, content, content_type)` tuple:

```python
client.consultations.upload_documents(
    "APT1A2B3C4D5",
    [("Blood report", "reports/blood.pdf"), ("X-ray", open("xray.png", "rb"))],
)
client.pharmacy.digitize_prescription(
    customer={
        "name": "Jane Doe",
        "api_customer_id": "CUST1001",
        "mobile_number": "9999999999",
        "gender": "female",
        "dob": "1990-08-24",
    },
    files=["prescription.pdf"],
    idempotency_key="upload-0001",
)
client.pharmacy.update_cart(
    customer_details={"api_customer_id": "CUST1001"},
    prescription_files=[("rx.jpg", jpeg_bytes, "image/jpeg")],
)
```

Vouchers come back as PDF bytes:

```python
pdf = client.appointments.get_voucher("APT1A2B3C4D5")
with open("voucher.pdf", "wb") as f:
    f.write(pdf)
```

### Testing on staging

`client.testing` wraps the staging-only endpoints that move a booking or order through its
lifecycle and fire real webhooks. They don't exist in production (it returns 401 or 404),
so only use them with `environment="staging"`:

```python
client.testing.simulate_appointment_status("APT1A2B3C4D5", status="confirm")
client.testing.simulate_consultation_status(
    "APT1A2B3C4D5", status="reschedule", reschedule_time="2026-01-16T04:30:00Z"
)
client.testing.simulate_order_status(
    "EPO000000000001", api_customer_id="CUST1001", status="in_progress"
)
```

## Errors

Non-2xx responses raise a subclass of `hlthstack.HlthstackError`:

| Exception | Status |
|---|---|
| `BadRequestError` | 400 |
| `AuthenticationError` | 401 (after one token refresh), or wrong credentials |
| `PermissionDeniedError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `UnprocessableEntityError` | 422 |
| `ServerError` | 5xx |
| `HlthstackError` | any other non-2xx status |
| `APIConnectionError` | network error or timeout (no response) |

Every error has `status_code`, `body` (parsed JSON, or text), `headers`, and `messages`: the
human-readable messages pulled out of whichever error shape the endpoint uses
(`{"errors": {"field": [...]}}`, `{"errors": {"messages": [...]}}`, `{"message": ...}`,
`{"msg": ..., "recall": ...}`, `{"error": ...}`, `{"errors": [...]}`, plain text).

```python
from hlthstack import BadRequestError, HlthstackError

try:
    client.appointments.reschedule("APT1A2B3C4D5", appointment_date_time="2026-01-16T02:30:00Z")
except BadRequestError as e:
    print(e.status_code, e.messages, e.body)
except HlthstackError as e:
    print("hlthstack error:", e)
```

The client does not retry failed calls (other than the single retry after a 401). Retry 5xx,
409 and network errors with backoff yourself, and never blindly retry booking creation:
check `appointments.get` or your webhooks first. Some ePharmacy responses are HTTP 200 with
`"success": false` nested inside (for example fulfillment options); check those flags.

## Webhooks

hlthstack signs every webhook with an HS256 JWT in the `Signature` header. The JWT does not
cover the body, so `verify_signature` checks the signature, that the ids in the claims match
the body, and that the `timestamp` claim is within 5 minutes:

```python
import os
from flask import Flask, abort, request
from hlthstack.webhooks import WebhookVerificationError, verify_signature

SECRET = os.environ["HLTHSTACK_WEBHOOK_SECRET"]
app = Flask(__name__)


@app.post("/hlthstack/webhooks")
def webhook():
    try:
        verify_signature(request.get_data(), request.headers.get("Signature"), SECRET)
    except WebhookVerificationError:
        abort(401)
    enqueue(request.get_json())  # acknowledge fast, process asynchronously
    return "", 200
```

`verify_signature(body, signature, secret, *, tolerance=300)` takes the raw body (bytes or
str) or the parsed JSON object and returns the JWT claims. Payload types for the seven
webhook events are in `hlthstack.webhooks`: `AppointmentStatusUpdateWebhook`,
`ConsultationStatusUpdateWebhook`, `LabResultsWebhook`, `PharmacyOrderStatusUpdateWebhook`,
`PharmacyAdditionalPaymentRequiredWebhook`, `PharmacyPostBillingWebhook` and
`PrescriptionDigitizedWebhook`.

Delivery is at-least-once and unordered: deduplicate, use the claims' `timestamp` to drop
older events, and treat `appointments.get` / `pharmacy.get_order` as the source of truth.
See the [webhooks guide](https://github.com/hlthstack/integration-guide/blob/main/docs/webhooks.md).

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e . --group dev
pytest
ruff check . && ruff format --check .
mypy
```

`src/hlthstack/_sync_resources.py` is generated from `_async_resources.py`: edit the async
file, then run `python scripts/unasync.py`.

## License

MIT
