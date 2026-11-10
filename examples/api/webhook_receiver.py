"""Receive hlthstack webhooks with Flask and verify their Signature header.

    HLTHSTACK_WEBHOOK_SECRET=... flask --app examples/api/webhook_receiver.py run

The signature is an HS256 JWT, verified here with the standard library only.
"""

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


def enqueue(event: dict[str, Any]) -> None:
    print("received", event.get("type"), event.get("appointment_id") or event.get("order_id"))


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
