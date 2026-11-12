import datetime as dt
import importlib.util
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, NamedTuple, Optional

import pytest
import respx
import yaml

from hlthstack import AsyncHlthstack, Hlthstack, HlthstackError, ValidationError
from hlthstack._validation import (
    IST,
    UploadFile,
    _check,
    _deserialize,
    _relative_date,
    form_to_dict,
    validate_request,
)
from hlthstack._validation_spec import OPERATIONS

from .conftest import NOW, PASSWORD, USERNAME

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_validation.py"

CUSTOMER = {
    "name": "Jane Doe",
    "dob": "1990-08-24",
    "gender": "female",
    "mobile_number": "9999999999",
    "api_customer_id": "CUST1001",
    "package_ids": [1001],
}
ADDRESS = {
    "address_line_one": "1 Example Road",
    "address_line_two": "Madhapur",
    "city": "Hyderabad",
    "state": "Telangana",
    "country": "India",
    "pincode": "500081",
    "latitude": 17.44,
    "longitude": 78.38,
}
EMPLOYEE = {
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
    "date_of_joining": "01-01-2025",
}
DIGITIZE_CUSTOMER = {k: CUSTOMER[k] for k in ("name", "api_customer_id", "mobile_number", "gender")}
DIGITIZE_CUSTOMER["dob"] = "1990-08-24"
PDF = ("rx.pdf", b"%PDF-1.4 example")


@pytest.fixture
def full_client() -> Iterator[Hlthstack]:
    with Hlthstack(
        username=USERNAME,
        password=PASSWORD,
        pre_registration_username="prereg@example.com",
        pre_registration_password=PASSWORD,
        environment="staging",
    ) as c:
        c._clock = lambda: NOW
        yield c


@pytest.fixture
def full_async_client() -> AsyncHlthstack:
    c = AsyncHlthstack(
        username=USERNAME,
        password=PASSWORD,
        pre_registration_username="prereg@example.com",
        pre_registration_password=PASSWORD,
        environment="staging",
    )
    c._clock = lambda: NOW
    return c


@pytest.fixture
def api(router: respx.MockRouter) -> respx.MockRouter:
    """Answer every API call with 200 ``{}`` (token routes are matched first)."""
    router.route(name="api").respond(json={})
    return router


# --------------------------------------------------------------------------- generated module


