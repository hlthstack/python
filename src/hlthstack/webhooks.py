"""Verify and type hlthstack webhooks.

hlthstack POSTs JSON to the URLs you register, with a ``Signature`` header holding an HS256
JWT signed with your webhook secret. The JWT does not cover the body, so
:func:`verify_signature` checks the signature, that the ids in the claims match the body,
and that the ``timestamp`` claim is recent. See
https://github.com/hlthstack/integration-guide/blob/main/docs/webhooks.md.
"""

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from typing import Any, Literal, Optional, TypedDict, Union, cast

from ._exceptions import WebhookVerificationError
from .types import (
    AppointmentDetails,
    LabResults,
    OrderItem,
    SplitDetails,
)

__all__ = [
    "AppointmentStatusUpdateWebhook",
    "ConsultationStatusUpdateWebhook",
    "LabResultsWebhook",
    "PharmacyAdditionalPaymentRequiredWebhook",
    "PharmacyOrderStatusUpdateWebhook",
    "PharmacyPostBillingWebhook",
    "PrescriptionDigitizedWebhook",
    "WebhookClaims",
    "WebhookPayload",
    "WebhookVerificationError",
    "verify_signature",
]

DEFAULT_TOLERANCE = 300

# --------------------------------------------------------------------------- payloads

AppointmentStatusUpdateWebhook = AppointmentDetails
"""``status_update`` / ``reports_upload`` for health checkups and lab tests."""

ConsultationStatusUpdateWebhook = AppointmentDetails
"""``status_update`` / ``reports_upload`` for consultations (same shape as appointments)."""

LabResultsWebhook = LabResults
"""``lab_results``: digitized lab results (sent only if you registered a lab-results URL)."""


class ShipmentDetails(TypedDict, total=False):
    delivery_type: Optional[Literal["store_pickup", "express", "standard"]]
    otp: Optional[str]
    tracking_partner: Optional[str]
    tracking_number: Optional[str]
    tracking_url: Optional[str]
    eta_from: Optional[str]
    eta_to: Optional[str]
    store_details: Optional[dict[str, Any]]


class PharmacyPayment(TypedDict, total=False):
    status: str
    razorpay_amount: float
    razorpay_payment_id: Optional[str]
    razorpay_order_id: Optional[str]
    sponsor_wallet_amount: float
    customer_wallet_amount: float
    promotional_wallet_amount: float
    h_points_amount: float
    refunded_amount: float
    total_collected_amount: float
    captured_at: Optional[str]
    refunded_at: Optional[str]
    partner_collected: bool
    partner_collected_amount: float
    additional_collected_amount: float
    partner_payment_reference: Optional[str]


class _PharmacyWebhookBase(TypedDict, total=False):
    order_id: str
    customer_id: str
    api_customer_id: Optional[str]
    member_id: Optional[str]
    ordered_for_name: Optional[str]
    mobile_number: Optional[str]
    order_type: Optional[str]
    vendor_name: Optional[str]
    service_type: Literal["pharmacy"]
    plan_id: Optional[str]
    customer_plan_id: Optional[int]
    subscription_id: Optional[str]
    status: str
    status_text: Optional[str]
    status_description: Optional[str]
    partner_status: Optional[str]
    order_items: list[OrderItem]
    total_amount: float
    total_selling_price: float
    total_discount: float
    sub_total: float
    additional_charge: float
    total_payable: float
    tracking_url: Optional[str]
    tracking_partner: Optional[str]
    tracking_number: Optional[str]
    eta_from: Optional[str]
    eta_to: Optional[str]
    shipment_details: ShipmentDetails
    address: str
    city: str
    pincode: str
    state: str
    split_details: SplitDetails
    payment: PharmacyPayment


class PharmacyOrderStatusUpdateWebhook(_PharmacyWebhookBase, total=False):
    """``status_update`` for a pharmacy order (every status change, including refunds)."""

    type: Literal["status_update"]


class AdditionalPayment(TypedDict, total=False):
    order_id: str
    amount_payable: float
    partner_collected_amount: float
    additional_collected_amount: float
    signalled_at: str


class PharmacyAdditionalPaymentRequiredWebhook(_PharmacyWebhookBase, total=False):
    """``additional_payment_required``: collect ``additional_payment.amount_payable``."""

    type: Literal["additional_payment_required"]
    additional_payment: AdditionalPayment


class SettlementOrder(TypedDict, total=False):
    order_id: str
    status: str
    selling_price: float


class Settlement(TypedDict, total=False):
    original_collected_amount: float
    additional_collected_amount: float
    total_collected_amount: float
    final_amount: float
    adjustment_amount: float
    settled_at: str
    orders: list[SettlementOrder]


