"""Client-side request validation.

Checks the request a method is about to send (path, query and body, after the method's
conversions) against the operation's schemas and ``x-hlthstack-rules`` from the OpenAPI
spec, compiled into ``_validation_spec.py`` by ``scripts/build_validation.py``. Only the
JSON Schema keywords and rule kinds that spec uses are implemented; the build script fails
on anything else. Checks that need stored data (plan benefits, slot availability, ...) are
left to the server.
"""

import datetime as dt
import functools
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, NamedTuple, Optional
from urllib.parse import unquote

from ._exceptions import ValidationErrorDetail
from ._validation_spec import OPERATIONS

__all__ = ["UploadFile", "form_to_dict", "validate_request"]

# Dates in rules are compared with today's date in India, and a date-time without an
# offset is read as IST, as the server does.
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "IST")

Detail = ValidationErrorDetail
Part = tuple[str, tuple[Optional[str], bytes, Optional[str]]]


class UploadFile(NamedTuple):
    """A file in a multipart request, as the validator sees it."""

    filename: str
    content_type: str
    size: int


_MISSING: Any = object()


def validate_request(
    operation_id: str,
    *,
    url: str,
    params: Optional[Mapping[str, Any]],
    json: Any,
    files: Optional[Sequence[Part]],
    now: dt.datetime,
) -> list[Detail]:
    """Return every problem with the request ``operation_id`` is about to send."""
    op = OPERATIONS[operation_id]
    errors: list[Detail] = []
    instance: dict[str, Any] = {}

    path_values = _path_values(op["path"], url)
    for param in op["parameters"]:
        name = param["name"]
        source = path_values if param["in"] == "path" else (params or {})
        if source.get(name) is None:
            if param["required"]:
                errors.append(_detail(name, "is required", "required"))
            continue
        value = _deserialize(source[name], param["schema"])
        instance[name] = value
        errors.extend(_check(value, param["schema"], name))

    if op["body"]:
        content_type, body = (
            ("multipart/form-data", form_to_dict(files))
            if files is not None
            else ("application/json", json)
        )
        if body is None:
            if op.get("body_required"):
                errors.append(_detail("", "a request body is required", "required"))
        elif content_type in op["body"]:
            errors.extend(_check(body, op["body"][content_type], ""))
            if isinstance(body, Mapping):
                instance.update(body)

    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    schema_paths = {e["path"] for e in errors}
    for rule in op["rules"]:
        for detail in _RULES[rule["rule"]](instance, rule, now):
            # A field that already failed its schema check is not also reported by a rule.
            if detail["path"] not in schema_paths:
                errors.append(detail)
    return errors


# --------------------------------------------------------------------------- request shape


@functools.cache
def _path_pattern(template: str) -> "re.Pattern[str]":
    parts = re.split(r"\{([^}]+)\}", template)
    regex = "".join(
        re.escape(part) if i % 2 == 0 else f"(?P<{part}>[^/]*)" for i, part in enumerate(parts)
    )
    return re.compile(regex)


def _path_values(template: str, url: str) -> dict[str, str]:
    match = _path_pattern(template).fullmatch(url)
    if match is None:
        raise RuntimeError(f"request path {url!r} does not match {template!r}")
    return {k: unquote(v) for k, v in match.groupdict().items()}


def _deserialize(value: Any, schema: Mapping[str, Any]) -> Any:
    """Read a path or query string as the type its schema declares, as the server does."""
    types = _types(schema)
    if not isinstance(value, str) or not types or "string" in types:
        return value
    if "integer" in types and re.fullmatch(r"[+-]?[0-9]+", value):
        return int(value)
    if "number" in types:
        try:
            number = float(value)
        except ValueError:
            return value
        return number if math.isfinite(number) else value
    if "boolean" in types and value in ("true", "false"):
        return value == "true"
    return value


