"""Generate the request-validation tables from the OpenAPI spec.

python scripts/build_validation.py          # rewrite src/hlthstack/_validation_spec.py
python scripts/build_validation.py --check  # exit 1 if it is out of date

For every operation the generated module holds the path template, the path and query
parameter schemas, the request body schema per content type and the operation's
``x-hlthstack-rules``, all with ``$ref`` resolved and annotations dropped. Multipart
schemas, whose fields are flat bracketed names (``customers[][dob]``), are rewritten into
the nested shape the server parses them into (``customers[].dob``), so they validate like
JSON bodies.

The rule kinds describe their conditions and bounds in prose. ``RULES`` below restates
each rule instance as parameters the validator reads; the script fails if the spec's rules
and ``RULES`` disagree, or if a schema uses a keyword or format the validator does not
implement.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "openapi" / "openapi.yaml"
TARGET = ROOT / "src" / "hlthstack" / "_validation_spec.py"

# Keywords the validator in src/hlthstack/_validation.py implements.
KEYWORDS = {
    "type",
    "enum",
    "required",
    "properties",
    "items",
    "pattern",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "minItems",
    "maxItems",
    "format",
    "allOf",
    "anyOf",
    "oneOf",
    "contentMediaType",  # kept: marks a file field
}
ANNOTATIONS = {"description", "example", "examples", "default", "title", "deprecated"}
FORMATS = {"date", "date-time", "uri", "uuid"}
RULE_KINDS = {
    "required_if",
    "at_least_one_of",
    "mutually_exclusive",
    "allowed_only_if",
    "unique_by",
    "relative_date",
    "no_conflicting_pincode",
    "file_limits",
    "item_count",
    "positive_decimal",
}

MB = 1024 * 1024
HOME_COLLECTION = {"path": "appointment_type", "equals": "home_collection"}
NOT_PRIORITY = {"path": "priority_consultation", "not_equals": True}
BOOKING_ADDRESS = [
    "address.address_line_one",
    "address.address_line_two",
    "address.city",
    "address.state",
    "address.country",
    "address.pincode",
]
BOOKING_ADDRESS_TEXT = ["address_line_one", "address_line_two", "city", "state", "country"]
AT_LEAST_ONE_YEAR_OLD = {
    "rule": "relative_date",
    "description": "Each customer's dob must be on or before the same date one year ago "
    "(members must be at least 1 year old).",
    "fields": ["customers[].dob"],
    "paths": ["customers[].dob"],
    "format": "date",
    "compare": "on_or_before",
    "base": "today",
    "years": -1,
}
UNIQUE_CUSTOMERS = {
    "rule": "unique_by",
    "description": "Each customer needs its own api_customer_id.",
    "fields": ["customers[].api_customer_id"],
    "array": "customers",
    "key": "api_customer_id",
}
LATER_THAN_NOW = {
    "rule": "relative_date",
    "description": "appointment_date_time must be later than now (a time without an offset "
    "is read as IST).",
    "fields": ["appointment_date_time"],
    "paths": ["appointment_date_time"],
    "format": "date-time",
    "compare": "after",
    "base": "now",
}
LOCATION_REQUIRED = {
    "rule": "required_if",
    "description": "When pincode is not sent, latitude and longitude are both required "
    "(the pincode is derived from them).",
    "fields": ["pincode", "latitude", "longitude"],
    "when": {"path": "pincode", "blank": True},
    "require": ["latitude", "longitude"],
}
VISITED_BEFORE = {
    "rule": "required_if",
    "description": "api_customer_id is required when sort_by is visited_before.",
    "fields": ["api_customer_id", "sort_by"],
    "when": {"path": "sort_by", "equals": "visited_before"},
    "require": ["api_customer_id"],
}
MAX_250_ROWS = {
    "rule": "item_count",
    "fields": ["employees", "dependants"],
    "paths": ["employees", "dependants"],
    "max": 250,
}


def _reschedule_pincode(what: str) -> dict[str, Any]:
    return {
        "rule": "no_conflicting_pincode",
        "description": f"When address is sent for a home-collection {what}, address_line_one, "
        "address_line_two, city, state and country must not contain a 6-digit pincode "
        "other than address.pincode.",
        "fields": BOOKING_ADDRESS,
        "address": "address",
        "text": BOOKING_ADDRESS_TEXT,
        "pincode": ["pincode"],
    }


def _either(*fields: str) -> list[list[str]]:
    return [[f] for f in fields]


# Each spec rule restated as validator parameters, in the spec's order. ``rule``,
# ``description`` and ``fields`` must match the spec exactly; the other keys are what the
# validator reads. Paths are dotted, ``[]`` stands for every array item.
RULES: dict[str, list[dict[str, Any]]] = {
    "listProviders": [
        LOCATION_REQUIRED,
        {
            "rule": "allowed_only_if",
            "description": "sort_by and gender are accepted only when service_name is "
            "inclinic_consultation.",
            "fields": ["sort_by", "gender", "service_name"],
            "when": {"path": "service_name", "equals": "inclinic_consultation"},
            "allowed": ["sort_by", "gender"],
        },
        VISITED_BEFORE,
    ],
    "createAppointment": [
        {
            "rule": "required_if",
            "description": "address is required when appointment_type is home_collection.",
            "fields": ["address", "appointment_type"],
            "when": HOME_COLLECTION,
            "require": ["address"],
        },
        UNIQUE_CUSTOMERS,
        AT_LEAST_ONE_YEAR_OLD,
        {
            "rule": "no_conflicting_pincode",
            "description": "Home collection only. address_line_one, address_line_two, city, "
            "state and country must not contain a 6-digit pincode other than "
            "address.pincode.",
            "fields": BOOKING_ADDRESS,
            "when": HOME_COLLECTION,
            "address": "address",
            "text": BOOKING_ADDRESS_TEXT,
            "pincode": ["pincode"],
        },
    ],
    "rescheduleBooking": [_reschedule_pincode("booking")],
    "rescheduleAppointment": [_reschedule_pincode("appointment")],
    "listInclinicConsultationProviders": [LOCATION_REQUIRED, VISITED_BEFORE],
    "createInclinicConsultation": [UNIQUE_CUSTOMERS, AT_LEAST_ONE_YEAR_OLD, LATER_THAN_NOW],
    "createSpecialistConsultation": [
        {
            "rule": "required_if",
            "description": "appointment_date_time is required unless priority_consultation is "
            "true.",
            "fields": ["appointment_date_time", "priority_consultation"],
            "when": NOT_PRIORITY,
            "require": ["appointment_date_time"],
        },
        {
            **LATER_THAN_NOW,
            "description": "Unless priority_consultation is true, appointment_date_time must "
            "be later than now (a time without an offset is read as IST).",
            "fields": ["appointment_date_time", "priority_consultation"],
            "when": NOT_PRIORITY,
        },
        UNIQUE_CUSTOMERS,
        AT_LEAST_ONE_YEAR_OLD,
    ],
    "rescheduleConsultation": [LATER_THAN_NOW],
    "uploadConsultationDocuments": [
        {
            # Each entry needing both a name and a value is the nested schema's ``required``.
            "rule": "item_count",
            "description": "At least one file; every file entry needs both a non-blank name "
            "and a value.",
            "fields": ["files[][name]", "files[][value]"],
            "paths": ["files"],
            "min": 1,
        },
        {
            # "not password-protected" can't be told reliably without parsing the PDF.
            "rule": "file_limits",
            "description": "Each file must be PDF, JPEG or PNG (extension pdf, jpg, jpeg or "
            "png) and not password-protected.",
            "fields": ["files[][value]"],
            "files": "files[].value",
            "extensions": ["pdf", "jpg", "jpeg", "png"],
        },
    ],
    "digitizePrescription": [
        {
            "rule": "item_count",
            "description": "customers must contain exactly one customer.",
            "fields": ["customers"],
            "paths": ["customers"],
            "min": 1,
            "max": 1,
        },
        {
            "rule": "item_count",
            "description": "files[] must contain at least one file.",
            "fields": ["files[]"],
            "paths": ["files"],
            "min": 1,
        },
        {
            "rule": "file_limits",
            "description": "Each file at most 10 MB, with content type image/jpeg, image/png "
            "or application/pdf.",
            "fields": ["files[]"],
            "files": "files[]",
            "max_bytes": 10 * MB,
            "content_types": ["image/jpeg", "image/png", "application/pdf"],
        },
        {
            "rule": "relative_date",
            "description": "dob must not be after today.",
            "fields": ["customers[][dob]"],
            "paths": ["customers[].dob"],
            "format": "date",
            "compare": "on_or_before",
            "base": "today",
        },
    ],
    "updateCart": [
        {
            "rule": "at_least_one_of",
            "description": "Send at least one change (products, address or address_id, "
            "prescription_urls or prescription_files, remove_prescription_ids, "
            "fulfillment_type or selected_chemist_id).",
            "fields": [
                "products",
                "address",
                "address_id",
                "prescription_urls",
                "prescription_files",
                "remove_prescription_ids",
                "fulfillment_type",
                "selected_chemist_id",
            ],
            "groups": _either(
                "products",
                "address",
                "address_id",
                "prescription_urls",
                "prescription_files",
                "remove_prescription_ids",
                "fulfillment_type",
                "selected_chemist_id",
            ),
        },
        {
            "rule": "mutually_exclusive",
            "description": "Send either address or address_id, not both.",
            "fields": ["address", "address_id"],
            "exclusive": ["address", "address_id"],
        },
        {
            # The "cart is already store pickup" half depends on stored data.
            "rule": "required_if",
            "description": "selected_chemist_id is required when fulfillment_type is "
            "store_pickup (or the cart is already store pickup and fulfillment_type is not "
            "sent).",
            "fields": ["selected_chemist_id", "fulfillment_type"],
            "when": {"path": "fulfillment_type", "equals": "store_pickup"},
            "require": ["selected_chemist_id"],
        },
        {
            "rule": "unique_by",
            "description": "Each product id may appear only once.",
            "fields": ["products[].id"],
            "array": "products",
            "key": "id",
        },
        {
            "rule": "at_least_one_of",
            "description": "A new address needs pincode or zip_code.",
            "fields": ["address.pincode", "address.zip_code"],
            "scope": "address",
            "groups": _either("pincode", "zip_code"),
        },
        {
            # Files fetched from prescription_urls are checked by the server. How the type
            # is told isn't specified: accept a matching content type or file extension.
            "rule": "file_limits",
            "description": "Each prescription file must be smaller than 7 MB and be PDF, PNG "
            "or JPEG; files fetched from prescription_urls must also be smaller than 7 MB and "
            "served as application/pdf, image/png or image/jpeg.",
            "fields": ["prescription_files", "prescription_urls"],
            "files": "prescription_files[]",
            "max_bytes_exclusive": 7 * MB,
            "content_types": ["application/pdf", "image/png", "image/jpeg"],
            "extensions": ["pdf", "png", "jpg", "jpeg"],
            "type_match": "either",
        },
        {
            "rule": "no_conflicting_pincode",
            "description": "A new address's line1, line2, city, state and country must not "
            "contain a 6-digit pincode other than its pincode.",
            "fields": [
                "address.line1",
                "address.line2",
                "address.city",
                "address.state",
                "address.country",
                "address.pincode",
            ],
            "address": "address",
            "text": ["line1", "line2", "city", "state", "country"],
            "pincode": ["pincode", "zip_code"],
        },
    ],
    "getOrderPaymentDetails": [
        {
            # "must match the store saved on the cart" depends on stored data.
            "rule": "required_if",
            "description": "selected_chemist_id is required when selected_delivery_option is "
            "store_pickup (and must match the store saved on the cart).",
            "fields": ["selected_chemist_id", "selected_delivery_option"],
            "when": {"path": "selected_delivery_option", "equals": "store_pickup"},
            "require": ["selected_chemist_id"],
        }
    ],
    "confirmOrder": [
        {
            # "must equal the order's amount_to_collect" depends on stored data.
            "rule": "positive_decimal",
            "description": "partner_collected_amount must be a decimal greater than 0 (it must "
            "also equal the order's amount_to_collect).",
            "fields": ["partner_collected_amount"],
            "path": "partner_collected_amount",
        }
    ],
    "getCustomerWallet": [
        {
            "rule": "at_least_one_of",
            "description": "Send api_customer_id or customer_id.",
            "fields": ["api_customer_id", "customer_id"],
            "groups": _either("api_customer_id", "customer_id"),
        }
    ],
    "listCustomerPlans": [
        {
            "rule": "at_least_one_of",
            "description": "Send api_customer_id or customer_id.",
            "fields": ["api_customer_id", "customer_id"],
            "groups": _either("api_customer_id", "customer_id"),
        }
    ],
    "createPreRegistrations": [
        {**MAX_250_ROWS, "description": "At most 250 rows in employees and dependants together."},
        {
            "rule": "at_least_one_of",
            "description": "Each employee needs a non-blank email or employee_code.",
            "fields": ["employees[].email", "employees[].employee_code"],
            "scope": "employees[]",
            "groups": _either("email", "employee_code"),
        },
        {
            "rule": "at_least_one_of",
            "description": "Each dependant needs guardian_email, or company_id together with "
            "guardian_employee_code.",
            "fields": [
                "dependants[].guardian_email",
                "dependants[].company_id",
                "dependants[].guardian_employee_code",
            ],
            "scope": "dependants[]",
            "groups": [["guardian_email"], ["company_id", "guardian_employee_code"]],
        },
        {
            "rule": "relative_date",
            "description": "date_of_birth (when not blank) must not be after today.",
            "fields": ["employees[].date_of_birth", "dependants[].date_of_birth"],
            "paths": ["employees[].date_of_birth", "dependants[].date_of_birth"],
            "format": "dd-mm-yyyy",
            "compare": "on_or_before",
            "base": "today",
        },
    ],
    "updatePreRegistrations": [
        {**MAX_250_ROWS, "description": "At most 250 rows in employees and dependants together."},
        {
            "rule": "at_least_one_of",
            "description": "Each employee needs email, or company_id together with employee_code.",
            "fields": ["employees[].email", "employees[].company_id", "employees[].employee_code"],
            "scope": "employees[]",
            "groups": [["email"], ["company_id", "employee_code"]],
        },
        {
            "rule": "at_least_one_of",
            "description": "Each dependant needs api_customer_id, dependent_code or mobile_number.",
            "fields": [
                "dependants[].api_customer_id",
                "dependants[].dependent_code",
                "dependants[].mobile_number",
            ],
            "scope": "dependants[]",
            "groups": _either("api_customer_id", "dependent_code", "mobile_number"),
        },
    ],
    "deactivatePreRegistrations": [
        {**MAX_250_ROWS, "description": "At most 250 entries in employees and dependants together."}
    ],
}


class SpecError(Exception):
    pass


def _resolve(spec: dict[str, Any], node: Any) -> Any:
    while isinstance(node, dict) and "$ref" in node:
        extra = set(node) - {"$ref"} - ANNOTATIONS
        if extra:
            raise SpecError(f"$ref with sibling keywords {sorted(extra)} is not supported")
        target: Any = spec
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def _schema(spec: dict[str, Any], node: Any, where: str) -> dict[str, Any]:
    """Resolve refs, drop annotations and fail on anything the validator can't check."""
    node = _resolve(spec, node)
    if not isinstance(node, dict):
        raise SpecError(f"{where}: schema is not an object")
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in ANNOTATIONS:
            continue
        if key not in KEYWORDS:
            raise SpecError(f"{where}: unsupported schema keyword {key!r}")
        if key == "properties":
            out[key] = {k: _schema(spec, v, f"{where}.{k}") for k, v in value.items()}
        elif key == "items":
            out[key] = _schema(spec, value, f"{where}[]")
        elif key in ("allOf", "anyOf", "oneOf"):
            out[key] = [_schema(spec, v, f"{where}<{key}>") for v in value]
        elif key == "format":
            if value not in FORMATS:
                raise SpecError(f"{where}: unsupported format {value!r}")
            out[key] = value
        elif key == "pattern":
            re.compile(value)
            out[key] = value
        else:
            out[key] = value
    return out