def test_validation_spec_is_generated_from_openapi() -> None:
    spec = importlib.util.spec_from_file_location("build_validation", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.TARGET.read_text() == module.generate(), (
        "_validation_spec.py is stale: run python scripts/build_validation.py"
    )


def test_every_operation_is_validated_by_its_method() -> None:
    source = (ROOT / "src" / "hlthstack" / "_async_resources.py").read_text()
    sent = set(re.findall(r'operation="(\w+)"', source))
    token_operations = {"getAccessToken", "getPreRegistrationAccessToken"}
    assert sent == set(OPERATIONS) - token_operations


# --------------------------------------------------------------------------- spec examples

PATH_VALUES = {
    "booking_id": "EKI0000000001700000000",
    "appointment_id": "APT1A2B3C4D5",
    "order_id": "EPO000000000001",
    "company_slug": "example-co",
    "provider_id": "1001",
    "benefit_type": "ahc",
    "request_id": "3f2b8c1e-0d4a-4c5e-9b7a-2e6f1d8c9a01",
}


def _spec() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((ROOT / "openapi" / "openapi.yaml").read_text())
    return loaded


def _resolve(spec: Mapping[str, Any], node: Any) -> Any:
    while isinstance(node, Mapping) and "$ref" in node:
        target: Any = spec
        for part in node["$ref"][2:].split("/"):
            target = target[part]
        node = target
    return node


class Example(NamedTuple):
    operation_id: str
    content_type: str
    body: Any


def _body_examples() -> list[Example]:
    spec = _spec()
    out = []
    for item in spec["paths"].values():
        for method, op in item.items():
            if method == "parameters" or "requestBody" not in op:
                continue
            body = _resolve(spec, op["requestBody"])
            for content_type, content in body["content"].items():
                values = [e["value"] for e in content.get("examples", {}).values()]
                if "example" in content:
                    values.append(content["example"])
                out += [Example(op["operationId"], content_type, v) for v in values]
    return out


@pytest.mark.parametrize("example", _body_examples(), ids=lambda e: e.operation_id)
def test_spec_request_examples_pass(example: Example) -> None:
    op = OPERATIONS[example.operation_id]
    url = op["path"].format(**PATH_VALUES)
    files: Optional[list[Any]] = None
    if example.content_type == "multipart/form-data":
        files = [(k, (None, str(v).encode(), None)) for k, v in example.body.items()]
    json = example.body if files is None else None
    errors = validate_request(
        example.operation_id, url=url, params={}, json=json, files=files, now=NOW
    )
    assert errors == []


def test_spec_parameter_examples_pass() -> None:
    spec = _spec()
    checked = 0
    for item in spec["paths"].values():
        for method, op in item.items():
            if method == "parameters":
                continue
            for raw in item.get("parameters", []) + op.get("parameters", []):
                param = _resolve(spec, raw)
                schema = param.get("schema", {})
                values = ([param["example"]] if "example" in param else []) + schema.get(
                    "examples", []
                )
                for value in values:
                    assert _check(_deserialize(str(value), schema), schema, param["name"]) == []
                    checked += 1
    assert checked > 0


# --------------------------------------------------------------------------- keywords


@pytest.mark.parametrize(
    ("schema", "valid", "invalid"),
    [
        ({"type": "string"}, ["", "x"], [1, None, True]),
        ({"type": "integer"}, [1, -3, 2.0], ["1", 1.5, True]),
        ({"type": "number"}, [1, 1.5], ["1", False]),
        ({"type": "boolean"}, [True, False], [0, "true"]),
        ({"type": "object"}, [{}], [[]]),
        ({"type": "array"}, [[], (1,)], [{}]),
        ({"type": ["string", "null"]}, ["x", None], [1]),
        ({"enum": ["male", "female"]}, ["male"], ["Male", None]),
        ({"enum": [0, 1]}, [0, 1], [False, True, "1"]),
        # Patterns are searched, not matched: unanchored ones match anywhere.
        ({"pattern": r"\S"}, ["  x  ", 5], ["", "   "]),
        ({"pattern": "EKI[0-9]{3}"}, ["xxEKI123yy"], ["EKI12"]),
        ({"pattern": "^[0-9]{6}$"}, ["500081"], ["5000812", " 500081"]),
        ({"minLength": 3}, ["abc", 1], ["ab"]),
        ({"maxLength": 3}, ["abc"], ["abcd"]),
        ({"minimum": 0}, [0, 5, "-1"], [-1, -0.5]),
        ({"maximum": 50}, [50], [51]),
        ({"exclusiveMinimum": 0}, [0.01, "0"], [0, -1]),
        ({"minItems": 1}, [[1]], [[]]),
        ({"maxItems": 2}, [[1, 2]], [[1, 2, 3]]),
        ({"format": "date"}, ["2026-02-28"], ["2026-02-30", "26-02-2026", "2026-2-1"]),
        (
            {"format": "date-time"},
            [
                "2026-01-15T02:30:00Z",
                "2026-01-15T08:00:00.000+05:30",
                "2026-01-15t02:30:00z",
                "2026-01-15T08:00:00",
            ],
            ["2026-01-15 02:30:00Z", "2026-01-15T25:00:00Z", "2026-01-15"],
        ),
        ({"format": "uri"}, ["https://example.com/a.pdf"], ["example.com/a.pdf", "https://a b"]),
        ({"format": "uuid"}, ["3f2b8c1e-0d4a-4c5e-9b7a-2e6f1d8c9a01"], ["3f2b8c1e"]),
        ({"required": ["a"]}, [{"a": None}], [{"b": 1}]),
        ({"properties": {"a": {"type": "integer"}}}, [{}, {"a": 1}], [{"a": "1"}]),
        ({"items": {"type": "integer"}}, [[1, 2]], [[1, "2"]]),
        ({"allOf": [{"minimum": 1}, {"maximum": 2}]}, [1, 2], [0, 3]),
        ({"anyOf": [{"type": "boolean"}, {"type": "integer", "enum": [0, 1]}]}, [True, 1], [2]),
        ({"oneOf": [{"type": "string"}, {"type": "integer"}]}, ["a", 1], [1.5]),
        ({"oneOf": [{"minimum": 0}, {"maximum": 10}]}, [-1, 11], [5]),
    ],
)
def test_keyword(schema: dict[str, Any], valid: list[Any], invalid: list[Any]) -> None:
    for value in valid:
        assert _check(value, schema, "field") == [], value
    for value in invalid:
        errors = _check(value, schema, "field")
        assert errors, value
        assert errors[0]["path"].startswith("field")


def test_keyword_errors_name_the_path_and_keyword() -> None:
    schema = {
        "type": "object",
        "required": ["customers"],
        "properties": {
            "customers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"mobile_number": {"type": "string", "pattern": "^[0-9]{10}$"}},
                },
            }
        },
    }
    errors = _check({"customers": [{"name": "A"}, {"mobile_number": "123"}]}, schema, "")
    assert errors == [
        {"path": "customers[1].name", "message": "is required", "rule": "required"},
        {
            "path": "customers[1].mobile_number",
            "message": "must match the pattern ^[0-9]{10}$",
            "rule": "pattern",
        },
    ]


