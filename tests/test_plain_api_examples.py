"""Run the plain-HTTP examples in examples/api against a local mock of the API."""

import base64
import datetime as dt
import email.policy
import hashlib
import hmac
import importlib
import json
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit

import pytest

from hlthstack.webhooks import verify_signature as sdk_verify_signature

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "api"
EXAMPLE_MODULES = (
    "client",
    "book_health_checkup",
    "book_consultation",
    "pharmacy_order",
    "upload_prescription",
    "pre_registration",
    "webhook_receiver",
)
USERNAME = "test-user"
PASSWORD = "test-password"
PREREG_USERNAME = "prereg@example.com"
PREREG_PASSWORD = "prereg-password"


def basic(username: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


# --------------------------------------------------------------------------- mock server


@dataclass
class Recorded:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]  # lower-case names
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)

    def form(self) -> list[tuple[str, Optional[str], bytes]]:
        """Multipart parts as (field name, filename, content)."""
        message = BytesParser(policy=email.policy.HTTP).parsebytes(
            b"Content-Type: " + self.headers["content-type"].encode() + b"\r\n\r\n" + self.body
        )
        parts = []
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            content = part.get_payload(decode=True)
            assert isinstance(name, str) and isinstance(content, bytes)
            parts.append((name, part.get_filename(), content))
        return parts


Reply = tuple[int, Any]  # (status, body): dict/list -> JSON, bytes -> PDF, str -> text


@dataclass
class MockAPI:
    url: str = ""
    requests: list[Recorded] = field(default_factory=list)
    replies: dict[tuple[str, str], list[Reply]] = field(default_factory=dict)
    token_lifetime: float = 3600
    tokens_issued: int = 0
    prereg_tokens_issued: int = 0

    def reply(self, method: str, path: str, *replies: Reply) -> None:
        self.replies.setdefault((method, path), []).extend(replies)

    def calls(self, path: Optional[str] = None) -> list[Recorded]:
        return [r for r in self.requests if path is None or r.path == path]

    def api_calls(self) -> list[Recorded]:
        token_paths = ("/api/get-access-token", "/api/pre_registration/access-token")
        return [r for r in self.requests if r.path not in token_paths]

    def respond(self, request: Recorded) -> Reply:
        queued = self.replies.get((request.method, request.path))
        if queued:
            return queued.pop(0)
        expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=self.token_lifetime)
        if request.path == "/api/get-access-token":
            if request.headers.get("authorization") != basic(USERNAME, PASSWORD):
                return 401, {"message": "Wrong credentials"}
            self.tokens_issued += 1
            iso = expires.strftime("%Y-%m-%dT%H:%M:%SZ")
            return 200, {"access_token": f"token-{self.tokens_issued}", "expires_at": iso}
        if request.path == "/api/pre_registration/access-token":
            if request.headers.get("authorization") != basic(PREREG_USERNAME, PREREG_PASSWORD):
                return 401, {"message": "Wrong credentials"}
            self.prereg_tokens_issued += 1
            utc = expires.strftime("%Y-%m-%d %H:%M:%S UTC")
            return 200, {"access_token": f"prereg-{self.prereg_tokens_issued}", "expires_at": utc}
        return 200, {"ok": True}


def make_handler(mock: MockAPI) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def handle_any(self) -> None:
            url = urlsplit(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            recorded = Recorded(
                method=self.command,
                path=url.path,
                query=parse_qs(url.query),
                headers={k.lower(): v for k, v in self.headers.items()},
                body=self.rfile.read(length),
            )
            mock.requests.append(recorded)
            status, body = mock.respond(recorded)
            if isinstance(body, bytes):
                payload, content_type = body, "application/pdf"
            elif isinstance(body, str):
                payload, content_type = body.encode(), "text/plain"
            else:
                payload, content_type = json.dumps(body).encode(), "application/json"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PATCH = handle_any

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


@pytest.fixture(scope="module")
def server() -> Iterator[ThreadingHTTPServer]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MockAPI()))
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def mock(server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch) -> Iterator[MockAPI]:
    mock = MockAPI(url=f"http://127.0.0.1:{server.server_address[1]}")
    server.RequestHandlerClass = make_handler(mock)
    monkeypatch.setenv("HLTHSTACK_BASE_URL", mock.url)
    monkeypatch.setenv("HLTHSTACK_USERNAME", USERNAME)
    monkeypatch.setenv("HLTHSTACK_PASSWORD", PASSWORD)
    monkeypatch.setenv("HLTHSTACK_PREREG_USERNAME", PREREG_USERNAME)
    monkeypatch.setenv("HLTHSTACK_PREREG_PASSWORD", PREREG_PASSWORD)
    monkeypatch.delenv("HLTHSTACK_ENTITY_ID", raising=False)
    monkeypatch.delenv("HLTHSTACK_SECRET_KEY", raising=False)
    monkeypatch.syspath_prepend(str(EXAMPLES))
    yield mock
    for name in EXAMPLE_MODULES:  # the next test re-imports them with fresh config and tokens
        sys.modules.pop(name, None)