def _form_tokens(name: str) -> list[str]:
    """``customers[][dob]`` -> ``["customers", "[]", "dob"]``."""
    head, _, rest = name.partition("[")
    tokens = [head]
    if rest:
        tokens += ["[]" if t == "" else t for t in re.findall(r"\[([^\[\]]*)\]", "[" + rest)]
    return tokens


def _insert(target: dict[str, Any], tokens: list[str], value: Any) -> None:
    name, rest = tokens[0], tokens[1:]
    if not rest:
        target[name] = value
    elif rest == ["[]"]:
        target.setdefault(name, []).append(value)
    elif rest[0] == "[]":
        items = target.setdefault(name, [])
        # A new item starts when its first key repeats (``files[][name]``, ``files[][value]``).
        if not items or not isinstance(items[-1], dict) or rest[1] in items[-1]:
            items.append({})
        _insert(items[-1], rest[1:], value)
    else:
        _insert(target.setdefault(name, {}), rest, value)


def form_to_dict(parts: Optional[Iterable[Part]]) -> dict[str, Any]:
    """Nest multipart fields the way the server parses bracketed names."""
    out: dict[str, Any] = {}
    for name, (filename, data, content_type) in parts or ():
        value: Any = (
            data.decode("utf-8", "replace")
            if filename is None
            else UploadFile(filename, content_type or "", len(data))
        )
        _insert(out, _form_tokens(name), value)
    return out


# --------------------------------------------------------------------------- JSON Schema


def _detail(path: str, message: str, rule: str) -> Detail:
    return {"path": path, "message": message, "rule": rule}


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _types(schema: Mapping[str, Any]) -> list[str]:
    types = schema.get("type")
    if types is None:
        return []
    return [types] if isinstance(types, str) else list(types)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_type(value: Any, name: str, schema: Mapping[str, Any]) -> bool:
    if name == "string":
        return isinstance(value, str) or (
            isinstance(value, UploadFile) and "contentMediaType" in schema
        )
    if name == "integer":
        return _is_number(value) and float(value).is_integer()
    if name == "number":
        return _is_number(value)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "object":
        return isinstance(value, Mapping)
    if name == "array":
        return isinstance(value, (list, tuple))
    raise ValueError(f"unknown JSON Schema type {name!r}")


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, UploadFile):
        return "file"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    return type(value).__name__


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return bool(a == b)


def _show(value: Any) -> str:
    return (
        "null" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
    )


_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_DATE_TIME = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]+)?"
    r"([Zz]|[+-][0-9]{2}:[0-9]{2})?"
)
_UUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")
_URI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:[^\s]*")


def _parse_date(value: str) -> Optional[dt.date]:
    match = _DATE.fullmatch(value)
    if not match:
        return None
    try:
        return dt.date(*(int(g) for g in match.groups()))
    except ValueError:
        return None


def _parse_date_time(value: str) -> Optional[dt.datetime]:
    match = _DATE_TIME.fullmatch(value)
    if not match:
        return None
    year, month, day, hour, minute, second = (int(g) for g in match.groups()[:6])
    fraction, offset = match.group(7), match.group(8)
    if offset is None:
        tz = IST
    elif offset in ("Z", "z"):
        tz = dt.timezone.utc
    else:
        hours, minutes = int(offset[1:3]), int(offset[4:6])
        if hours > 23 or minutes > 59:
            return None
        sign = -1 if offset[0] == "-" else 1
        tz = dt.timezone(sign * dt.timedelta(hours=hours, minutes=minutes))
    micro = int((fraction[1:] + "000000")[:6]) if fraction else 0
    try:
        return dt.datetime(year, month, day, hour, minute, second, micro, tzinfo=tz)
    except ValueError:
        return None


_FORMATS: dict[str, tuple[Callable[[str], bool], str]] = {
    "date": (lambda v: _parse_date(v) is not None, "must be a date (YYYY-MM-DD)"),
    # The offset is optional: the API reads a date-time without one as IST.
    "date-time": (
        lambda v: _parse_date_time(v) is not None,
        "must be an ISO 8601 date-time (for example 2026-01-15T02:30:00Z)",
    ),
    "uri": (lambda v: _URI.fullmatch(v) is not None, "must be an absolute URI"),
    "uuid": (lambda v: _UUID.fullmatch(v) is not None, "must be a UUID"),
}


