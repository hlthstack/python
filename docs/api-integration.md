# Plain REST API integration (Python)

Call the hlthstack partner REST API directly over HTTP, without the `hlthstack` SDK. The
examples use [requests](https://requests.readthedocs.io/); [httpx](https://www.python-httpx.org/)
works the same way (`httpx.Client` in place of `requests.Session`). Flask is used only for
the webhook receiver. To let a library do the token handling, input checks and error parsing
for you, see the [SDK integration guide](sdk-integration.md).

The code below is taken from runnable scripts in [`examples/api/`](../examples/api/):

| File | What it does |
|---|---|
| [`client.py`](../examples/api/client.py) | Token cache and `api()` / `pre_registration_api()` request helpers |
| [`book_health_checkup.py`](../examples/api/book_health_checkup.py) | Providers, slots, book, details, reschedule, voucher, cancel |
| [`book_consultation.py`](../examples/api/book_consultation.py) | In-clinic doctor consultation |
| [`pharmacy_order.py`](../examples/api/pharmacy_order.py) | ePharmacy cart and order |
| [`upload_prescription.py`](../examples/api/upload_prescription.py) | Multipart upload for prescription digitization |
| [`pre_registration.py`](../examples/api/pre_registration.py) | Register, update and deactivate members |
| [`webhook_receiver.py`](../examples/api/webhook_receiver.py) | Flask webhook endpoint with signature verification |

```bash
pip install -r examples/api/requirements.txt   # requests, and flask for the webhook receiver
export HLTHSTACK_USERNAME=... HLTHSTACK_PASSWORD=...   # staging credentials
python examples/api/book_health_checkup.py
```

The scripts default to staging and read their configuration from environment variables
(listed at the top of `client.py`). Every request and response field is defined in the
[OpenAPI spec](https://github.com/hlthstack/integration-guide/blob/main/openapi/openapi.yaml);
the [integration guide](https://github.com/hlthstack/integration-guide/tree/main/docs) explains
each flow in depth.

## Environments

| Environment | Base URL |
|---|---|
| Production | `https://api.hlthstack.io` |
| Staging | `https://staging-api.hlthstack.io` |

- Credentials, package ids, plan ids, entity ids and webhook secrets are different per
  environment.
- Staging has extra endpoints that move bookings and orders through their lifecycle and fire
  real webhooks ([testing](https://github.com/hlthstack/integration-guide/blob/main/docs/testing.md)).
  They don't exist in production.
- Set a client timeout of 30-60 seconds: create, reschedule and cancel calls can take a few
  seconds, and ePharmacy fulfillment options typically take 3-8 seconds.

```python
BASE_URL = os.environ.get("HLTHSTACK_BASE_URL", "https://staging-api.hlthstack.io")
TIMEOUT = 60  # seconds; create, reschedule and cancel calls can take a few seconds
REFRESH_MARGIN = 300  # request a new token 5 minutes before the current one expires

session = requests.Session()
```

## Authentication

`GET /api/get-access-token` with HTTP Basic auth, using the username and password hlthstack
issued to you, returns a token valid for one hour:

```json
{ "access_token": "YOUR_ACCESS_TOKEN", "expires_at": "2026-01-15T07:16:21Z" }
```

Send it as `Authorization: Bearer <access_token>` on every other call. There is no refresh
token: request a new token before `expires_at`. A missing, invalid or expired token returns
`401` with the plain-text body `HTTP Token: Access denied.`; wrong credentials on the token
call return `401 {"message": "Wrong credentials"}`.

### Token helper

Cache the token and fetch a new one five minutes before it expires. The lock makes one
thread fetch the token while the others wait for it:

```python
class AccessToken:
    """Fetches a token with HTTP Basic auth and caches it until shortly before it expires."""

    def __init__(self, path: str, username: str, password: str) -> None:
        self.path = path
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get(self, force_refresh: bool = False) -> str:
        with self._lock:  # one refresh at a time, shared by all threads
            if force_refresh or self._token is None or time.time() >= self._expires_at:
                response = session.get(
                    BASE_URL + self.path, auth=(self.username, self.password), timeout=TIMEOUT
                )
                if not response.ok:
                    raise APIError(response.status_code, _parse_body(response))
                data = response.json()
                self._token = str(data["access_token"])
                self._expires_at = _parse_expires_at(data["expires_at"]) - REFRESH_MARGIN
            return self._token


def _parse_expires_at(value: str) -> float:
    if value.endswith(" UTC"):  # pre-registration: "2026-01-15 07:16:21 UTC"
        expires = datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC")
    else:  # ISO 8601: "2026-01-15T07:16:21Z"
        expires = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires.timestamp()


token = AccessToken(
    "/api/get-access-token",
    os.environ.get("HLTHSTACK_USERNAME", ""),
    os.environ.get("HLTHSTACK_PASSWORD", ""),
)
```

(`datetime.fromisoformat` accepts a trailing `Z` only from Python 3.11, hence the replace.)

### Request helper

`api()` adds the bearer token, sends JSON bodies (`json=`), query strings (`params=`) or
multipart forms (`data=` + `files=`), fetches a new token and retries once on a 401, and raises
`APIError` with the parsed body on any other non-2xx response. It returns the parsed JSON, or
the raw bytes for PDF responses such as vouchers:

```python
def _send(
    auth_headers: Callable[[str], dict[str, str]],
    access_token: AccessToken,
    method: str,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    json: Any = None,
    data: Optional[dict[str, Any]] = None,
    files: Any = None,
    headers: Optional[dict[str, str]] = None,
) -> Any:
    for attempt in (1, 2):
        response = session.request(
            method,
            BASE_URL + path,
            params=params,
            json=json,
            data=data,
            files=files,
            headers={
                **auth_headers(access_token.get(force_refresh=attempt == 2)),
                **(headers or {}),
            },
            timeout=TIMEOUT,
        )
        if response.status_code == 401 and attempt == 1:
            continue  # token expired or revoked: get a new one and retry once
        if not response.ok:
            raise APIError(response.status_code, _parse_body(response))
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return response.json()
        return response.content  # vouchers are PDF bytes
    raise AssertionError("unreachable")


def api(method: str, path: str, **kwargs: Any) -> Any:
    return _send(
        lambda value: {"Authorization": f"Bearer {value}", **_entity_headers()},
        token,
        method,
        path,
        **kwargs,
    )


def _parse_body(response: requests.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text
```

`APIError` and `_entity_headers()` are in the next sections. Pass upload contents as bytes,
not open file objects, so the retry after a 401 can send them again.

```python
providers = api(
    "GET",
    "/api/providers",
    params={"service_name": "ahc", "package_ids": "1001", "pincode": "500081"},
)
```

## Multi-entity partners

If your company has several entities, your credentials are issued for the first one. To act
for another entity, add two headers to every call except `get-access-token`:

| Header | Value |
|---|---|
| `API-ENTITY-ID` | The id of the entity to act for (shared at onboarding) |
| `API-SECRET-KEY` | The secret key shared at onboarding. Required whenever `API-ENTITY-ID` is sent |

Without `API-ENTITY-ID`, calls act for the entity tied to the credentials. `client.py` sends
the headers on every call when `HLTHSTACK_ENTITY_ID` is set:

```python
def _entity_headers() -> dict[str, str]:
    entity_id = os.environ.get("HLTHSTACK_ENTITY_ID")
    if not entity_id:
        return {}  # act for the entity tied to the credentials
    return {"API-ENTITY-ID": entity_id, "API-SECRET-KEY": os.environ["HLTHSTACK_SECRET_KEY"]}
```

To act for a different entity on one call, pass the headers explicitly:

```python
api(
    "GET",
    "/api/appointments",
    params={"booking_id": "EKI0000000001700000000"},
    headers={"API-ENTITY-ID": "1002", "API-SECRET-KEY": os.environ["ENTITY_1002_SECRET_KEY"]},
)
```

Header problems return `400 {"message": "..."}`: `API-ENTITY-ID header cannot be blank`,
`API-SECRET-KEY header cannot be blank`, `Invalid Entity`,
`API integration not enabled for this entity` or `API-SECRET-KEY is invalid`. An entity whose
contract is not enabled for API booking gets
`400 {"message": "The entity is not enabled for API booking."}` on every call. See
[authentication](https://github.com/hlthstack/integration-guide/blob/main/docs/authentication.md).

## Book a health checkup

A booking covers one or more members at one provider and time (`booking_id`); each member
gets an appointment (`appointment_id`). From
[`book_health_checkup.py`](../examples/api/book_health_checkup.py), with
`PACKAGE_ID = 1001` (use the package ids shared with you) and `PINCODE = "500081"`. The full
flow is in the
[health checkups guide](https://github.com/hlthstack/integration-guide/blob/main/docs/health-checkups.md).

### 1. List providers

`GET /api/providers` with `service_name`, `package_ids` (comma-separated) and `pincode`, or
`latitude` + `longitude` instead of the pincode. Optional: `radius`, `page`, `per_page`
(at most 50), `plan_id`, `auto_allocate_provider`. Results are sorted by distance.

```python
def list_providers() -> list[dict[str, Any]]:
    response = api(
        "GET",
        "/api/providers",
        params={"service_name": "ahc", "package_ids": str(PACKAGE_ID), "pincode": PINCODE},
    )
    providers: list[dict[str, Any]] = response["providers"]
    return providers
```

### 2. Get slots

`GET /api/providers/{provider_id}/{benefit_type}/slots` with `package_ids` and `pincode`.
Pass `booking_date` (`YYYY-MM-DD`) for one day, or omit it for up to `count_days` days
(default 14). Read `booking_slots[].slots[]` and book with a slot's `utc_slot_time`. A
`booking_date` before the provider's first bookable date (from its `slot_lead_time` and
`timezone`) returns 400.

```python
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
```

### 3. Create the booking

`POST /api/appointments`. `appointment_type` is `inclinic` or `home_collection`; home
collection also needs `address` (`address_line_one`, `address_line_two`, `city`, `state`,
`country`, `pincode`, `latitude`, `longitude`). Optional: `plan_id`, `customer_plan_id` or
`subscription_id`, `api_partner_order_id`.

```python
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
```

The response has `booking_id`, `status` and `customers[].appointment_id`:

- `status: "confirmed"`: paid from the member's wallet. The appointment itself starts at
  `new` and becomes `confirmed` when the provider confirms it (you get a webhook).
- `status: "payment_pending"` with `payment_link`: the member must pay the rest.

Don't blindly retry a failed or timed-out create: check with step 4 or your webhooks whether
the booking exists first (see [Errors](#errors)).

### 4. Get the booking

`GET /api/appointments?booking_id=...` returns every appointment in the booking; add
`appointment_id` for one. Each appointment has the same shape as the webhook payload.

```python
def get_booking(booking_id: str) -> dict[str, Any]:
    details: dict[str, Any] = api("GET", "/api/appointments", params={"booking_id": booking_id})
    return details


for appointment in get_booking(booking["booking_id"])["appointments"]:
    print(appointment["appointment_id"], appointment["status"])
```

### 5. Reschedule

`PATCH /api/appointments/{appointment_id}/reschedule` (or
`PATCH /api/bookings/{booking_id}/reschedule` for the whole booking) with a new
`appointment_date_time`. Add `provider_id` to move to another provider (not allowed once the
appointment is confirmed at its provider), and for home collection `address` together with
`provider_id` to change the address.

```python
def reschedule(appointment_id: str, slot_time: str) -> None:
    api(
        "PATCH",
        f"/api/appointments/{appointment_id}/reschedule",
        json={"appointment_date_time": slot_time},
    )
```

### 6. Cancel

`PATCH /api/appointments/{appointment_id}/cancel` (or `PATCH /api/bookings/{booking_id}/cancel`),
with no body. Rescheduling and cancelling are allowed until 30 minutes before the slot (home
collection: or until a phlebotomist is assigned, whichever is first). Booking-level calls can
succeed partially: `success` and `failed` in the response list appointment ids.

```python
def cancel(appointment_id: str) -> None:
    api("PATCH", f"/api/appointments/{appointment_id}/cancel")
```

### 7. Download the voucher

`GET /api/appointments/{appointment_id}/voucher` returns a PDF once the appointment is
`confirmed` (before that, `400 voucher only available for download when appointment is
confirmed`). `api()` returns the bytes:

```python
def download_voucher(appointment_id: str, path: str) -> None:
    pdf: bytes = api("GET", f"/api/appointments/{appointment_id}/voucher")
    with open(path, "wb") as f:
        f.write(pdf)
```

On staging, confirm an appointment yourself with the staging-only status endpoint, as the
example script does before downloading the voucher:

```python
def simulate_confirmation(appointment_id: str) -> None:
    """Staging only: confirm the appointment as the provider would."""
    api("POST", f"/api/appointments/{appointment_id}/update_status", json={"status": "confirm"})
```

After the visit, `GET /api/appointments/{appointment_id}/reports` and
`GET /api/appointments/{appointment_id}/lab_results` return the reports and structured
results.

## Consultations

An in-clinic doctor consultation: find a doctor, pick a slot, book. From
[`book_consultation.py`](../examples/api/book_consultation.py):

```python
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
```

Track it with `GET /api/consultations/inclinic_consultation/{appointment_id}`, reschedule
with `PATCH /api/consultations/{appointment_id}/reschedule`, cancel with
`PATCH /api/consultations/{appointment_id}/cancel`. Audio and video specialist consultations
(scheduled or priority) use `/api/consultations/specialist_consultation`. See the
[consultations guide](https://github.com/hlthstack/integration-guide/blob/main/docs/consultations.md).

## ePharmacy

Fill the member's cart, read the delivery options, place the order. From
[`pharmacy_order.py`](../examples/api/pharmacy_order.py), with
`CUSTOMER = {"api_customer_id": "CUST1001"}` and a medicine id from
`GET /api/epharmacy/medicines/search?name=...`:

```python
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
```

Query parameters on ePharmacy endpoints use bracketed names such as
`customer_details[api_customer_id]`. Prescription-only medicines (`rx_required: true`) need a
prescription on the cart (`prescription_urls`, or `prescription_files[]` uploaded as
multipart). `POST /api/epharmacy/orders/payment_details` quotes the amounts before you order.
In the partner-collected payment flow, confirm the payment with
`POST /api/epharmacy/orders/{order_id}/confirm`. See the
[ePharmacy guide](https://github.com/hlthstack/integration-guide/blob/main/docs/epharmacy.md).

## File uploads

Uploads are `multipart/form-data` with **bracketed form field names** exactly as the spec
defines them. Put the text fields in `data=` and the files in `files=`; repeat a key to send
several files. Prescription digitization (`POST /api/prescriptions/digitize`) takes exactly
one customer as `customers[][name]`, `customers[][api_customer_id]`,
`customers[][mobile_number]`, `customers[][gender]` and `customers[][dob]`, an optional
`plan_id`, and one or more `files[]` (JPEG, PNG or PDF, each up to 10 MB). From
[`upload_prescription.py`](../examples/api/upload_prescription.py):

```python
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
```

Send a unique `Idempotency-Key` per upload so a retry returns the original request instead of
creating a duplicate. `completed` and `partial` results carry the extracted `items` and a
ready `cart_id`.

Other uploads follow the same pattern: consultation documents
(`POST /api/consultations/{appointment_id}/upload_documents`, as `files[][name]` +
`files[][value]` pairs) and cart prescriptions (`PATCH /api/epharmacy/cart` with
`customer_details[api_customer_id]` and `prescription_files[]`, each under 7 MB).

## Pre-registration

Pre-registration registers, updates and deactivates members and their dependants in bulk. It
has **its own credentials** (an account email and password, separate from the booking API's)
and its own token:

1. `GET /api/pre_registration/access-token` with HTTP Basic auth (the account email as the
   username) returns
   `{"access_token": "YOUR_PRE_REGISTRATION_TOKEN", "expires_at": "2026-01-15 07:16:21 UTC"}`.
   The token lasts one hour. `expires_at` is UTC but formatted `YYYY-MM-DD HH:MM:SS UTC`,
   not ISO 8601 (`_parse_expires_at` above handles both).
2. Send the token **without a `Bearer` prefix** in the `X-EKINCARE-KEY` header. The
   `API-ENTITY-ID` / `API-SECRET-KEY` headers are not used; each row names its company with
   `company_id`.

A missing, invalid or expired token returns `401` with an empty body, as does any token once
your company's contract has ended; `403` with an empty body means the account's role may not
use this API. In `client.py` the same `AccessToken` class handles this token:

```python
pre_registration_token = AccessToken(
    "/api/pre_registration/access-token",
    os.environ.get("HLTHSTACK_PREREG_USERNAME", ""),
    os.environ.get("HLTHSTACK_PREREG_PASSWORD", ""),
)


def pre_registration_api(method: str, path: str, **kwargs: Any) -> Any:
    """Call a pre-registration endpoint: the raw token in ``X-EKINCARE-KEY``, no Bearer."""
    return _send(
        lambda value: {"X-EKINCARE-KEY": value},
        pre_registration_token,
        method,
        path,
        **kwargs,
    )
```

Each write takes at most **250 rows** (`employees` and `dependants` together) and returns a
`request_id`; poll `GET /v1/corporate/pre_registrations/{request_id}/status` until `status`
is `completed`, then read `success_records` and `failure_records`. On create, **every
required key must be present in every row**, even when empty: a row missing one is dropped
silently. From [`pre_registration.py`](../examples/api/pre_registration.py):

```python
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


request_id = submit("/v1/corporate/pre_registrations", {"employees": [EMPLOYEE]})
status = wait_for(request_id)
for record in status["failure_records"]:
    print("failed:", record.get("email"), record["errors"])

update = {"employees": [{"email": "jane.doe@example.com", "grade": "C"}]}
wait_for(submit("/v1/corporate/pre_registrations/update", update))

deactivate = {"employees": ["jane.doe@example.com"]}  # emails; dependants by mobile
wait_for(submit("/v1/corporate/pre_registrations/deactivate", deactivate))
```

Field rules, dependants, voluntary plans and row errors are in the
[pre-registration guide](https://github.com/hlthstack/integration-guide/blob/main/docs/pre-registration.md).

## Errors

Check the HTTP status first, then read the body defensively: error bodies are not uniform
across endpoints.

| Shape | Example | Where |
|---|---|---|
| Field errors | `{"errors": {"package_ids": ["should be an integer array"]}}` | Validation (usually 400). Nested fields are prefixed: `customer_mobile_number`, `address_pincode` |
| Messages | `{"errors": {"messages": ["This booking cannot be rescheduled"]}}` | Business-rule failures (400/422) and unexpected errors (422) |
| Plain message | `{"message": "Required details are missing"}` | Auth, entity headers, slots |
| Bare list | `{"errors": ["Invalid status"]}` | Staging simulation endpoints |
| Success flag | `{"success": false, "message": "Order not found"}` | ePharmacy |
| Booking failure | `{"msg": "...", "recall": false}` | Booking could not be placed |
| Single error | `{"error": "Invalid company slug for authenticated partner."}` | Wallet endpoints |
| Plain text | `HTTP Token: Access denied.` | 401 for a missing, invalid or expired bearer token |
| Empty body | | Pre-registration 401 and 403 |

`APIError` keeps the status and parsed body, and collects the readable messages from any of
these shapes:

```python
class APIError(Exception):
    """A non-2xx response. ``body`` is the parsed JSON, or the text."""

    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        self.messages = error_messages(body)
        super().__init__(f"HTTP {status_code}: {'; '.join(self.messages) or body!r}")


def error_messages(body: Any) -> list[str]:
    """Pull the human-readable messages out of any of the API's error shapes."""
    if isinstance(body, str):
        return [body] if body.strip() else []
    if not isinstance(body, dict):
        return []
    messages: list[str] = []
    errors = body.get("errors")
    if isinstance(errors, list):  # {"errors": ["..."]}
        messages += [str(error) for error in errors]
    elif isinstance(errors, dict):  # {"errors": {"messages": [...]}} / {"errors": {"field": [...]}}
        for field, value in errors.items():
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, bool):  # {"errors": {"msg": "...", "recall": false}}
                    continue
                generic = field in ("messages", "base", "msg")
                messages.append(str(item) if generic else f"{field}: {item}")
    for key in ("message", "msg", "error"):  # {"message": ...}, {"msg": ...}, {"error": ...}
        if isinstance(body.get(key), str):
            messages.append(body[key])
    return messages
```

```python
try:
    reschedule("APT1A2B3C4D5", "2030-01-16T02:30:00Z")
except APIError as e:
    print(e.status_code, e.messages, e.body)
except requests.RequestException as e:  # connection error or timeout: no response
    print("network error:", e)
```

| Status | Meaning |
|---|---|
| 400 | Invalid parameters, invalid plan or subscription, bad entity headers, entity not enabled for API booking, or an action not allowed in the current state |
| 401 | Missing, invalid or expired token (the helper already retried once with a new token) |
| 403 | The booking or appointment isn't yours, or the service isn't enabled on your plan |
| 404 | Member, cart or order not found; a staging-only endpoint called in production |
| 409 | Concurrent partner-payment confirmation |
| 422 | Business rule or processing failure, or an unexpected error |
| 5xx | Server error, or a provider's system couldn't be reached |

Retrying:

- Retry 5xx, 409 and network errors with backoff. Don't retry other 4xx responses unchanged:
  fix the request.
- **Don't blindly retry booking creation** (`POST /api/appointments` or a consultation
  create). A timeout doesn't mean the booking failed: check `GET /api/appointments` or your
  webhooks first.
- Prescription digitization (with the same `Idempotency-Key`) and partner-payment
  confirmation are safe to retry.
- Some ePharmacy responses are HTTP 200 with `"success": false` nested inside (for example
  fulfillment options); check those flags.

See [errors](https://github.com/hlthstack/integration-guide/blob/main/docs/errors.md) for the
common messages and their fixes.

## Validating inputs yourself

The API reports invalid input as 400 or 422. To catch problems before you call it, check the
input rules yourself. The most important ones:

| Rule | Where |
|---|---|
| `pincode` is 6 digits (a booking address's pincode cannot start with 0) | Providers and slots queries, booking and consultation addresses, cart address |
| `pincode`, or both `latitude` and `longitude`, is required | `GET /api/providers`, in-clinic consultation providers |
| `api_customer_id` is alphanumeric (`^[a-zA-Z0-9]+$`) and unique within the request | Booking and consultation `customers[]`, prescription digitization |
| `gender` is `male`, `female` or `non-binary`, lowercase | Booking and consultation `customers[]`, prescription digitization (pre-registration uses `Male` / `Female` / `Non-binary`, any case) |
| `mobile_number` is 10 digits, no `+91` | Customers, cart `customer_details`, pre-registration rows |
| `package_ids` is a comma-separated list of ids in queries (`1001,1002`), an array in bodies | Providers, slots, bookings, consultations |
| `dob` is `YYYY-MM-DD` and at least one year ago; not in the future for digitization | Booking and consultation customers, prescription digitization |
| `appointment_date_time` is ISO 8601 UTC, a slot's `utc_slot_time` | Bookings, consultations, reschedules |
| A consultation's `appointment_date_time` is in the future | Consultation create and reschedule |
| `address` is required for `appointment_type: home_collection`; its text fields must not contain any other 6-digit pincode | `POST /api/appointments`, reschedule with an address |
| `address` (with `pincode`) is required | In-clinic consultations |
| At most 250 rows in `employees` + `dependants`; dates as `DD-MM-YYYY` or `DD/MM/YYYY` | Pre-registration |

The full list is in the
[OpenAPI spec](https://github.com/hlthstack/integration-guide/blob/main/openapi/openapi.yaml):
each request schema encodes the per-field checks (`required`, `enum`, `pattern`,
`minLength`, `maximum`, `minItems`, ...), and rules that span fields or depend on today's
date are listed on each operation under `x-hlthstack-rules` (kinds described in
`x-hlthstack-rule-kinds`). Checks that need stored data (plan benefits, wallet balances,
slot availability, provider capabilities) are made only by the server.

The SDK runs all of these checks automatically before sending a request and reports every
problem at once ([SDK validation](sdk-integration.md#validation)).

## Webhooks

hlthstack POSTs JSON to the URLs you register at onboarding. Every request carries a
`Signature` header: an HS256 JWT signed with your webhook secret. The JWT has no `exp` claim
and does **not** cover the body, so check all three:

1. The signature is valid for your secret (HS256 only).
2. The ids in the claims match the ids in the body: `order_id` and `webhook_type` (= the
   body's `type`) for pharmacy events, `request_id` for prescription digitization, otherwise
   `appointment_id` and `booking_id`.
3. The `timestamp` claim (Unix seconds) is within your tolerance window, 5 minutes here, to
   block replays.

[`webhook_receiver.py`](../examples/api/webhook_receiver.py) does this with the standard
library only (no JWT package), and Flask for the endpoint:

```python
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Optional

from flask import Flask, abort, request

TOLERANCE = 300  # seconds


class InvalidSignature(Exception):
    pass


def _b64decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def verify_signature(signature: Optional[str], body: dict[str, Any], secret: str) -> dict[str, Any]:
    """Check the JWT's signature, that its ids match the body, and that it is recent."""
    try:
        header_b64, claims_b64, signature_b64 = (signature or "").split(".")
        header = json.loads(_b64decode(header_b64))
        claims = json.loads(_b64decode(claims_b64))
        received = _b64decode(signature_b64)
    except ValueError as e:  # wrong segment count, bad base64 or bad JSON
        raise InvalidSignature("malformed signature") from e
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise InvalidSignature("algorithm must be HS256")
    expected = hmac.new(
        secret.encode(), f"{header_b64}.{claims_b64}".encode(), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(expected, received):
        raise InvalidSignature("bad signature")
    if not isinstance(claims, dict):
        raise InvalidSignature("claims must be an object")

    # The JWT has no exp claim: reject old (replayed) signatures with its timestamp.
    timestamp = claims.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise InvalidSignature("missing timestamp")
    if abs(time.time() - timestamp) > TOLERANCE:
        raise InvalidSignature("stale timestamp")

    # The JWT does not cover the body: the ids in the claims must match the body's.
    if "order_id" in claims:  # pharmacy
        ok = claims["order_id"] == body.get("order_id")
        ok = ok and claims.get("webhook_type") == body.get("type")
    elif "request_id" in claims:  # prescription digitization
        ok = claims["request_id"] == body.get("request_id")
    else:  # appointment, consultation, lab results
        ok = bool(claims.get("appointment_id"))
        ok = ok and claims.get("appointment_id") == body.get("appointment_id")
        ok = ok and claims.get("booking_id") == body.get("booking_id")
    if not ok:
        raise InvalidSignature("claims do not match the body")
    return claims


app = Flask(__name__)


@app.post("/hlthstack/webhooks")
def webhook() -> tuple[str, int]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400)
    try:
        verify_signature(
            request.headers.get("Signature"), body, os.environ["HLTHSTACK_WEBHOOK_SECRET"]
        )
    except InvalidSignature:
        abort(401)
    enqueue(body)  # acknowledge fast; process asynchronously and deduplicate
    return "", 200
```

- Reply 2xx quickly (the timeout is 30 seconds) and process asynchronously.
- Delivery is at-least-once and unordered: deduplicate, use the claims' `timestamp` (and
  `event_timestamp` on appointments) to drop older events, and treat
  `GET /api/appointments` / `GET /api/epharmacy/orders/{order_id}` as the source of truth.
- Failed deliveries are retried only on connection errors, timeouts and HTTP 408, 502, 503
  and 504. Other non-2xx responses (including 401 and 500) are not retried.

Payload shapes and the claims per event are in the
[webhooks guide](https://github.com/hlthstack/integration-guide/blob/main/docs/webhooks.md).

## Moving to the SDK

The SDK wraps everything above: token caching and refresh (including the pre-registration
token), entity headers, one method per endpoint, multipart uploads from paths or bytes, error
classes with the messages extracted, input validation and webhook verification.

```bash
pip install "git+https://github.com/hlthstack/python"
```

| Plain API | SDK |
|---|---|
| `api("GET", "/api/providers", params={...})` | `client.appointments.list_providers(...)` |
| `api("POST", "/api/appointments", json={...})` | `client.appointments.create(...)` |
| `api("PATCH", f"/api/appointments/{id}/reschedule", json={...})` | `client.appointments.reschedule(id, ...)` |
| `api("GET", f"/api/appointments/{id}/voucher")` | `client.appointments.get_voucher(id)` |
| `pre_registration_api("POST", "/v1/corporate/pre_registrations", json={...})` | `client.pre_registration.create(...)` |
| `APIError` | `hlthstack.HlthstackError` and its subclasses |
| `verify_signature(signature, body, secret)` | `hlthstack.webhooks.verify_signature(body, signature, secret)` |

Request and response fields keep their API names, so the dicts you build today carry over.
See the [SDK integration guide](sdk-integration.md).
