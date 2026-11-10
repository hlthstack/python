import base64
import hashlib
import hmac
import json
import time
from typing import Any

import pytest

from hlthstack.webhooks import WebhookVerificationError, verify_signature

SECRET = "test-webhook-secret"
NOW = 1_768_440_000.0


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_jwt(claims: dict[str, Any], secret: str = SECRET, alg: str = "HS256") -> str:
    header = b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    payload = b64(json.dumps(claims).encode())
    signature = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{b64(signature)}"


APPOINTMENT_BODY = {
    "type": "status_update",
    "booking_id": "EKI0000000001700000000",
    "appointment_id": "APT1A2B3C4D5",
    "status": "confirmed",
}
APPOINTMENT_CLAIMS = {
    "appointment_id": "APT1A2B3C4D5",
    "booking_id": "EKI0000000001700000000",
    "timestamp": int(NOW),
    "webhook_type": "status_update",
}


def test_valid_appointment_webhook_raw_body() -> None:
    raw = json.dumps(APPOINTMENT_BODY).encode()
    claims = verify_signature(raw, make_jwt(APPOINTMENT_CLAIMS), SECRET, now=NOW + 10)
    assert claims["appointment_id"] == "APT1A2B3C4D5"


def test_valid_with_parsed_body_str_and_bytes_secret() -> None:
    signature = make_jwt(APPOINTMENT_CLAIMS)
    verify_signature(APPOINTMENT_BODY, signature, SECRET.encode(), now=NOW)
    verify_signature(json.dumps(APPOINTMENT_BODY), signature, SECRET, now=NOW)


def test_reports_upload_type_does_not_need_to_match_webhook_type() -> None:
    body = {**APPOINTMENT_BODY, "type": "reports_upload"}
    verify_signature(body, make_jwt(APPOINTMENT_CLAIMS), SECRET, now=NOW)


def test_uses_current_time_by_default() -> None:
    claims = {**APPOINTMENT_CLAIMS, "timestamp": int(time.time())}
    verify_signature(APPOINTMENT_BODY, make_jwt(claims), SECRET)


def test_pharmacy_webhook() -> None:
    body = {"type": "post_billing", "order_id": "EPO000000000003", "service_type": "pharmacy"}
    claims = {"order_id": "EPO000000000003", "timestamp": NOW, "webhook_type": "post_billing"}
    verify_signature(body, make_jwt(claims), SECRET, now=NOW)
    wrong_type = {**claims, "webhook_type": "status_update"}
    with pytest.raises(WebhookVerificationError, match="match"):
        verify_signature(body, make_jwt(wrong_type), SECRET, now=NOW)


def test_digitization_webhook() -> None:
    body = {"type": "digitization_results", "request_id": "DIGI_RQ_A1B2C3D4E"}
    claims = {
        "request_id": "DIGI_RQ_A1B2C3D4E",
        "timestamp": NOW,
        "webhook_type": "digitization_results",
    }
    verify_signature(body, make_jwt(claims), SECRET, now=NOW)
    with pytest.raises(WebhookVerificationError):
        verify_signature({**body, "request_id": "OTHER"}, make_jwt(claims), SECRET, now=NOW)


@pytest.mark.parametrize(
    ("signature", "body", "now", "match"),
    [
        (None, APPOINTMENT_BODY, NOW, "Missing"),
        ("not-a-jwt", APPOINTMENT_BODY, NOW, "valid JWT"),
        ("a.b.c", APPOINTMENT_BODY, NOW, "valid JWT"),
        (make_jwt(APPOINTMENT_CLAIMS, secret="other-secret"), APPOINTMENT_BODY, NOW, "invalid"),
        (make_jwt(APPOINTMENT_CLAIMS, alg="HS512"), APPOINTMENT_BODY, NOW, "HS256"),
        (make_jwt(APPOINTMENT_CLAIMS, alg="none"), APPOINTMENT_BODY, NOW, "HS256"),
        (make_jwt(APPOINTMENT_CLAIMS), APPOINTMENT_BODY, NOW + 301, "tolerance"),
        (make_jwt(APPOINTMENT_CLAIMS), APPOINTMENT_BODY, NOW - 301, "tolerance"),
        (
            make_jwt({k: v for k, v in APPOINTMENT_CLAIMS.items() if k != "timestamp"}),
            APPOINTMENT_BODY,
            NOW,
            "timestamp",
        ),
        (
            make_jwt(APPOINTMENT_CLAIMS),
            {**APPOINTMENT_BODY, "appointment_id": "APT0THER"},
            NOW,
            "match",
        ),
        (
            make_jwt(APPOINTMENT_CLAIMS),
            {**APPOINTMENT_BODY, "booking_id": "EKI0THER"},
            NOW,
            "match",
        ),
        (make_jwt({"timestamp": NOW}), APPOINTMENT_BODY, NOW, "match"),
        (make_jwt(APPOINTMENT_CLAIMS), b"not json", NOW, "JSON"),
        (make_jwt(APPOINTMENT_CLAIMS), b"[]", NOW, "JSON object"),
    ],
)
def test_rejections(signature: Any, body: Any, now: float, match: str) -> None:
    with pytest.raises(WebhookVerificationError, match=match):
        verify_signature(body, signature, SECRET, now=now)


def test_tampered_claims_rejected() -> None:
    header, _, signature = make_jwt(APPOINTMENT_CLAIMS).split(".")
    forged = b64(json.dumps({**APPOINTMENT_CLAIMS, "appointment_id": "APT0THER"}).encode())
    with pytest.raises(WebhookVerificationError, match="invalid"):
        verify_signature(
            {**APPOINTMENT_BODY, "appointment_id": "APT0THER"},
            f"{header}.{forged}.{signature}",
            SECRET,
            now=NOW,
        )


def test_custom_tolerance() -> None:
    signature = make_jwt(APPOINTMENT_CLAIMS)
    verify_signature(APPOINTMENT_BODY, signature, SECRET, now=NOW + 500, tolerance=600)
    with pytest.raises(WebhookVerificationError):
        verify_signature(APPOINTMENT_BODY, signature, SECRET, now=NOW + 61, tolerance=60)