class PharmacyPostBillingWebhook(_PharmacyWebhookBase, total=False):
    """``post_billing``: refund ``settlement.adjustment_amount`` to the member."""

    type: Literal["post_billing"]
    settlement: Settlement


class DigitizedDocument(TypedDict, total=False):
    id: int
    url: str
    type: Literal["pdf", "image"]
    name: str


class PrescriptionDigitizedWebhook(TypedDict, total=False):
    """``digitization_results``: a prescription digitization request finished."""

    type: Literal["digitization_results"]
    event_type: Literal["pharmacy.prescription.digitized"]
    request_id: str
    status: Literal["completed", "partial", "rejected", "failed"]
    customer_id: str
    api_customer_id: Optional[str]
    member_id: Optional[str]
    plan_id: Optional[str]
    items: Optional[list[dict[str, Any]]]
    reviewed_items: Optional[list[dict[str, Any]]]
    cart_id: Optional[int]
    documents: list[DigitizedDocument]
    comment: Optional[str]


WebhookPayload = Union[
    AppointmentDetails,
    LabResults,
    PharmacyOrderStatusUpdateWebhook,
    PharmacyAdditionalPaymentRequiredWebhook,
    PharmacyPostBillingWebhook,
    PrescriptionDigitizedWebhook,
]


class WebhookClaims(TypedDict, total=False):
    """Claims of the ``Signature`` JWT. Which ids are present depends on the event."""

    appointment_id: str
    booking_id: str
    order_id: str
    request_id: str
    timestamp: float
    webhook_type: str


# --------------------------------------------------------------------------- verification


def verify_signature(
    body: Union[bytes, str, Mapping[str, Any]],
    signature: Optional[str],
    secret: Union[str, bytes],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    now: Optional[float] = None,
) -> WebhookClaims:
    """Verify a webhook and return its JWT claims.

    Checks, as described in the webhooks guide:

    1. ``signature`` (the ``Signature`` header) is an HS256 JWT valid for ``secret``;
    2. the ids in the claims match the body (``order_id`` and ``webhook_type`` == ``type``
       for pharmacy events, ``request_id`` for digitization results, otherwise
       ``appointment_id`` and ``booking_id``);
    3. the ``timestamp`` claim is within ``tolerance`` seconds (default 300) of ``now``.

    Args:
        body: The request body: raw bytes/str, or the already-parsed JSON object.
        signature: The value of the ``Signature`` header.
        secret: Your webhook signing secret for this environment.
        tolerance: Maximum age (and clock skew) in seconds.
        now: Current Unix time; defaults to ``time.time()``.

    Raises:
        WebhookVerificationError: if any check fails.
    """
    if not signature:
        raise WebhookVerificationError("Missing Signature header")
    claims = _decode_hs256(signature, secret)

    payload: Any = body
    if isinstance(body, (bytes, str)):
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise WebhookVerificationError("Body is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise WebhookVerificationError("Body is not a JSON object")

    timestamp = claims.get("timestamp")
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
        raise WebhookVerificationError("Signature has no numeric timestamp claim")
    current = time.time() if now is None else now
    if abs(current - timestamp) > tolerance:
        raise WebhookVerificationError("Signature timestamp is outside the tolerance window")

    if "order_id" in claims:
        ok = claims["order_id"] == payload.get("order_id") and claims.get(
            "webhook_type"
        ) == payload.get("type")
    elif "request_id" in claims:
        ok = claims["request_id"] == payload.get("request_id")
    else:
        ok = (
            "appointment_id" in claims
            and claims["appointment_id"] == payload.get("appointment_id")
            and claims.get("booking_id") == payload.get("booking_id")
        )
    if not ok:
        raise WebhookVerificationError("Signature claims do not match the body")
    return cast(WebhookClaims, claims)


def _b64decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _decode_hs256(token: str, secret: Union[str, bytes]) -> dict[str, Any]:
    try:
        header_b64, claims_b64, signature_b64 = token.strip().split(".")
        header = json.loads(_b64decode(header_b64))
        claims = json.loads(_b64decode(claims_b64))
        signature = _b64decode(signature_b64)
    except (ValueError, binascii.Error) as exc:
        raise WebhookVerificationError("Signature is not a valid JWT") from exc
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise WebhookVerificationError("Signature algorithm must be HS256")
    if not isinstance(claims, dict):
        raise WebhookVerificationError("Signature claims are not a JSON object")
    key = secret.encode() if isinstance(secret, str) else secret
    expected = hmac.new(key, f"{header_b64}.{claims_b64}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise WebhookVerificationError("Signature is invalid")
    return claims
