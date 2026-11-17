# SDK integration (Python)

Integrate with the hlthstack partner REST API through this package, `hlthstack`. To call
the API over plain HTTP without it, see the [plain REST API guide](api-integration.md).

- Sync (`Hlthstack`) and async (`AsyncHlthstack`) clients with the same methods
- Access tokens fetched, cached and refreshed for you
- One method per API operation, with `TypedDict` types for requests and responses
- Every request checked against the API's input rules before it is sent, with all problems
  reported at once
- Webhook signature verification with the standard library only
- Python 3.9+, one dependency ([httpx](https://www.python-httpx.org/))

**See also:** [REST API reference and guides](https://github.com/hlthstack/integration-guide)

**On this page**

- [Install](#install)
- [Quickstart](#quickstart) · [Async](#async)
- [Configuration](#configuration) · [Environments](#environments) ·
  [Authentication](#authentication) · [Multi-entity partners](#multi-entity-partners)
- [API surface](#api-surface) · [Files](#files) · [Pre-registration](#pre-registration) ·
  [Testing on staging](#testing-on-staging)
- [Errors](#errors)
- [Validation](#validation)
- [Webhooks](#webhooks)
- [Development](#development)

## Install

Install the library straight from this GitHub repository:

```bash
pip install "git+https://github.com/hlthstack/python@v1.0.2"
```

In `requirements.txt`:

```text
hlthstack @ git+https://github.com/hlthstack/python@v1.0.2
```

> [!TIP]
> Pin a release tag, as above, so your builds are reproducible. Releases and their changes
> are listed in [CHANGELOG.md](../CHANGELOG.md).

The same `hlthstack @ git+https://...` form works in `pyproject.toml` dependencies.

> [!NOTE]
> A PyPI release (`pip install hlthstack`) may follow later; until then, install from GitHub.

## Quickstart

Find a provider, pick a slot, book a health checkup and read the booking back:

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

`AsyncHlthstack` has the same methods as `Hlthstack`; await each call and use the client as
an async context manager:

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

Every constructor argument, with its default:

```python
Hlthstack(
    username="...",  # API username issued by hlthstack (not needed for pre-registration only)
    password="...",  # API password issued by hlthstack
    environment="production",  # or "staging"
    base_url=None,  # override the environment's URL
    entity_id=None,  # multi-entity partners: default entity to act for
    secret_key=None,  # API secret key; required with entity_id
    timeout=60.0,  # seconds, or an httpx.Timeout
    pre_registration_username=None,  # pre-registration login (an email), for client.pre_registration
    pre_registration_password=None,
    validate=True,  # check requests before sending them (see Validation)
)
```

- Use one client per set of credentials and reuse it: it keeps a connection pool and the
  access token.
- Close it with `client.close()` (`await client.aclose()` for the async client), or use it as
  a context manager.

> [!CAUTION]
> Credentials, the entity secret key and webhook secrets are server-side secrets: never ship
> them in a browser or mobile app.

### Environments

| `environment` | Base URL |
|---|---|
| `"production"` (default) | `https://api.hlthstack.io` |
| `"staging"` | `https://staging-api.hlthstack.io` |

Credentials, package ids, plan ids, entity ids and webhook secrets differ per environment.

### Authentication

> [!NOTE]
> You never handle tokens yourself. Tokens last one hour; the client requests a new one five
> minutes before it expires.

- On the first call the client requests an access token (`GET /api/get-access-token` with
  HTTP Basic auth) and caches it.
- If a call still returns 401, the client fetches a new token and retries that call once.
- Token refreshes are shared between threads (sync client) or tasks (async client).
- `client.get_access_token()` fetches a token explicitly if you need one.

`client.pre_registration` uses separate credentials and its own token:

| | Main API | Pre-registration |
|---|---|---|
| Credentials | `username` / `password` | `pre_registration_username` / `pre_registration_password` |
| Token request | `GET /api/get-access-token` | `GET /api/pre_registration/access-token` |
| Sent as | Bearer token | `X-EKINCARE-KEY` |
| Explicit fetch | `client.get_access_token()` | `client.pre_registration.get_access_token()` |

The pre-registration token is cached and refreshed the same way.

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

- Path parameters are positional; everything else is a keyword argument named as in the
  spec.
- Optional arguments left as `None` are not sent.
- Every method except the `pre_registration` ones also takes `entity_id=` and `secret_key=`.
- Every method that calls the API takes `validate=` (see [Validation](#validation)).

**`client`**

| Method | Operation | Endpoint |
|---|---|---|
| `get_access_token` | getAccessToken | `GET /api/get-access-token` |

**`client.appointments`**

| Method | Operation | Endpoint |
|---|---|---|
| `list_providers` | listProviders | `GET /api/providers` |
| `list_slots` | listSlots | `GET /api/providers/{provider_id}/{benefit_type}/slots` |
| `create` | createAppointment | `POST /api/appointments` |
| `get` | getAppointment | `GET /api/appointments` |
| `reschedule_booking` | rescheduleBooking | `PATCH /api/bookings/{booking_id}/reschedule` |
| `cancel_booking` (optional `reason=`) | cancelBooking | `PATCH /api/bookings/{booking_id}/cancel` |
| `reschedule` | rescheduleAppointment | `PATCH /api/appointments/{appointment_id}/reschedule` |
| `cancel` (optional `reason=`) | cancelAppointment | `PATCH /api/appointments/{appointment_id}/cancel` |
| `get_voucher` | getAppointmentVoucher | `GET /api/appointments/{appointment_id}/voucher` |
| `get_reports` | getAppointmentReports | `GET /api/appointments/{appointment_id}/reports` |
| `get_lab_results` | getAppointmentLabResults | `GET /api/appointments/{appointment_id}/lab_results` |

**`client.consultations`**

| Method | Operation | Endpoint |
|---|---|---|
| `list_inclinic_providers` | listInclinicConsultationProviders | `GET /api/consultations/inclinic_consultation/providers` |
| `list_specialist_providers` | listSpecialistConsultationProviders | `GET /api/consultations/specialist_consultation/providers` |
| `list_slots` | listSlots | `GET /api/providers/{provider_id}/{benefit_type}/slots` |
| `create_inclinic` | createInclinicConsultation | `POST /api/consultations/inclinic_consultation` |
| `create_specialist` | createSpecialistConsultation | `POST /api/consultations/specialist_consultation` |
| `get_inclinic` | getInclinicConsultation | `GET /api/consultations/inclinic_consultation/{appointment_id}` |
| `get_specialist` | getSpecialistConsultation | `GET /api/consultations/specialist_consultation/{appointment_id}` |
| `reschedule` | rescheduleConsultation | `PATCH /api/consultations/{appointment_id}/reschedule` |
| `cancel` | cancelConsultation | `PATCH /api/consultations/{appointment_id}/cancel` |
| `get_summary_and_prescription` | getConsultationSummaryAndPrescription | `GET /api/consultations/{appointment_id}/summary_and_prescription` |
| `get_voucher` | getConsultationVoucher | `GET /api/consultations/{appointment_id}/voucher` |
| `upload_documents` | uploadConsultationDocuments | `POST /api/consultations/{appointment_id}/upload_documents` |

**`client.pharmacy`**

| Method | Operation | Endpoint |
|---|---|---|
| `search_medicines` | searchMedicines | `GET /api/epharmacy/medicines/search` |
| `digitize_prescription` | digitizePrescription | `POST /api/prescriptions/digitize` |
| `get_prescription_digitization` | getPrescriptionDigitization | `GET /api/prescriptions/digitize/{request_id}` |
| `get_cart` | getCart | `GET /api/epharmacy/cart` |
| `update_cart` | updateCart | `PATCH /api/epharmacy/cart` |
| `get_fulfillment_options` | getFulfillmentOptions | `GET /api/epharmacy/fulfillment_options` |
| `get_order_payment_details` | getOrderPaymentDetails | `POST /api/epharmacy/orders/payment_details` |
| `create_order` | createOrder | `POST /api/epharmacy/orders` |
| `list_orders` | listOrders | `GET /api/epharmacy/orders` |
| `get_order` | getOrder | `GET /api/epharmacy/orders/{order_id}` |
| `cancel_order` | cancelOrder | `PATCH /api/epharmacy/orders/{order_id}/cancel` |
| `confirm_order` | confirmOrder | `POST /api/epharmacy/orders/{order_id}/confirm` |

**`client.wallet`**

| Method | Operation | Endpoint |
|---|---|---|
| `get_customer_wallet` | getCustomerWallet | `GET /api/{company_slug}/customers/wallet` |
| `list_customer_plans` | listCustomerPlans | `GET /api/{company_slug}/customers/plans` |

**`client.pre_registration`**

| Method | Operation | Endpoint |
|---|---|---|
| `get_access_token` | getPreRegistrationAccessToken | `GET /api/pre_registration/access-token` |
| `create` | createPreRegistrations | `POST /v1/corporate/pre_registrations` |
| `update` | updatePreRegistrations | `POST /v1/corporate/pre_registrations/update` |
| `deactivate` | deactivatePreRegistrations | `POST /v1/corporate/pre_registrations/deactivate` |
| `get_status` | getPreRegistrationStatus | `GET /v1/corporate/pre_registrations/{request_id}/status` |

**`client.testing`** (**Staging only.** See [Testing on staging](#testing-on-staging).)

| Method | Operation | Endpoint |
|---|---|---|
| `simulate_appointment_status` | simulateAppointmentStatus | `POST /api/appointments/{appointment_id}/update_status` |
| `simulate_consultation_status` | simulateConsultationStatus | `PATCH /api/consultations/{appointment_id}/update_status` |
| `simulate_order_status` | simulateOrderStatus | `PATCH /api/epharmacy/orders/{order_id}/update_status` |

A few conveniences on top of the raw API:

- `package_ids` accepts a list (`[1001, 1002]`) or the comma-separated string.
- Date and date-time arguments accept strings or `datetime.date` / timezone-aware
  `datetime.datetime` objects (sent as UTC, `2026-01-15T02:30:00Z`).
- Where the API wraps the member id as `customer_details[api_customer_id]` (query) or
  `{"customer_details": {"api_customer_id": ...}}` (body) and nothing else, the method takes
  `api_customer_id=` directly. `update_cart` takes the full `customer_details` dict.
- `digitize_prescription` takes a single `customer` (the API accepts exactly one).

Responses are the parsed JSON `dict`s, typed with the `TypedDict`s in `hlthstack.types`.

> [!TIP]
> Many keys are present only in some states; read them with `.get()`.

### Files

Uploads accept any of:

- a path
- `bytes`
- a binary file object
- a `(filename, content)` / `(filename, content, content_type)` tuple

For example, consultation documents, a prescription to digitize, and cart prescriptions:

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

### Pre-registration

Register, update and deactivate members (employees) and their dependants in bulk, at most
**250 rows per call**:

1. Each write returns a `request_id`.
2. Poll `get_status` until `status` is `completed`.
3. Read `success_records` and `failure_records`.

```python
import os
import time
from hlthstack import Hlthstack

client = Hlthstack(
    pre_registration_username=os.environ["HLTHSTACK_PREREG_USERNAME"],
    pre_registration_password=os.environ["HLTHSTACK_PREREG_PASSWORD"],
    environment="staging",
)

accepted = client.pre_registration.create(
    employees=[
        {
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
        }
    ],
)
status = client.pre_registration.get_status(accepted["request_id"])
while status["status"] != "completed":
    time.sleep(5)
    status = client.pre_registration.get_status(accepted["request_id"])
for record in status["failure_records"]:
    print(record.get("email"), record["errors"])

client.pre_registration.update(employees=[{"email": "jane.doe@example.com", "grade": "C"}])
client.pre_registration.deactivate(employees=["jane.doe@example.com"])
```

> [!WARNING]
> On `create`, every key the `PreRegistrationEmployee` / `PreRegistrationDependant` types mark
> required must be present in each row, even when empty: the API silently drops rows that miss
> one.

- `update` takes the identifier and only the fields to change.
- `deactivate` takes employee emails and dependant mobile numbers.

**See also:** the
[pre-registration guide](https://github.com/hlthstack/integration-guide/blob/main/docs/pre-registration.md).

### Testing on staging

`client.testing` wraps the staging-only endpoints that move a booking or order through its
lifecycle and fire real webhooks:

```python
client.testing.simulate_appointment_status("APT1A2B3C4D5", status="confirm")
client.testing.simulate_consultation_status(
    "APT1A2B3C4D5", status="reschedule", reschedule_time="2026-01-16T04:30:00Z"
)
client.testing.simulate_order_status(
    "EPO000000000001", api_customer_id="CUST1001", status="in_progress"
)
```

> [!IMPORTANT]
> These endpoints don't exist in production (it returns 401 or 404), so only use them with
> `environment="staging"`.

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
| `ValidationError` | the request breaks the API's input rules; nothing was sent (see [Validation](#validation)) |

Every error has:

| Attribute | Contents |
|---|---|
| `status_code` | The HTTP status |
| `body` | Parsed JSON, or text |
| `headers` | The response headers |
| `messages` | The human-readable messages pulled out of whichever error shape the endpoint uses |

The error shapes `messages` understands: `{"errors": {"field": [...]}}`,
`{"errors": {"messages": [...]}}`, `{"message": ...}`, `{"msg": ..., "recall": ...}`,
`{"error": ...}`, `{"errors": [...]}`, plain text.

Catch the specific class first, then `HlthstackError`:

```python
from hlthstack import BadRequestError, HlthstackError

try:
    client.appointments.reschedule("APT1A2B3C4D5", appointment_date_time="2026-01-16T02:30:00Z")
except BadRequestError as e:
    print(e.status_code, e.messages, e.body)
except HlthstackError as e:
    print("hlthstack error:", e)
```

> [!WARNING]
> The client does not retry failed calls (other than the single retry after a 401).
>
> - Retry 5xx, 409 and network errors with backoff yourself.
> - Never blindly retry booking creation: check `appointments.get` or your webhooks first.
> - Some ePharmacy responses are HTTP 200 with `"success": false` nested inside (for example
>   fulfillment options); check those flags.

## Validation

Before a method sends its request, the client checks it against the input rules in the
[OpenAPI spec](https://github.com/hlthstack/integration-guide/blob/main/openapi/openapi.yaml)
and, if anything is wrong, raises `hlthstack.ValidationError` listing every problem.

> [!NOTE]
> Nothing is sent and no access token is requested. The check runs on the request as it
> would go out, after the method's conversions (package id lists, `datetime`s,
> `api_customer_id=`).

What is checked:

- **Fields**: required fields, types, allowed values and patterns (mobile numbers, pincodes,
  member ids, booking and appointment ids, genders, relations, dates in pre-registration
  rows), string lengths, number ranges, list sizes, and date (`YYYY-MM-DD`), date-time (ISO
  8601 with an offset, such as `2026-01-15T02:30:00Z`), URI and UUID formats.
- **Rules across fields**: for example
  - `address` for home collection
  - `pincode`, or `latitude` and `longitude`
  - `api_customer_id` or `employee_id`
  - `address` or `address_id`, not both
  - `selected_chemist_id` for store pickup
  - one entry per `api_customer_id` or product id
  - `sort_by` and `gender` only for in-clinic consultations
  - no 6-digit number other than the pincode in an Indian address's text fields
- **Dates**: members at least one year old, consultation times in the future, dates of birth
  not in the future (dates are compared with today's date in India).
- **Files and counts**: upload types, extensions and sizes; at most 250 pre-registration rows
  per call; a positive `partner_collected_amount`.

This request breaks three rules:

```python
from hlthstack import ValidationError

try:
    client.appointments.create(
        service_name="ahc",
        appointment_type="home_collection",
        provider_id=1001,
        appointment_date_time="2026-01-15T02:30:00Z",
        customers=[
            {
                "name": "Jane Doe",
                "dob": "1990-08-24",
                "gender": "Female",
                "mobile_number": "99999 99999",
                "api_customer_id": "CUST1001",
                "package_ids": [1001],
            }
        ],
    )
except ValidationError as e:
    print(e)
    for error in e.errors:
        print(error["path"], error["rule"], error["message"])
```

It prints:

```text
Invalid createAppointment request (3 problems):
  - customers[0].mobile_number: must match the pattern ^[0-9]{10}$ [pattern]
  - customers[0].gender: must be one of: male, female, non-binary [enum]
  - address: address is required when appointment_type is home_collection. [required_if]
```

About `ValidationError`:

- It subclasses `HlthstackError` (and `ValueError`).
- `errors` is a list of `{"path", "message", "rule"}` dicts:
  - `path` points into the request (`customers[0].dob`, `files[1].value`; empty for the
    request as a whole).
  - `rule` is the JSON Schema keyword (`required`, `pattern`, ...) or the spec's rule kind
    (`required_if`, `unique_by`, ...).
- `messages` has the same problems as `"path: message"` strings.

To skip the checks, for example if the API accepts something before this library is
updated, turn them off for the client or for one call:

```python
client = Hlthstack(username="...", password="...", validate=False)
client.appointments.get("EKI0000000001700000000", validate=True)  # check this one call

client = Hlthstack(username="...", password="...")
client.appointments.get("EKI0000000001700000000", validate=False)  # skip this one call
```

Checks that need data stored by hlthstack are made by the server and still come back as
`HlthstackError` subclasses (`BadRequestError`, `NotFoundError`, `UnprocessableEntityError`,
...):

- plan benefits and wallet balances
- slot availability
- provider capabilities
- whether a member, booking or cart exists and what state it is in
- the order's amount to collect
- password-protected PDFs and files fetched from `prescription_urls`

Pre-registration rows are checked again while they are processed and reported in
`failure_records`.

## Webhooks

hlthstack signs every webhook with an HS256 JWT in the `Signature` header. The JWT does not
cover the body, so `verify_signature` checks:

1. the signature,
2. that the ids in the claims match the body, and
3. that the `timestamp` claim is within 5 minutes.

A Flask receiver:

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
str) or the parsed JSON object and returns the JWT claims.

Payload types for the seven webhook events are in `hlthstack.webhooks`:

- `AppointmentStatusUpdateWebhook`
- `ConsultationStatusUpdateWebhook`
- `LabResultsWebhook`
- `PharmacyOrderStatusUpdateWebhook`
- `PharmacyAdditionalPaymentRequiredWebhook`
- `PharmacyPostBillingWebhook`
- `PrescriptionDigitizedWebhook`

> [!IMPORTANT]
> Delivery is at-least-once and unordered: deduplicate, use the claims' `timestamp` to drop
> older events, and treat `appointments.get` / `pharmacy.get_order` as the source of truth.

**See also:** the [webhooks guide](https://github.com/hlthstack/integration-guide/blob/main/docs/webhooks.md).

## Development

Set up a virtual environment, then run the tests, linters and type checks:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e . --group dev
pytest
ruff check . && ruff format --check .
mypy
```

Two modules are generated; don't edit them by hand:

- `src/hlthstack/_sync_resources.py` is generated from `_async_resources.py`: edit the async
  file, then run `python scripts/unasync.py`.
- `src/hlthstack/_validation_spec.py` is generated from `openapi/openapi.yaml` (a copy of the
  integration guide's spec): after updating the spec, run `python scripts/build_validation.py`.
  It fails if the spec uses a schema keyword or rule the validator in `_validation.py` does
  not implement; restate new `x-hlthstack-rules` in the script's `RULES` table.