def test_one_of_reports_the_branch_with_the_right_type() -> None:
    schema = {
        "oneOf": [
            {"type": "string"},
            {"type": "object", "required": ["plan_id"], "properties": {}},
        ]
    }
    assert _check({"start_date": "x"}, schema, "plans[0]") == [
        {"path": "plans[0].plan_id", "message": "is required", "rule": "required"}
    ]


def test_spec_uses_only_implemented_keywords() -> None:
    spec = importlib.util.spec_from_file_location("build_validation", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    used: set[str] = set()

    def walk(schema: Any) -> None:
        if isinstance(schema, dict):
            used.update(k for k in schema if k not in ("properties",))
            for value in schema.get("properties", {}).values():
                walk(value)
            walk(schema.get("items"))
            for key in ("allOf", "anyOf", "oneOf"):
                for sub in schema.get(key, []):
                    walk(sub)

    for op in OPERATIONS.values():
        for param in op["parameters"]:
            walk(param["schema"])
        for schema in op["body"].values():
            walk(schema)
    assert used - {"properties"} <= module.KEYWORDS
    assert {"pattern", "format", "oneOf", "anyOf", "allOf", "exclusiveMinimum"} <= used


def test_query_strings_are_read_as_their_schema_type() -> None:
    assert _deserialize("17.0", {"type": "number"}) == 17.0
    assert _deserialize("1001", {"type": "integer"}) == 1001
    assert _deserialize("true", {"type": "boolean"}) is True
    assert _deserialize("abc", {"type": "integer"}) == "abc"
    assert _deserialize("007", {"type": "string"}) == "007"


def test_multipart_fields_are_nested_like_the_server_parses_them() -> None:
    parts = [
        ("customers[][name]", (None, b"Jane", None)),
        ("customers[][dob]", (None, b"1990-08-24", None)),
        ("files[][name]", (None, b"A", None)),
        ("files[][value]", ("a.pdf", b"%PDF", "application/pdf")),
        ("files[][name]", (None, b"B", None)),
        ("files[][value]", ("b.png", b"png", "image/png")),
        ("customer_details[api_customer_id]", (None, b"CUST1001", None)),
        ("prescription_files[]", ("rx.pdf", b"%PDF", "application/pdf")),
        ("plan_id", (None, b"EXAMPLE_PLAN", None)),
    ]
    assert form_to_dict(parts) == {
        "customers": [{"name": "Jane", "dob": "1990-08-24"}],
        "files": [
            {"name": "A", "value": UploadFile("a.pdf", "application/pdf", 4)},
            {"name": "B", "value": UploadFile("b.png", "image/png", 3)},
        ],
        "customer_details": {"api_customer_id": "CUST1001"},
        "prescription_files": [UploadFile("rx.pdf", "application/pdf", 4)],
        "plan_id": "EXAMPLE_PLAN",
    }


# --------------------------------------------------------------------------- rule kinds


def _errors(operation_id: str, *, now: dt.datetime = NOW, **request: Any) -> set[tuple[str, str]]:
    op = OPERATIONS[operation_id]
    request.setdefault("url", op["path"].format(**PATH_VALUES))
    request.setdefault("params", {})
    request.setdefault("json", None)
    request.setdefault("files", None)
    return {(e["path"], e["rule"]) for e in validate_request(operation_id, now=now, **request)}


def test_rule_required_if() -> None:
    params = {"service_name": "ahc", "package_ids": "1001"}
    assert _errors("listProviders", params=params) == {
        ("latitude", "required_if"),
        ("longitude", "required_if"),
    }
    assert _errors("listProviders", params={**params, "pincode": "500081"}) == set()
    assert _errors("listProviders", params={**params, "latitude": "17.4", "longitude": "78.3"}) == (
        set()
    )
    body = {
        "provider_id": 1,
        "appointment_date_time": "2026-01-15T02:30:00Z",
        "appointment_type": "home_collection",
        "service_name": "ahc",
        "customers": [CUSTOMER],
    }
    assert _errors("createAppointment", json=body) == {("address", "required_if")}
    assert _errors("createAppointment", json={**body, "appointment_type": "inclinic"}) == set()


def test_rule_allowed_only_if() -> None:
    params = {"service_name": "ahc", "package_ids": "1001", "pincode": "500081", "gender": "Male"}
    assert _errors("listProviders", params=params) == {("gender", "allowed_only_if")}
    params["service_name"] = "inclinic_consultation"
    assert _errors("listProviders", params=params) == set()


def test_rule_at_least_one_of() -> None:
    assert _errors("listCustomerPlans") == {("", "at_least_one_of")}
    assert _errors("listCustomerPlans", params={"customer_id": "  "}) == {("", "at_least_one_of")}
    assert _errors("listCustomerPlans", params={"customer_id": "1001"}) == set()
    dependants = [
        {"guardian_employee_code": "EMP1"},  # needs company_id too
        {"company_id": "1001", "guardian_employee_code": "EMP1"},
        {"guardian_email": "jane.doe@example.com"},
    ]
    row = {"first_name": "John", "last_name": "", "date_of_birth": "", "gender": ""}
    row.update(mobile_number="", relation="Father")
    body = {"dependants": [{**row, **d} for d in dependants]}
    assert _errors("createPreRegistrations", json=body) == {("dependants[0]", "at_least_one_of")}


def test_rule_mutually_exclusive() -> None:
    body = {
        "customer_details": {"api_customer_id": "CUST1001"},
        "address": {"line1": "1 Example Road", "city": "Pune", "state": "MH", "pincode": "411001"},
        "address_id": 5,
    }
    assert _errors("updateCart", json=body) == {("address_id", "mutually_exclusive")}


def test_rule_unique_by() -> None:
    body = {
        "customer_details": {"api_customer_id": "CUST1001"},
        "products": [{"id": 1, "quantity": 1}, {"id": 2, "quantity": 1}, {"id": 1, "quantity": 0}],
    }
    errors = validate_request(
        "updateCart", url="/api/epharmacy/cart", params={}, json=body, files=None, now=NOW
    )
    assert [(e["path"], e["rule"]) for e in errors] == [("products[2].id", "unique_by")]
    assert errors[0]["message"].startswith("same value as products[0].id.")


def test_rule_relative_date() -> None:
    body: dict[str, Any] = {
        "provider_id": 1,
        "appointment_date_time": "2026-01-15T02:30:00Z",
        "customers": [{**CUSTOMER, "dob": "2025-01-01"}, {**CUSTOMER, "api_customer_id": "C2"}],
        "address": ADDRESS,
    }
    assert _errors("createInclinicConsultation", json=body) == set()
    body["customers"][0]["dob"] = "2025-01-02"  # less than a year before 2026-01-01
    body["appointment_date_time"] = "2026-01-01T05:29:59+05:30"  # one second before NOW
    assert _errors("createInclinicConsultation", json=body) == {
        ("customers[0].dob", "relative_date"),
        ("appointment_date_time", "relative_date"),
    }
    # Priority consultations need no time.
    specialist = {"provider_id": 1, "customers": [CUSTOMER], "priority_consultation": True}
    assert _errors("createSpecialistConsultation", json=specialist) == set()
    specialist["appointment_date_time"] = "2025-01-01T00:00:00Z"
    assert _errors("createSpecialistConsultation", json=specialist) == set()
    specialist["priority_consultation"] = False
    assert _errors("createSpecialistConsultation", json=specialist) == {
        ("appointment_date_time", "relative_date")
    }


def test_relative_date_reads_times_without_offset_as_ist_and_today_in_ist() -> None:
    rule = OPERATIONS["rescheduleConsultation"]["rules"][0]
    now = dt.datetime(2026, 1, 1, 0, 0, tzinfo=IST)
    assert _relative_date({"appointment_date_time": "2026-01-01T00:00:01"}, rule, now) == []
    assert _relative_date({"appointment_date_time": "2026-01-01T00:00:00"}, rule, now)
    # 20:00 UTC on 31 December is already 1 January in India.
    late = dt.datetime(2025, 12, 31, 20, 0, tzinfo=dt.timezone.utc)
    employee = {**EMPLOYEE, "date_of_birth": "01-01-2026"}
    assert _errors("createPreRegistrations", json={"employees": [employee]}, now=late) == set()
    employee["date_of_birth"] = "02/01/2026"
    assert _errors("createPreRegistrations", json={"employees": [employee]}, now=late) == {
        ("employees[0].date_of_birth", "relative_date")
    }
    employee["date_of_birth"] = " "  # blank is allowed
    assert _errors("createPreRegistrations", json={"employees": [employee]}, now=late) == set()


def test_rule_no_conflicting_pincode() -> None:
    body: dict[str, Any] = {
        "provider_id": 1,
        "appointment_date_time": "2026-01-15T02:30:00Z",
        "appointment_type": "home_collection",
        "service_name": "ahc",
        "customers": [CUSTOMER],
        "address": {**ADDRESS, "address_line_two": "Madhapur 500033", "city": "Hyderabad 500081"},
    }
    assert _errors("createAppointment", json=body) == {
        ("address.address_line_two", "no_conflicting_pincode")
    }
    # Only for home collection, only for Indian addresses, and only standalone numbers.
    assert _errors("createAppointment", json={**body, "appointment_type": "inclinic"}) == set()
    body["address"] = {**body["address"], "country": "Nepal"}
    assert _errors("createAppointment", json=body) == set()
    body["address"] = {**ADDRESS, "address_line_two": "Flat 1234567 / A500033"}
    assert _errors("createAppointment", json=body) == set()
    cart = {
        "customer_details": {"api_customer_id": "CUST1001"},
        "address": {"line1": "Road 411002", "city": "Pune", "state": "MH", "zip_code": "411001"},
    }
    # No country counts as India; zip_code stands in for pincode.
    assert _errors("updateCart", json=cart) == {("address.line1", "no_conflicting_pincode")}


def test_rule_file_limits() -> None:
    url = "/api/prescriptions/digitize"
    customer = [
        (f"customers[][{k}]", (None, str(v).encode(), None)) for k, v in DIGITIZE_CUSTOMER.items()
    ]
    big = 10 * 1024 * 1024
    files = [
        ("files[]", ("a.pdf", b"x" * big, "application/pdf")),
        ("files[]", ("b.pdf", b"x" * (big + 1), "application/pdf")),
        ("files[]", ("c.txt", b"x", "text/plain")),
    ]
    assert _errors("digitizePrescription", url=url, files=customer + files) == {
        ("files[1]", "file_limits"),
        ("files[2]", "file_limits"),
    }
    # updateCart accepts a matching content type or a matching extension.
    cart = [("customer_details[api_customer_id]", (None, b"CUST1001", None))]
    ok = [
        ("prescription_files[]", ("rx.pdf", b"x", "application/octet-stream")),
        ("prescription_files[]", ("rx", b"x", "image/png")),
    ]
    bad = [
        ("prescription_files[]", ("file", b"x", "application/octet-stream")),
        ("prescription_files[]", ("rx.jpg", b"x" * (7 * 1024 * 1024), "image/jpeg")),
    ]
    assert _errors("updateCart", url="/api/epharmacy/cart", files=cart + ok + bad) == {
        ("prescription_files[2]", "file_limits"),
        ("prescription_files[3]", "file_limits"),
    }


def test_rule_item_count() -> None:
    rows = [{"email": f"user{i}@example.com"} for i in range(251)]
    assert _errors("updatePreRegistrations", json={"employees": rows}) == {("", "item_count")}
    assert (
        _errors(
            "updatePreRegistrations",
            json={"employees": rows[:200], "dependants": [{"dependent_code": "D"}] * 50},
        )
        == set()
    )
    upload = "/api/consultations/APT1A2B3C4D5/upload_documents"
    assert _errors("uploadConsultationDocuments", url=upload, files=[]) == {("files", "required")}


def test_rule_positive_decimal() -> None:
    url = "/api/epharmacy/orders/EPO000000000001/confirm"
    body = {"customer_details": {"api_customer_id": "C1"}, "partner_payment_reference": "T1"}
    for amount in ("261.0", " 1 ", 0.5):
        assert (
            _errors("confirmOrder", url=url, json={**body, "partner_collected_amount": amount})
            == set()
        )
    for amount in ("0", "-5", "abc", "", "NaN"):
        assert _errors(
            "confirmOrder", url=url, json={**body, "partner_collected_amount": amount}
        ) == {("partner_collected_amount", "positive_decimal")}
    assert _errors("confirmOrder", url=url, json={**body, "partner_collected_amount": 0}) == {
        ("partner_collected_amount", "exclusiveMinimum")
    }


# --------------------------------------------------------------------------- per operation


class Case(NamedTuple):
    method: str
    args: tuple[Any, ...]
    valid: dict[str, Any]
    invalid: dict[str, Any]
    errors: set[tuple[str, str]]


CASES = [
    Case(
        "appointments.list_providers",
        (),
        {"service_name": "ahc", "package_ids": [1001], "pincode": "500081"},
        {"service_name": "ahc", "package_ids": [1001], "sort_by": "fee"},
        {("latitude", "required_if"), ("longitude", "required_if"), ("sort_by", "allowed_only_if")},
    ),
    Case(
        "appointments.create",
        (),
        {
            "service_name": "ahc",
            "appointment_type": "home_collection",
            "provider_id": 1001,
            "appointment_date_time": dt.datetime(2026, 1, 15, 2, 30, tzinfo=dt.timezone.utc),
            "customers": [CUSTOMER],
            "address": ADDRESS,
        },
        {
            "service_name": "ahc",
            "appointment_type": "home_collection",
            "provider_id": 1001,
            "appointment_date_time": "2026-01-15T02:30:00Z",
            "customers": [CUSTOMER, {**CUSTOMER, "mobile_number": "12345"}],
        },
        {
            ("address", "required_if"),
            ("customers[1].api_customer_id", "unique_by"),
            ("customers[1].mobile_number", "pattern"),
        },
    ),
    Case(
        "appointments.reschedule_booking",
        ("EKI0000000001700000000",),
        {"appointment_date_time": "2026-01-16T02:30:00Z", "address": ADDRESS},
        {
            "appointment_date_time": "2026-01-16T02:30:00Z",
            "address": {**ADDRESS, "state": "Telangana 500001"},
        },
        {("address.state", "no_conflicting_pincode")},
    ),
    Case(
        "appointments.reschedule",
        ("APT1A2B3C4D5",),
        {"appointment_date_time": "2026-01-16T02:30:00Z", "provider_id": 1002},
        {
            "appointment_date_time": "2026-01-16 02:30",
            "provider_id": "P1",
            "address": {**ADDRESS, "address_line_one": "Plot 500002"},
        },
        {
            ("appointment_date_time", "format"),
            ("provider_id", "pattern"),
            ("address.address_line_one", "no_conflicting_pincode"),
        },
    ),
    Case(
        "consultations.list_inclinic_providers",
        (),
        {"package_ids": [2001], "latitude": 17.4, "longitude": 78.3, "sort_by": "fee"},
        {"package_ids": [2001], "pincode": "5000", "sort_by": "visited_before", "per_page": 51},
        {("pincode", "pattern"), ("api_customer_id", "required_if"), ("per_page", "maximum")},
    ),
    Case(
        "consultations.create_inclinic",
        (),
        {
            "provider_id": 2001,
            "appointment_date_time": "2026-01-15T04:30:00.000Z",
            "customers": [CUSTOMER],
            "address": ADDRESS,
        },
        {
            "provider_id": 2001,
            "appointment_date_time": "2025-12-31T23:59:59Z",
            "customers": [{**CUSTOMER, "dob": "2025-06-01"}],
            "address": {k: v for k, v in ADDRESS.items() if k != "pincode"},
        },
        {
            ("appointment_date_time", "relative_date"),
            ("customers[0].dob", "relative_date"),
            ("address.pincode", "required"),
        },
    ),
    Case(
        "consultations.create_specialist",
        (),
        {"provider_id": 3001, "customers": [CUSTOMER], "priority_consultation": True},
        {"provider_id": 3001, "customers": [CUSTOMER, CUSTOMER], "priority_consultation": False},
        {("appointment_date_time", "required_if"), ("customers[1].api_customer_id", "unique_by")},
    ),
    Case(
        "consultations.reschedule",
        ("APT1A2B3C4D5",),
        {"appointment_date_time": "2026-01-16T04:30:00Z"},
        {"appointment_date_time": "2025-12-01T04:30:00Z"},
        {("appointment_date_time", "relative_date")},
    ),
    Case(
        "consultations.upload_documents",
        ("APT1A2B3C4D5", [("Blood report", PDF), ("X-ray", ("xray.PNG", b"png"))]),
        {},
        {},
        set(),
    ),
    Case(
        "pharmacy.digitize_prescription",
        (),
        {"customer": DIGITIZE_CUSTOMER, "files": [PDF]},
        {
            "customer": {**DIGITIZE_CUSTOMER, "dob": "2026-01-02", "gender": "Female"},
            "files": [("rx.heic", b"x")],
        },
        {
            ("customers[0].dob", "relative_date"),
            ("customers[0].gender", "enum"),
            ("files[0]", "file_limits"),
        },
    ),
    Case(
        "pharmacy.update_cart",
        (),
        {
            "customer_details": {"api_customer_id": "CUST1001"},
            "products": [{"id": 1, "quantity": 2}],
        },
        {
            "customer_details": {"api_customer_id": "CUST1001", "mobile_number": "+919999999999"},
            "address": {"line1": "1 Example Road", "city": "Pune", "state": "MH"},
            "address_id": 5,
            "fulfillment_type": "store_pickup",
            "prescription_urls": ["http://files.example.com/rx.pdf"],
        },
        {
            ("customer_details.mobile_number", "pattern"),
            ("address_id", "mutually_exclusive"),
            ("selected_chemist_id", "required_if"),
            ("address", "at_least_one_of"),
            ("prescription_urls[0]", "pattern"),
        },
    ),
    Case(
        "pharmacy.get_order_payment_details",
        (),
        {"api_customer_id": "CUST1001", "cart_id": 701, "selected_delivery_option": "standard"},
        {"api_customer_id": "CUST1001", "cart_id": 701, "selected_delivery_option": "store_pickup"},
        {("selected_chemist_id", "required_if")},
    ),
    Case(
        "pharmacy.confirm_order",
        ("EPO000000000001",),
        {
            "api_customer_id": "CUST1001",
            "partner_collected_amount": "261.00",
            "partner_payment_reference": "TXN-0001",
        },
        {
            "api_customer_id": "CUST1001",
            "partner_collected_amount": "0.00",
            "partner_payment_reference": " ",
        },
        {
            ("partner_collected_amount", "positive_decimal"),
            ("partner_payment_reference", "pattern"),
        },
    ),
    Case(
        "wallet.get_customer_wallet",
        ("example-co",),
        {"api_customer_id": "CUST1001"},
        {"customer_plan_id": -1},
        {("", "at_least_one_of"), ("customer_plan_id", "minimum")},
    ),
    Case(
        "wallet.list_customer_plans",
        ("example-co",),
        {"customer_id": "1001"},
        {"api_customer_id": ""},
        {("", "at_least_one_of")},
    ),
    Case(
        "pre_registration.create",
        (),
        {"employees": [EMPLOYEE]},
        {
            "employees": [
                {**EMPLOYEE, "email": "", "employee_code": None},
                {**EMPLOYEE, "date_of_birth": "01-01-2027", "vip": "maybe"},
            ]
        },
        {
            ("employees[0]", "at_least_one_of"),
            ("employees[1].date_of_birth", "relative_date"),
            ("employees[1].vip", "pattern"),
        },
    ),
    Case(
        "pre_registration.update",
        (),
        {"employees": [{"company_id": 1001, "employee_code": "EMP1001", "grade": "C"}]},
        {"employees": [{"employee_code": "EMP1001"}], "dependants": [{"relation": "Father"}]},
        {("employees[0]", "at_least_one_of"), ("dependants[0]", "at_least_one_of")},
    ),
    Case(
        "pre_registration.deactivate",
        (),
        {"employees": ["jane.doe@example.com"], "dependants": ["9999999998"]},
        {"employees": [f"user{i}@example.com" for i in range(200)], "dependants": ["1"] * 51},
        {("", "item_count")},
    ),
]
# upload_documents takes its files positionally: its invalid call is separate.
UPLOAD_INVALID = ("APT1A2B3C4D5", [(" ", ("notes.docx", b"x"))])


def _method(client: Any, name: str) -> Any:
    target = client
    for part in name.split("."):
        target = getattr(target, part)
    return target


def _invalid_call(case: Case) -> tuple[tuple[Any, ...], dict[str, Any], set[tuple[str, str]]]:
    if case.method == "consultations.upload_documents":
        return UPLOAD_INVALID, {}, {("files[0].name", "pattern"), ("files[0].value", "file_limits")}
    return case.args, case.invalid, case.errors


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.method)
def test_operation_sync(case: Case, api: respx.MockRouter, full_client: Hlthstack) -> None:
    method = _method(full_client, case.method)
    method(*case.args, **case.valid)
    assert api["api"].call_count == 1

    args, kwargs, expected = _invalid_call(case)
    api.reset()
    with pytest.raises(ValidationError) as caught:
        method(*args, **kwargs)
    assert {(e["path"], e["rule"]) for e in caught.value.errors} == expected
    assert not api.calls  # nothing sent, not even a token request

    method(*args, **kwargs, validate=False)
    assert api["api"].call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.method)