def _form_tokens(name: str) -> list[str]:
    """``customers[][dob]`` -> ``["customers", "[]", "dob"]``."""
    match = re.fullmatch(r"([^\[\]]+)((?:\[[^\[\]]*\])*)", name)
    if not match:
        raise SpecError(f"unsupported form field name {name!r}")
    return [match.group(1)] + [
        "[]" if t == "" else t for t in re.findall(r"\[([^\[\]]*)\]", match.group(2))
    ]


def _nest(
    target: dict[str, Any], tokens: list[str], schema: dict[str, Any], required: bool
) -> None:
    props = target.setdefault("properties", {})
    name, rest = tokens[0], tokens[1:]
    if required and name not in target.setdefault("required", []):
        target["required"].append(name)
    if not rest:
        props[name] = schema
    elif rest == ["[]"]:
        props[name] = (
            schema if schema.get("type") == "array" else {"type": "array", "items": schema}
        )
    elif rest[0] == "[]":
        array = props.setdefault(name, {"type": "array", "items": {"type": "object"}})
        _nest(array["items"], rest[1:], schema, required)
    else:
        _nest(props.setdefault(name, {"type": "object"}), rest, schema, required)


def _nested_form_schema(flat: dict[str, Any], where: str) -> dict[str, Any]:
    """Rewrite a flat multipart schema into the nested shape the server parses it into."""
    if set(flat) - {"type", "properties", "required"} or flat.get("type") != "object":
        raise SpecError(f"{where}: unsupported multipart schema")
    out: dict[str, Any] = {"type": "object"}
    required = set(flat.get("required", []))
    for name, schema in flat.get("properties", {}).items():
        _nest(out, _form_tokens(name), schema, name in required)
    return out