@functools.cache
def _regex(pattern: str) -> "re.Pattern[str]":
    return re.compile(pattern)


def _check(value: Any, schema: Mapping[str, Any], path: str) -> list[Detail]:
    """Every way ``value`` fails ``schema`` (the keywords the spec uses)."""
    types = _types(schema)
    if types and not any(_is_type(value, t, schema) for t in types):
        expected = " or ".join(types)
        return [_detail(path, f"must be {expected}, not {_type_name(value)}", "type")]
    out: list[Detail] = []
    if "enum" in schema and not any(_same(value, e) for e in schema["enum"]):
        allowed = ", ".join(_show(e) for e in schema["enum"])
        out.append(_detail(path, f"must be one of: {allowed}", "enum"))
    if isinstance(value, str):
        if "pattern" in schema and not _regex(schema["pattern"]).search(value):
            out.append(_detail(path, f"must match the pattern {schema['pattern']}", "pattern"))
        if "minLength" in schema and len(value) < schema["minLength"]:
            n = schema["minLength"]
            out.append(_detail(path, f"must be at least {n} characters long", "minLength"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            n = schema["maxLength"]
            out.append(_detail(path, f"must be at most {n} characters long", "maxLength"))
        if "format" in schema:
            valid, message = _FORMATS[schema["format"]]
            if not valid(value):
                out.append(_detail(path, message, "format"))
    if _is_number(value):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(_detail(path, f"must be at least {schema['minimum']}", "minimum"))
        if "maximum" in schema and value > schema["maximum"]:
            out.append(_detail(path, f"must be at most {schema['maximum']}", "maximum"))
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            bound = schema["exclusiveMinimum"]
            out.append(_detail(path, f"must be greater than {bound}", "exclusiveMinimum"))
    if isinstance(value, Mapping):
        for name in schema.get("required", []):
            if name not in value:
                out.append(_detail(_join(path, name), "is required", "required"))
        for name, sub in schema.get("properties", {}).items():
            if name in value:
                out.extend(_check(value[name], sub, _join(path, name)))
    if isinstance(value, (list, tuple)):
        if "minItems" in schema and len(value) < schema["minItems"]:
            n = schema["minItems"]
            out.append(_detail(path, f"must have at least {n} item(s)", "minItems"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            n = schema["maxItems"]
            out.append(_detail(path, f"must have at most {n} item(s)", "maxItems"))
        if "items" in schema:
            for i, item in enumerate(value):
                out.extend(_check(item, schema["items"], f"{path}[{i}]"))
    for sub in schema.get("allOf", []):
        out.extend(_check(value, sub, path))
    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            out.extend(_check_alternatives(value, schema[keyword], path, keyword))
    return out


def _check_alternatives(
    value: Any, schemas: list[Mapping[str, Any]], path: str, keyword: str
) -> list[Detail]:
    results = [_check(value, s, path) for s in schemas]
    passing = sum(1 for r in results if not r)
    if keyword == "oneOf" and passing > 1:
        return [_detail(path, "matches more than one of the allowed forms", keyword)]
    if passing:
        return []
    # When only one alternative has the value's type, its errors are the useful ones.
    typed = [r for s, r in zip(schemas, results) if r[0]["rule"] != "type"]
    if len(typed) == 1:
        return typed[0]
    return [_detail(path, "does not match any of the allowed forms", keyword)]


# --------------------------------------------------------------------------- rules

Rule = Mapping[str, Any]


def _get(root: Any, path: str) -> Any:
    for key in path.split("."):
        if not isinstance(root, Mapping) or key not in root:
            return _MISSING
        root = root[key]
    return root


def _find(root: Any, path: str) -> list[tuple[str, Any]]:
    """Every value at a dotted path; ``name[]`` steps into each item of an array."""
    nodes: list[tuple[str, Any]] = [("", root)]
    for segment in path.split("."):
        each = segment.endswith("[]")
        name = segment[:-2] if each else segment
        found: list[tuple[str, Any]] = []
        for at, node in nodes:
            if not isinstance(node, Mapping) or name not in node:
                continue
            child, child_path = node[name], _join(at, name)
            if not each:
                found.append((child_path, child))
            elif isinstance(child, (list, tuple)):
                found.extend((f"{child_path}[{i}]", item) for i, item in enumerate(child))
        nodes = found
    return nodes


def _blank(value: Any) -> bool:
    if value is _MISSING or value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, Mapping)):
        return len(value) == 0
    return False


def _sent(value: Any) -> bool:
    return value is not _MISSING and value is not None


def _holds(instance: Mapping[str, Any], condition: Optional[Mapping[str, Any]]) -> bool:
    if condition is None:
        return True
    value = _get(instance, condition["path"])
    if "equals" in condition:
        return _sent(value) and _same(value, condition["equals"])
    if "not_equals" in condition:
        return not (_sent(value) and _same(value, condition["not_equals"]))
    if "blank" in condition:
        return _blank(value) is bool(condition["blank"])
    raise ValueError(f"unknown rule condition {condition!r}")


def _required_if(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    if not _holds(instance, rule["when"]):
        return []
    return [
        _detail(field, rule["description"], rule["rule"])
        for field in rule["require"]
        if _blank(_get(instance, field))
    ]


def _allowed_only_if(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    if _holds(instance, rule["when"]):
        return []
    return [
        _detail(field, rule["description"], rule["rule"])
        for field in rule["allowed"]
        if _sent(_get(instance, field))
    ]


def _at_least_one_of(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    scopes = _find(instance, rule["scope"]) if rule.get("scope") else [("", instance)]
    out = []
    for path, node in scopes:
        if not isinstance(node, Mapping):
            continue
        if not any(all(not _blank(_get(node, f)) for f in group) for group in rule["groups"]):
            out.append(_detail(path, rule["description"], rule["rule"]))
    return out


def _mutually_exclusive(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    sent = [f for f in rule["exclusive"] if _sent(_get(instance, f))]
    if len(sent) < 2:
        return []
    return [_detail(sent[-1], rule["description"], rule["rule"])]


def _unique_by(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    items = _get(instance, rule["array"])
    if not isinstance(items, (list, tuple)):
        return []
    seen: dict[str, int] = {}
    out = []
    key = rule["key"]
    for i, item in enumerate(items):
        if not isinstance(item, Mapping) or not _sent(item.get(key, _MISSING)):
            continue
        value = _show(item[key])
        if value in seen:
            first = f"{rule['array']}[{seen[value]}].{key}"
            message = f"same value as {first}. {rule['description']}"
            out.append(_detail(f"{rule['array']}[{i}].{key}", message, rule["rule"]))
        else:
            seen[value] = i
    return out


_DMY = re.compile(r"([0-9]{2})([-/])([0-9]{2})\2([0-9]{4})")


def _rule_date(value: str, fmt: str) -> Any:
    if fmt == "date":
        return _parse_date(value)
    if fmt == "date-time":
        return _parse_date_time(value)
    match = _DMY.fullmatch(value.strip())  # dd-mm-yyyy or dd/mm/yyyy
    if not match:
        return None
    try:
        return dt.date(int(match.group(4)), int(match.group(3)), int(match.group(1)))
    except ValueError:
        return None


def _add_years(day: dt.date, years: int) -> dt.date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 February
        return day.replace(year=day.year + years, day=28)


def _relative_date(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    if not _holds(instance, rule.get("when")):
        return []
    out = []
    for field in rule["paths"]:
        for path, value in _find(instance, field):
            parsed = _rule_date(value, rule["format"]) if isinstance(value, str) else None
            if parsed is None:
                continue  # blank or malformed: the schema reports it
            if rule["base"] == "now" and rule["compare"] == "after":
                if parsed <= now:
                    out.append(_detail(path, rule["description"], rule["rule"]))
            elif rule["base"] == "today" and rule["compare"] == "on_or_before":
                bound = _add_years(now.astimezone(IST).date(), rule.get("years", 0))
                if parsed > bound:
                    message = f"must be on or before {bound.isoformat()}. {rule['description']}"
                    out.append(_detail(path, message, rule["rule"]))
            else:
                raise ValueError(f"unknown relative_date comparison in {rule!r}")
    return out


_PINCODE = re.compile(r"\b[0-9]{6}\b")


def _no_conflicting_pincode(
    instance: Mapping[str, Any], rule: Rule, now: dt.datetime
) -> list[Detail]:
    address = _get(instance, rule["address"])
    if not isinstance(address, Mapping) or not _holds(instance, rule.get("when")):
        return []
    country = address.get("country")
    if not (_blank(country) or (isinstance(country, str) and country.strip().lower() == "india")):
        return []
    pincode = next((address[k] for k in rule["pincode"] if not _blank(address.get(k))), None)
    if pincode is None:
        return []  # nothing to compare against
    out = []
    for field in rule["text"]:
        text = address.get(field)
        if not isinstance(text, str):
            continue
        if any(m.group() != str(pincode).strip() for m in _PINCODE.finditer(text)):
            message = f"contains a 6-digit number other than the pincode. {rule['description']}"
            out.append(_detail(_join(rule["address"], field), message, rule["rule"]))
    return out


def _file_limits(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    out = []
    for path, file in _find(instance, rule["files"]):
        if not isinstance(file, UploadFile):
            continue
        extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        content_type = file.content_type.split(";")[0].strip().lower()
        problems = []
        if "extensions" in rule and extension not in rule["extensions"]:
            problems.append(f"file name {file.filename!r} has a disallowed extension")
        if "content_types" in rule and content_type not in rule["content_types"]:
            problems.append(f"content type {content_type or 'none'!r} is not allowed")
        if rule.get("type_match") == "either" and len(problems) < 2:
            problems = []  # a matching extension or content type is enough
        too_big = ("max_bytes" in rule and file.size > rule["max_bytes"]) or (
            "max_bytes_exclusive" in rule and file.size >= rule["max_bytes_exclusive"]
        )
        if too_big:
            problems.append(f"file is too large ({file.size} bytes)")
        for problem in problems:
            out.append(_detail(path, f"{problem}. {rule['description']}", rule["rule"]))
    return out


def _item_count(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    values = [_get(instance, p) for p in rule["paths"]]
    count = sum(len(v) for v in values if isinstance(v, (list, tuple)))
    path = rule["paths"][0] if len(rule["paths"]) == 1 else ""
    if count < rule.get("min", 0) or count > rule.get("max", math.inf):
        return [_detail(path, f"has {count} item(s). {rule['description']}", rule["rule"])]
    return []


def _positive_decimal(instance: Mapping[str, Any], rule: Rule, now: dt.datetime) -> list[Detail]:
    value = _get(instance, rule["path"])
    if not _sent(value):
        return []
    try:
        number = Decimal(value.strip()) if isinstance(value, str) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        number = Decimal("NaN")
    if number.is_finite() and number > 0:
        return []
    return [_detail(rule["path"], rule["description"], rule["rule"])]


_RULES: dict[str, Callable[[Mapping[str, Any], Rule, dt.datetime], list[Detail]]] = {
    "required_if": _required_if,
    "at_least_one_of": _at_least_one_of,
    "mutually_exclusive": _mutually_exclusive,
    "allowed_only_if": _allowed_only_if,
    "unique_by": _unique_by,
    "relative_date": _relative_date,
    "no_conflicting_pincode": _no_conflicting_pincode,
    "file_limits": _file_limits,
    "item_count": _item_count,
    "positive_decimal": _positive_decimal,
}