async def test_operation_async(
    case: Case, api: respx.MockRouter, full_async_client: AsyncHlthstack
) -> None:
    async with full_async_client as client:
        method = _method(client, case.method)
        await method(*case.args, **case.valid)
        assert api["api"].call_count == 1

        args, kwargs, expected = _invalid_call(case)
        api.reset()
        with pytest.raises(ValidationError) as caught:
            await method(*args, **kwargs)
        assert {(e["path"], e["rule"]) for e in caught.value.errors} == expected
        assert not api.calls


# --------------------------------------------------------------------------- client behaviour


def test_validation_error_shape(router: respx.MockRouter, client: Hlthstack) -> None:
    with pytest.raises(ValidationError) as caught:
        client.appointments.get("EKI123")
    error = caught.value
    assert isinstance(error, HlthstackError)
    assert isinstance(error, ValueError)
    assert error.operation_id == "getAppointment"
    assert error.status_code is None
    assert error.errors == [
        {
            "path": "booking_id",
            "message": "must match the pattern EKI[0-9A-Z_]{19}",
            "rule": "pattern",
        }
    ]
    assert error.messages == ["booking_id: must match the pattern EKI[0-9A-Z_]{19}"]
    assert str(error) == (
        "Invalid getAppointment request (1 problem):\n"
        "  - booking_id: must match the pattern EKI[0-9A-Z_]{19} [pattern]"
    )
    assert not router.calls


def test_validation_can_be_turned_off_per_client_and_per_call(router: respx.MockRouter) -> None:
    route = router.get("/api/appointments").respond(json={})
    with Hlthstack(
        username=USERNAME, password=PASSWORD, environment="staging", validate=False
    ) as c:
        c.appointments.get("EKI123")
        assert route.call_count == 1
        with pytest.raises(ValidationError):
            c.appointments.get("EKI123", validate=True)
    with Hlthstack(username=USERNAME, password=PASSWORD, environment="staging") as c:
        c.appointments.get("EKI123", validate=False)
        assert route.call_count == 2


def test_missing_digitization_field_is_reported(client: Hlthstack) -> None:
    customer: Any = {k: v for k, v in DIGITIZE_CUSTOMER.items() if k != "mobile_number"}
    with pytest.raises(ValidationError) as caught:
        client.pharmacy.digitize_prescription(customer=customer, files=[PDF])
    assert caught.value.errors == [
        {"path": "customers[0].mobile_number", "message": "is required", "rule": "required"}
    ]