def _rules(op_id: str, spec_rules: list[dict[str, Any]], kinds: set[str]) -> list[dict[str, Any]]:
    table = RULES.get(op_id, [])
    if len(spec_rules) != len(table):
        raise SpecError(
            f"{op_id}: the spec has {len(spec_rules)} x-hlthstack-rules, RULES has {len(table)}"
        )
    for index, (rule, mine) in enumerate(zip(spec_rules, table)):
        if rule.get("rule") not in kinds:
            raise SpecError(f"{op_id} rule {index}: unknown rule kind {rule.get('rule')!r}")
        for key in ("rule", "description", "fields"):
            if rule.get(key) != mine[key]:
                raise SpecError(
                    f"{op_id} rule {index}: {key} differs from RULES; update RULES\n"
                    f"  spec:  {rule.get(key)!r}\n  RULES: {mine[key]!r}"
                )
    return [dict(r) for r in table]


def build() -> dict[str, Any]:
    spec = yaml.safe_load(SPEC.read_text())
    kinds = set(spec.get("x-hlthstack-rule-kinds", {}))
    if kinds != RULE_KINDS:
        raise SpecError(f"x-hlthstack-rule-kinds changed: {sorted(kinds ^ RULE_KINDS)}")
    operations: dict[str, Any] = {}
    for path_template, item in spec["paths"].items():
        for method, op in item.items():
            if method == "parameters":
                continue
            op_id = op["operationId"]
            entry: dict[str, Any] = {"path": path_template, "parameters": [], "body": {}}
            for raw in item.get("parameters", []) + op.get("parameters", []):
                param = _resolve(spec, raw)
                if param["in"] == "header":
                    continue  # set by the client, not by method arguments
                if param["in"] not in ("path", "query"):
                    raise SpecError(f"{op_id}: unsupported parameter location {param['in']!r}")
                entry["parameters"].append(
                    {
                        "name": param["name"],
                        "in": param["in"],
                        "required": bool(param.get("required", False)),
                        "schema": _schema(spec, param.get("schema", {}), param["name"]),
                    }
                )
            body = _resolve(spec, op.get("requestBody"))
            if body:
                entry["body_required"] = bool(body.get("required", False))
                for content_type, content in body["content"].items():
                    schema = _schema(spec, content["schema"], f"{op_id} body")
                    if content_type == "multipart/form-data":
                        schema = _nested_form_schema(schema, f"{op_id} body")
                    elif content_type != "application/json":
                        raise SpecError(f"{op_id}: unsupported content type {content_type!r}")
                    entry["body"][content_type] = schema
            entry["rules"] = _rules(op_id, op.get("x-hlthstack-rules", []), kinds)
            operations[op_id] = entry
    unused = set(RULES) - set(operations)
    if unused:
        raise SpecError(f"RULES names operations that are not in the spec: {sorted(unused)}")
    return operations