def load(name: str) -> ModuleType:
    """Import an example after the environment is set (they read it at import time)."""
    for module in EXAMPLE_MODULES:
        sys.modules.pop(module, None)
    return importlib.import_module(name)


def load_all(*names: str) -> list[ModuleType]:
    load("client")
    return [importlib.import_module(name) for name in names]


# --------------------------------------------------------------------------- auth helpers


def test_token_is_fetched_with_basic_auth_and_cached(mock: MockAPI) -> None:
    client = load("client")
    client.api("GET", "/api/providers", params={"service_name": "ahc"})
    client.api("GET", "/api/providers", params={"service_name": "dental"})

    [token_call] = mock.calls("/api/get-access-token")
    assert token_call.method == "GET"
    assert token_call.headers["authorization"] == basic(USERNAME, PASSWORD)
    first, second = mock.calls("/api/providers")
    assert first.headers["authorization"] == "Bearer token-1"
    assert second.headers["authorization"] == "Bearer token-1"
    assert first.query == {"service_name": ["ahc"]}
    assert "api-entity-id" not in first.headers
    assert "api-secret-key" not in first.headers


def test_token_is_refreshed_five_minutes_before_expiry(mock: MockAPI) -> None:
    mock.token_lifetime = 240  # already inside the 5-minute margin
    client = load("client")
    client.api("GET", "/api/providers")
    client.api("GET", "/api/providers")
    assert mock.tokens_issued == 2
    assert [c.headers["authorization"] for c in mock.calls("/api/providers")] == [
        "Bearer token-1",
        "Bearer token-2",
    ]


def test_401_refreshes_the_token_and_retries_once(mock: MockAPI) -> None:
    client = load("client")
    mock.reply("GET", "/api/appointments", (401, "HTTP Token: Access denied."))
    mock.reply("GET", "/api/appointments", (200, {"appointments": []}))
    assert client.api("GET", "/api/appointments", params={"booking_id": "B"}) == {
        "appointments": []
    }
    assert mock.tokens_issued == 2
    assert [c.headers["authorization"] for c in mock.calls("/api/appointments")] == [
        "Bearer token-1",
        "Bearer token-2",
    ]


def test_second_401_raises(mock: MockAPI) -> None:
    client = load("client")
    denied = (401, "HTTP Token: Access denied.")
    mock.reply("GET", "/api/appointments", denied, denied)
    with pytest.raises(client.APIError) as exc:
        client.api("GET", "/api/appointments")
    assert exc.value.status_code == 401
    assert exc.value.messages == ["HTTP Token: Access denied."]
    assert len(mock.calls("/api/appointments")) == 2


