import io
import re
from pathlib import Path
from typing import NamedTuple, Optional

import httpx
import pytest
import respx

from hlthstack import Hlthstack
from hlthstack.types import DigitizationCustomer


class Part(NamedTuple):
    name: str
    filename: Optional[str]
    content_type: Optional[str]
    data: bytes


def parse_multipart(request: httpx.Request) -> list[Part]:
    match = re.search(r"boundary=([^;]+)", request.headers["Content-Type"])
    assert match, request.headers["Content-Type"]
    assert request.headers["Content-Type"].startswith("multipart/form-data")
    boundary = match.group(1).encode()
    parts = []
    for chunk in request.content.split(b"--" + boundary)[1:-1]:
        head, _, data = chunk.strip(b"\r\n").partition(b"\r\n\r\n")
        headers = head.decode()
        name = re.search(r'name="([^"]*)"', headers)
        filename = re.search(r'filename="([^"]*)"', headers)
        ctype = re.search(r"Content-Type: (\S+)", headers)
        assert name
        parts.append(
            Part(
                name.group(1),
                filename.group(1) if filename else None,
                ctype.group(1) if ctype else None,
                data,
            )
        )
    return parts


CUSTOMER: DigitizationCustomer = {
    "name": "Jane Doe",
    "api_customer_id": "CUST1001",
    "mobile_number": "9999999999",
    "gender": "female",
    "dob": "1990-08-24",
}


def test_upload_documents_interleaves_name_value_pairs(
    router: respx.MockRouter, client: Hlthstack, tmp_path: Path
) -> None:
    report = tmp_path / "blood.pdf"
    report.write_bytes(b"%PDF blood")
    route = router.post("/api/consultations/APT1A2B3C4D5/upload_documents").respond(
        json={"message": "Document uploaded successfully"}
    )
    result = client.consultations.upload_documents(
        "APT1A2B3C4D5",
        [
            ("Blood report", str(report)),
            ("X-ray", io.BytesIO(b"\x89PNG xray")),
            ("Scan", ("scan.jpg", b"jpeg-bytes")),
        ],
    )
    assert result == {"message": "Document uploaded successfully"}
    parts = parse_multipart(route.calls.last.request)
    assert [(p.name, p.filename) for p in parts] == [
        ("files[][name]", None),
        ("files[][value]", "blood.pdf"),
        ("files[][name]", None),
        ("files[][value]", "file"),
        ("files[][name]", None),
        ("files[][value]", "scan.jpg"),
    ]
    assert parts[0].data == b"Blood report"
    assert parts[1].data == b"%PDF blood"
    assert parts[1].content_type == "application/pdf"
    assert parts[3].data == b"\x89PNG xray"
    assert parts[5].content_type == "image/jpeg"


def test_digitize_prescription(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.post("/api/prescriptions/digitize").respond(
        202, json={"request_id": "DIGI_RQ_A1B2C3D4E", "status": "pending"}
    )
    result = client.pharmacy.digitize_prescription(
        customer=CUSTOMER,
        files=[("rx.pdf", b"%PDF rx"), ("rx2.png", io.BytesIO(b"png"), "image/png")],
        plan_id="EXAMPLE_PLAN",
        idempotency_key="upload-0001",
    )
    assert result["request_id"] == "DIGI_RQ_A1B2C3D4E"
    request = route.calls.last.request
    assert request.headers["Idempotency-Key"] == "upload-0001"
    parts = parse_multipart(request)
    fields = {p.name: p.data.decode() for p in parts if p.filename is None}
    assert fields == {
        "customers[][name]": "Jane Doe",
        "customers[][api_customer_id]": "CUST1001",
        "customers[][mobile_number]": "9999999999",
        "customers[][gender]": "female",
        "customers[][dob]": "1990-08-24",
        "plan_id": "EXAMPLE_PLAN",
    }
    files = [p for p in parts if p.filename is not None]
    assert [(p.name, p.filename, p.content_type, p.data) for p in files] == [
        ("files[]", "rx.pdf", "application/pdf", b"%PDF rx"),
        ("files[]", "rx2.png", "image/png", b"png"),
    ]


def test_update_cart_with_prescription_files(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.patch("/api/epharmacy/cart").respond(json={"success": True, "cart": {}})
    client.pharmacy.update_cart(
        customer_details={"api_customer_id": "CUST1001"},
        plan_id="EXAMPLE_PLAN",
        prescription_files=[b"%PDF rx"],
    )
    parts = parse_multipart(route.calls.last.request)
    assert [(p.name, p.filename, p.data) for p in parts] == [
        ("customer_details[api_customer_id]", None, b"CUST1001"),
        ("plan_id", None, b"EXAMPLE_PLAN"),
        ("prescription_files[]", "file", b"%PDF rx"),
    ]


def test_update_cart_rejects_mixing_files_with_other_changes(client: Hlthstack) -> None:
    with pytest.raises(ValueError, match="products"):
        client.pharmacy.update_cart(
            customer_details={"api_customer_id": "CUST1001"},
            products=[{"id": 50001, "quantity": 1}],
            prescription_files=[b"%PDF rx"],
        )


def test_single_file_instead_of_list_is_rejected(client: Hlthstack) -> None:
    with pytest.raises(TypeError):
        client.pharmacy.digitize_prescription(customer=CUSTOMER, files="rx.pdf")


def test_multipart_resent_after_401(router: respx.MockRouter, client: Hlthstack) -> None:
    route = router.post("/api/prescriptions/digitize").mock(
        side_effect=[
            httpx.Response(401, text="HTTP Token: Access denied."),
            httpx.Response(202, json={"request_id": "DIGI_RQ_A1B2C3D4E"}),
        ]
    )
    client.pharmacy.digitize_prescription(customer=CUSTOMER, files=[io.BytesIO(b"%PDF rx")])
    assert route.call_count == 2
    first, second = (parse_multipart(c.request) for c in route.calls)
    assert first == second
    assert first[-1].data == b"%PDF rx"