HEADER = '''\
# This file is generated from openapi/openapi.yaml by scripts/build_validation.py. Do not edit.
"""Request schemas and rules per operationId, read by ``_validation.py``."""

from typing import Any

'''
ASSIGN = "OPERATIONS: dict[str, Any] = "
WIDTH = 100


def _literal(value: Any) -> str:
    """A one-line Python literal, quoted the way ``ruff format`` quotes it."""
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_literal(k)}: {_literal(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_literal(v) for v in value) + "]"
    if isinstance(value, str):
        if '"' in value and "'" not in value:
            return repr(value)
        return json.dumps(value, ensure_ascii=False)
    if value is None or isinstance(value, (bool, int, float)):
        return repr(value)
    raise SpecError(f"cannot write {type(value).__name__} values")


def _format(value: Any, indent: int, used: int) -> str:
    """Format like ``ruff format``: one line when it fits, else one item per line."""
    flat = _literal(value)
    if not isinstance(value, (dict, list)) or not value or indent + used + len(flat) <= WIDTH:
        return flat
    pad = " " * (indent + 4)
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            key = f"{_literal(k)}: "
            lines.append(f"{pad}{key}{_format(v, indent + 4, len(key) + 1)},")
        open_, close = "{", "}"
    else:
        lines = [f"{pad}{_format(v, indent + 4, 1)}," for v in value]
        open_, close = "[", "]"
    return open_ + "\n" + "\n".join(lines) + "\n" + " " * indent + close


def generate() -> str:
    return HEADER + ASSIGN + _format(build(), 0, len(ASSIGN)) + "\n"


def main() -> int:
    try:
        output = generate()
    except SpecError as exc:
        print(f"build_validation: {exc}", file=sys.stderr)
        return 2
    if "--check" in sys.argv[1:]:
        if not TARGET.exists() or TARGET.read_text() != output:
            print(f"{TARGET.name} is out of date; run python scripts/build_validation.py")
            return 1
        return 0
    TARGET.write_text(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