def test_wrong_credentials_raise(mock: MockAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HLTHSTACK_PASSWORD", "wrong")
    client = load("client")
    with pytest.raises(client.APIError) as exc:
        client.api("GET", "/api/providers")
    assert exc.value.status_code == 401
    assert exc.value.messages == ["Wrong credentials"]
    assert mock.calls("/api/providers") == []


@pytest.mark.parametrize(
    ("body", "messages"),
    [
        (
            {"errors": {"messages": ["This booking cannot be rescheduled"]}},
            ["This booking cannot be rescheduled"],
        ),
        (
            {"errors": {"package_ids": ["should be an integer array"]}},
            ["package_ids: should be an integer array"],
        ),
        ({"message": "Required details are missing"}, ["Required details are missing"]),
        ({"errors": ["Invalid status"]}, ["Invalid status"]),
        ({"success": False, "message": "Order not found"}, ["Order not found"]),
        ({"msg": "Booking failed", "recall": False}, ["Booking failed"]),
        ({"error": "Invalid company slug"}, ["Invalid company slug"]),
        (
            {"success": False, "errors": {"msg": "Pharmacy benefit not enabled", "recall": False}},
            ["Pharmacy benefit not enabled"],
        ),
        (
            {"status": "invalid_payment", "errors": {"base": ["Amount mismatch"]}},
            ["Amount mismatch"],
        ),
    ],
)
def test_error_shapes(mock: MockAPI, body: Any, messages: list[str]) -> None:
    client = load("client")
    mock.reply("POST", "/api/appointments", (422, body))
    with pytest.raises(client.APIError) as exc:
        client.api("POST", "/api/appointments", json={})
    assert exc.value.status_code == 422
    assert exc.value.body == body
    assert exc.value.messages == messages


def test_entity_headers(mock: MockAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HLTHSTACK_ENTITY_ID", "1001")
    monkeypatch.setenv("HLTHSTACK_SECRET_KEY", "entity-secret")
    client = load("client")
    client.api("GET", "/api/providers")
    client.api(
        "GET", "/api/providers", headers={"API-ENTITY-ID": "1002", "API-SECRET-KEY": "other"}
    )

    [token_call] = mock.calls("/api/get-access-token")
    assert "api-entity-id" not in token_call.headers  # never on the token request
    default, override = mock.calls("/api/providers")
    assert default.headers["api-entity-id"] == "1001"
    assert default.headers["api-secret-key"] == "entity-secret"
    assert override.headers["api-entity-id"] == "1002"
    assert override.headers["api-secret-key"] == "other"


# --------------------------------------------------------------------------- health checkups


def test_book_health_checkup(
    mock: MockAPI, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slot = {"available": True}
    mock.reply("GET", "/api/providers", (200, {"providers": [{"provider_id": 1001}]}))
    mock.reply(
        "GET",
        "/api/providers/1001/ahc/slots",
        (
            200,
            {
                "booking_slots": [
                    {
                        "date": "2030-01-15",
                        "slots": [
                            {
                                **slot,
                                "available": False,
                                "utc_slot_time": "2030-01-15T01:30:00.000Z",
                            },
                            {**slot, "utc_slot_time": "2030-01-15T02:30:00.000Z"},
                            {**slot, "utc_slot_time": "2030-01-15T03:30:00.000Z"},
                        ],
                    }
                ]
            },
        ),
    )
    mock.reply(
        "POST",
        "/api/appointments",
        (
            200,
            {
                "booking_id": "EKI0000000001700000000",
                "status": "confirmed",
                "customers": [{"appointment_id": "APT1A2B3C4D5"}],
            },
        ),
    )
    mock.reply(
        "GET",
        "/api/appointments",
        (200, {"appointments": [{"appointment_id": "APT1A2B3C4D5", "status": "new"}]}),
    )
    mock.reply("GET", "/api/appointments/APT1A2B3C4D5/voucher", (200, b"%PDF-1.4 voucher"))
    monkeypatch.chdir(tmp_path)

    [example] = load_all("book_health_checkup")
    example.main()

    calls = mock.api_calls()
    assert [(c.method, c.path) for c in calls] == [
        ("GET", "/api/providers"),
        ("GET", "/api/providers/1001/ahc/slots"),
        ("POST", "/api/appointments"),
        ("GET", "/api/appointments"),
        ("PATCH", "/api/appointments/APT1A2B3C4D5/reschedule"),
        ("POST", "/api/appointments/APT1A2B3C4D5/update_status"),
        ("GET", "/api/appointments/APT1A2B3C4D5/voucher"),
        ("PATCH", "/api/appointments/APT1A2B3C4D5/cancel"),
    ]
    providers, slots, create, details, reschedule, confirm, _, _ = calls
    assert providers.query == {
        "service_name": ["ahc"],
        "package_ids": ["1001"],
        "pincode": ["500081"],
    }
    assert slots.query == {"package_ids": ["1001"], "pincode": ["500081"]}
    assert create.headers["content-type"] == "application/json"
    assert create.json() == {
        "service_name": "ahc",
        "appointment_type": "inclinic",
        "provider_id": 1001,
        "appointment_date_time": "2030-01-15T02:30:00.000Z",
        "customers": [
            {
                "name": "Jane Doe",
                "dob": "1990-08-24",
                "gender": "female",
                "mobile_number": "9999999999",
                "api_customer_id": "CUST1001",
                "package_ids": [1001],
            }
        ],
    }
    assert details.query == {"booking_id": ["EKI0000000001700000000"]}
    assert reschedule.json() == {"appointment_date_time": "2030-01-15T03:30:00.000Z"}
    assert confirm.json() == {"status": "confirm"}
    assert all(c.headers["authorization"] == "Bearer token-1" for c in calls)
    assert (tmp_path / "voucher.pdf").read_bytes() == b"%PDF-1.4 voucher"


def test_consultation_and_pharmacy(mock: MockAPI) -> None:
    mock.reply(
        "GET",
        "/api/consultations/inclinic_consultation/providers",
        (200, {"providers": [{"provider_id": 2001}]}),
    )
    mock.reply(
        "GET",
        "/api/providers/2001/inclinic_consultation/slots",
        (
            200,
            {
                "booking_slots": [
                    {"slots": [{"available": True, "utc_slot_time": "2030-01-15T04:30:00.000Z"}]}
                ]
            },
        ),
    )
    mock.reply(
        "POST",
        "/api/consultations/inclinic_consultation",
        (200, {"booking_id": "EKI0000000001700000000", "customers": [{"appointment_id": "A"}]}),
    )
    mock.reply("PATCH", "/api/epharmacy/cart", (200, {"success": True, "cart": {"id": 701}}))
    mock.reply(
        "GET",
        "/api/epharmacy/fulfillment_options",
        (
            200,
            {
                "success": True,
                "delivery_options": {"success": True, "standard": {"location_token": "TOKEN"}},
            },
        ),
    )
    mock.reply("POST", "/api/epharmacy/orders", (200, {"status": "confirmed"}))
    consultation, pharmacy = load_all("book_consultation", "pharmacy_order")

    consultation.book_inclinic_consultation()
    pharmacy.place_order(50001)

    providers = mock.calls("/api/consultations/inclinic_consultation/providers")[0]
    assert providers.query == {
        "package_ids": ["2001"],
        "pincode": ["500084"],
        "sort_by": ["distance"],
    }
    book = mock.calls("/api/consultations/inclinic_consultation")[0].json()
    assert book["provider_id"] == 2001
    assert book["appointment_date_time"] == "2030-01-15T04:30:00.000Z"
    assert book["service_mode"] == "at_provider_location"
    assert book["address"]["pincode"] == "500084"
    assert book["customers"][0]["package_ids"] == [2001]

    cart = mock.calls("/api/epharmacy/cart")[0]
    assert cart.method == "PATCH"
    assert cart.json()["customer_details"] == {"api_customer_id": "CUST1001"}
    assert cart.json()["products"] == [{"id": 50001, "quantity": 1}]
    options = mock.calls("/api/epharmacy/fulfillment_options")[0]
    assert options.query == {"customer_details[api_customer_id]": ["CUST1001"], "cart_id": ["701"]}
    assert mock.calls("/api/epharmacy/orders")[0].json() == {
        "customer_details": {"api_customer_id": "CUST1001"},
        "cart_id": 701,
        "delivery_option": "standard",
        "location_token": "TOKEN",
    }


# --------------------------------------------------------------------------- uploads


def test_upload_prescription(
    mock: MockAPI, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prescription = tmp_path / "rx.pdf"
    prescription.write_bytes(b"%PDF-1.4 rx")
    mock.reply(
        "POST",
        "/api/prescriptions/digitize",
        (401, "HTTP Token: Access denied."),  # the file must be resent after the refresh
        (202, {"request_id": "DIGI_RQ_A1B2C3D4E", "status": "pending"}),
    )
    mock.reply(
        "GET",
        "/api/prescriptions/digitize/DIGI_RQ_A1B2C3D4E",
        (200, {"status": "ai_processing"}),
        (200, {"status": "completed", "cart_id": 701, "items": []}),
    )
    [example] = load_all("upload_prescription")
    monkeypatch.setattr(example.time, "sleep", lambda seconds: None)

    accepted = example.digitize_prescription(str(prescription), idempotency_key="upload-0001")
    result = example.wait_for_digitization(accepted["request_id"])

    assert result["cart_id"] == 701
    first, upload = mock.calls("/api/prescriptions/digitize")
    assert upload.headers["authorization"] == "Bearer token-2"
    assert upload.headers["idempotency-key"] == "upload-0001"
    assert upload.headers["content-type"].startswith("multipart/form-data; boundary=")
    expected = [
        ("customers[][name]", None, b"Jane Doe"),
        ("customers[][api_customer_id]", None, b"CUST1001"),
        ("customers[][mobile_number]", None, b"9999999999"),
        ("customers[][gender]", None, b"female"),
        ("customers[][dob]", None, b"1990-08-24"),
        ("files[]", "rx.pdf", b"%PDF-1.4 rx"),
    ]
    assert upload.form() == expected
    assert first.form() == expected
    assert len(mock.calls("/api/prescriptions/digitize/DIGI_RQ_A1B2C3D4E")) == 2


# --------------------------------------------------------------------------- pre-registration


def test_pre_registration(mock: MockAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    request_ids = iter(["11111111-0000-4000-8000-000000000001", "2", "3"])
    for path in ("", "/update", "/deactivate"):
        mock.reply(
            "POST",
            f"/v1/corporate/pre_registrations{path}",
            (200, {"message": "Request has been accepted", "request_id": next(request_ids)}),
        )
    mock.reply(
        "GET",
        "/v1/corporate/pre_registrations/11111111-0000-4000-8000-000000000001/status",
        (200, {"status": "inprogress"}),
        (200, {"status": "completed", "success_records": [], "failure_records": []}),
    )
    for request_id in ("2", "3"):
        mock.reply(
            "GET",
            f"/v1/corporate/pre_registrations/{request_id}/status",
            (200, {"status": "completed", "success_records": [], "failure_records": []}),
        )
    [example] = load_all("pre_registration")
    monkeypatch.setattr(example.time, "sleep", lambda seconds: None)

    example.main()

    [token_call] = mock.calls("/api/pre_registration/access-token")
    assert token_call.headers["authorization"] == basic(PREREG_USERNAME, PREREG_PASSWORD)
    assert mock.calls("/api/get-access-token") == []
    calls = mock.api_calls()
    for call in calls:
        assert call.headers["x-ekincare-key"] == "prereg-1"  # raw token, cached
        assert "authorization" not in call.headers
        assert "api-entity-id" not in call.headers
    create = mock.calls("/v1/corporate/pre_registrations")[0].json()
    assert create == {"employees": [example.EMPLOYEE]}
    assert mock.calls("/v1/corporate/pre_registrations/update")[0].json() == {
        "employees": [{"email": "jane.doe@example.com", "grade": "C"}]
    }
    assert mock.calls("/v1/corporate/pre_registrations/deactivate")[0].json() == {
        "employees": ["jane.doe@example.com"]
    }


def test_pre_registration_token_expiry_format(mock: MockAPI) -> None:
    mock.token_lifetime = 240  # inside the refresh margin: "YYYY-MM-DD HH:MM:SS UTC" parsed
    client = load("client")
    client.pre_registration_api("GET", "/v1/corporate/pre_registrations/1/status")
    client.pre_registration_api("GET", "/v1/corporate/pre_registrations/1/status")
    assert mock.prereg_tokens_issued == 2


def test_pre_registration_row_limit(mock: MockAPI) -> None:
    [example] = load_all("pre_registration")
    with pytest.raises(ValueError, match="at most 250 rows"):
        example.submit(
            "/v1/corporate/pre_registrations",
            {"employees": [example.EMPLOYEE] * 200, "dependants": [{}] * 51},
        )
    assert mock.requests == []


# --------------------------------------------------------------------------- webhooks

SECRET = "test-webhook-secret"
APPOINTMENT = {
    "type": "status_update",
    "appointment_id": "APT1A2B3C4D5",
    "booking_id": "EKI0000000001700000000",
    "status": "confirmed",
}
ORDER = {"type": "status_update", "order_id": "EPO000000000001", "service_type": "pharmacy"}
DIGITIZATION = {"type": "digitization_results", "request_id": "DIGI_RQ_A1B2C3D4E"}


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign(claims: dict[str, Any], secret: str = SECRET, alg: str = "HS256") -> str:
    header = b64url(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    payload = b64url(json.dumps(claims).encode())
    signature = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256)
    return f"{header}.{payload}.{b64url(signature.digest())}"


def appointment_claims(**overrides: Any) -> dict[str, Any]:
    return {
        "appointment_id": APPOINTMENT["appointment_id"],
        "booking_id": APPOINTMENT["booking_id"],
        "timestamp": int(time.time()),
        "webhook_type": "status_update",
        **overrides,
    }


@pytest.mark.parametrize(
    ("body", "claims"),
    [
        (APPOINTMENT, appointment_claims()),
        (ORDER, {"order_id": ORDER["order_id"], "webhook_type": "status_update"}),
        (DIGITIZATION, {"request_id": DIGITIZATION["request_id"]}),
    ],
)
def test_webhook_accepts_valid_signature(
    mock: MockAPI, body: dict[str, Any], claims: dict[str, Any]
) -> None:
    [receiver] = load_all("webhook_receiver")
    signature = sign({**claims, "timestamp": int(time.time())})
    assert receiver.verify_signature(signature, body, SECRET)["timestamp"] > 0
    # The SDK's verifier accepts the same token: the test signer produces a real JWT.
    sdk_verify_signature(body, signature, SECRET)


@pytest.mark.parametrize(
    ("signature", "body"),
    [
        (None, APPOINTMENT),
        ("not-a-jwt", APPOINTMENT),
        ("a.b.c", APPOINTMENT),
        (sign(appointment_claims(), secret="wrong-secret"), APPOINTMENT),
        (sign(appointment_claims(), alg="HS512"), APPOINTMENT),
        (sign(appointment_claims())[:-2] + "AA", APPOINTMENT),  # tampered signature
        (sign(appointment_claims(timestamp=int(time.time()) - 600)), APPOINTMENT),  # stale
        (sign(appointment_claims(timestamp=int(time.time()) + 600)), APPOINTMENT),  # future
        (sign(appointment_claims(timestamp="now")), APPOINTMENT),
        (sign({k: v for k, v in appointment_claims().items() if k != "timestamp"}), APPOINTMENT),
        (sign(appointment_claims(appointment_id="APT000000000")), APPOINTMENT),
        (sign(appointment_claims(booking_id="EKI0000000000000000000")), APPOINTMENT),
        (sign({"timestamp": int(time.time())}), {}),  # no ids at all
        (
            sign({"order_id": "EPO000000000002", "timestamp": int(time.time())}),
            ORDER,
        ),
        (
            sign(
                {
                    "order_id": ORDER["order_id"],
                    "webhook_type": "post_billing",
                    "timestamp": int(time.time()),
                }
            ),
            ORDER,
        ),
        (sign({"request_id": "DIGI_RQ_OTHER", "timestamp": int(time.time())}), DIGITIZATION),
    ],
)
def test_webhook_rejects_invalid_signature(
    mock: MockAPI, signature: Optional[str], body: dict[str, Any]
) -> None:
    [receiver] = load_all("webhook_receiver")
    with pytest.raises(receiver.InvalidSignature):
        receiver.verify_signature(signature, body, SECRET)


def test_webhook_tampered_body(mock: MockAPI) -> None:
    [receiver] = load_all("webhook_receiver")
    signature = sign(appointment_claims())
    with pytest.raises(receiver.InvalidSignature):
        receiver.verify_signature(signature, {**APPOINTMENT, "booking_id": "EKI_OTHER"}, SECRET)


def test_webhook_flask_route(mock: MockAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HLTHSTACK_WEBHOOK_SECRET", SECRET)
    [receiver] = load_all("webhook_receiver")
    received: list[dict[str, Any]] = []
    monkeypatch.setattr(receiver, "enqueue", received.append)
    http = receiver.app.test_client()

    ok = http.post(
        "/hlthstack/webhooks", json=APPOINTMENT, headers={"Signature": sign(appointment_claims())}
    )
    stale = http.post(
        "/hlthstack/webhooks",
        json=APPOINTMENT,
        headers={"Signature": sign(appointment_claims(timestamp=int(time.time()) - 600))},
    )
    unsigned = http.post("/hlthstack/webhooks", json=APPOINTMENT)

    assert (ok.status_code, stale.status_code, unsigned.status_code) == (200, 401, 401)
    assert received == [APPOINTMENT]
