"""Safe shared criteria for the visitor-log Reward Kit dimensions."""

import json
import math
import os
import re
import stat
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from rewardkit import criterion

MAX_DELIVERABLE_BYTES = 1_000_000
PUBLIC_FIELDS = frozenset(
    {
        "requests_reviewed",
        "conversations_reviewed",
        "same_day_breach_ts",
        "same_day_breaches",
        "returned_same_day",
        "returned_next_working_day",
        "unresolved_by_followup",
        "returned_next_working_day_ts",
        "unresolved_ts",
        "custody_audit",
    }
)
COUNT_FIELDS = (
    "requests_reviewed",
    "conversations_reviewed",
    "returned_same_day",
    "returned_next_working_day",
    "unresolved_by_followup",
)
TIMESTAMP_FIELDS = (
    "same_day_breach_ts",
    "returned_next_working_day_ts",
    "unresolved_ts",
)
BREACH_FIELD_ORDER = ("ts", "date", "asked_by", "asked_of", "resolution")
BREACH_FIELDS = frozenset(BREACH_FIELD_ORDER)
CUSTODY_FIELDS = (
    "request_ts",
    "request_date",
    "asked_by",
    "asked_of",
    "first_return_surface",
    "first_return_id",
    "first_return_at",
    "outcome",
)
RESOLUTIONS = frozenset({"next_working_day", "unresolved"})
CUSTODY_OUTCOMES = frozenset({"same_day", "next_working_day", "unresolved"})
RETURN_SURFACES = frozenset({"slack", "gmail", "none"})


def _instant(value: str) -> str | None:
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.utcoffset() is None:
        return None
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


def _finite_json(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite_json(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _finite_json(item) for key, item in value.items()
        )
    return value is None or isinstance(value, bool | int | str)


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS:
        return False
    if any(
        isinstance(document.get(field), bool)
        or not isinstance(document.get(field), int)
        for field in COUNT_FIELDS
    ):
        return False
    for field in TIMESTAMP_FIELDS:
        values = document.get(field)
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            return False
    breaches = document.get("same_day_breaches")
    if not isinstance(breaches, list):
        return False
    for breach in breaches:
        if not isinstance(breach, dict) or set(breach) != BREACH_FIELDS:
            return False
        if not all(
            isinstance(breach.get(field), str)
            for field in ("ts", "date", "asked_by", "asked_of", "resolution")
        ):
            return False
        if breach["resolution"] not in RESOLUTIONS:
            return False
    custody_audit = document.get("custody_audit")
    if not isinstance(custody_audit, list):
        return False
    for record in custody_audit:
        if not isinstance(record, dict) or set(record) != set(CUSTODY_FIELDS):
            return False
        if not all(isinstance(record.get(field), str) for field in CUSTODY_FIELDS):
            return False
        surface = record["first_return_surface"]
        return_id = record["first_return_id"]
        return_at = record["first_return_at"]
        if surface not in RETURN_SURFACES or record["outcome"] not in CUSTODY_OUTCOMES:
            return False
        if surface == "none":
            if return_id or return_at:
                return False
        elif not return_id or not return_at or _instant(return_at) is None:
            return False
    return True


def _submitted(workspace: Path, path: str) -> dict[str, object]:
    deliverable = workspace / path
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(deliverable, flags)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > MAX_DELIVERABLE_BYTES
        ):
            return {}
        with os.fdopen(descriptor, encoding="utf-8") as stream:
            descriptor = -1
            contents = stream.read(MAX_DELIVERABLE_BYTES + 1)
        if len(contents.encode()) > MAX_DELIVERABLE_BYTES:
            return {}
        loaded = json.loads(contents)
    except ValueError, UnicodeDecodeError, OSError, RecursionError:
        return {}
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        valid = (
            isinstance(loaded, dict)
            and _finite_json(loaded)
            and _valid_contract(loaded)
        )
    except RecursionError:
        return {}
    return loaded if valid else {}


def _canonical_value(value: object) -> object:
    if isinstance(value, list):
        return tuple(sorted((_canonical_value(item) for item in value), key=repr))
    if isinstance(value, dict):
        return tuple(
            sorted(
                (str(key).strip(), _canonical_value(item))
                for key, item in value.items()
            )
        )
    return str(value).strip()


def _canonical_field(field: str, value: object) -> object:
    if field == "first_return_at" and isinstance(value, str) and value:
        return _instant(value)
    return _canonical_value(value)


def _canonical(item: object, fields: tuple[str, ...] | None) -> str | None:
    if fields is None:
        if isinstance(item, dict | list):
            return None
        return repr(_canonical_value(item))
    if not isinstance(item, dict):
        return None
    return repr(tuple(_canonical_field(field, item.get(field, "")) for field in fields))


def _as_multiset(values: object, fields: tuple[str, ...] | None) -> Counter[str]:
    if not isinstance(values, list):
        return Counter()
    return Counter(
        member
        for member in (_canonical(item, fields) for item in values)
        if member is not None
    )


def _expected_multiset(
    expected: list[object], fields: tuple[str, ...] | None
) -> Counter[str]:
    return Counter(
        member
        for member in (_canonical(item, fields) for item in expected)
        if member is not None
    )


@criterion(description="{key}: F1 against the certified multiset", shared=True)
def set_f1(
    workspace: Path,
    path: str,
    key: str,
    expected: list[object],
    fields: tuple[str, ...] | None = None,
) -> float:
    got = _as_multiset(_submitted(workspace, path).get(key), fields)
    want = _expected_multiset(expected, fields)
    if not want:
        return 1.0 if not got else 0.0
    hits = sum((got & want).values())
    if not hits:
        return 0.0
    precision = hits / sum(got.values())
    recall = hits / sum(want.values())
    return 2 * precision * recall / (precision + recall)


@criterion(
    description="{key}: exactly the certified multiset, no misses and no extras",
    shared=True,
)
def exact_set(
    workspace: Path,
    path: str,
    key: str,
    expected: list[object],
    fields: tuple[str, ...] | None = None,
) -> bool:
    return _as_multiset(
        _submitted(workspace, path).get(key), fields
    ) == _expected_multiset(expected, fields)


@criterion(description="{key} within {tol} of {expected}", shared=True)
def numeric_close(
    workspace: Path, path: str, key: str, expected: float, tol: float = 0.0
) -> bool:
    value = _submitted(workspace, path).get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    try:
        actual = float(value)
        target = float(expected)
        tolerance = float(tol)
    except TypeError, ValueError, OverflowError:
        return False
    if not all(math.isfinite(number) for number in (actual, target, tolerance)):
        return False
    return abs(actual - target) <= tolerance


@criterion(description="{path} exactly follows the typed public contract", shared=True)
def exact_schema(workspace: Path, path: str) -> bool:
    return bool(_submitted(workspace, path))


@criterion(
    description="the custody ledger reconciles to every public count and partition",
    shared=True,
)
def custody_audit_reconciles(workspace: Path, path: str) -> bool:
    submitted = _submitted(workspace, path)
    audit = submitted.get("custody_audit")
    # An empty ledger reconciles with itself vacuously: every count is zero,
    # every partition is empty, and every equality below holds. That is not a
    # reconciliation, it is the absence of one, so it earns nothing.
    if not isinstance(audit, list) or not audit:
        return False
    request_ts = [record["request_ts"] for record in audit]
    if len(request_ts) != len(set(request_ts)):
        return False
    outcomes = Counter(record["outcome"] for record in audit)
    breaches = [record for record in audit if record["outcome"] != "same_day"]
    breach_records = [
        {
            "ts": record["request_ts"],
            "date": record["request_date"],
            "asked_by": record["asked_by"],
            "asked_of": record["asked_of"],
            "resolution": record["outcome"],
        }
        for record in breaches
    ]
    next_ts = [
        record["request_ts"]
        for record in audit
        if record["outcome"] == "next_working_day"
    ]
    unresolved_ts = [
        record["request_ts"] for record in audit if record["outcome"] == "unresolved"
    ]
    return (
        len(audit) == submitted.get("requests_reviewed")
        and outcomes["same_day"] == submitted.get("returned_same_day")
        and outcomes["next_working_day"] == submitted.get("returned_next_working_day")
        and outcomes["unresolved"] == submitted.get("unresolved_by_followup")
        and _as_multiset(submitted.get("same_day_breach_ts"), None)
        == _expected_multiset([record["request_ts"] for record in breaches], None)
        and _as_multiset(submitted.get("same_day_breaches"), BREACH_FIELD_ORDER)
        == _expected_multiset(breach_records, BREACH_FIELD_ORDER)
        and _as_multiset(submitted.get("returned_next_working_day_ts"), None)
        == _expected_multiset(next_ts, None)
        and _as_multiset(submitted.get("unresolved_ts"), None)
        == _expected_multiset(unresolved_ts, None)
    )


def _previous_nonspace(source: str, index: int) -> int:
    cursor = index - 1
    while cursor >= 0 and source[cursor].isspace():
        cursor -= 1
    return cursor


def _matching_open(source: str, close: int, opening: str, closing: str) -> int | None:
    depth = 0
    for cursor in range(close, -1, -1):
        if source[cursor] == closing:
            depth += 1
        elif source[cursor] == opening:
            depth -= 1
            if depth == 0:
                return cursor
    return None


def _ends_control_condition(source: str, close: int) -> bool:
    opening = _matching_open(source, close, "(", ")")
    if opening is None:
        return False
    cursor = _previous_nonspace(source, opening)
    end = cursor + 1
    while cursor >= 0 and (source[cursor].isalnum() or source[cursor] in "_$"):
        cursor -= 1
    return source[cursor + 1 : end] in {
        "catch",
        "for",
        "if",
        "switch",
        "while",
        "with",
    }


def _starts_regex_literal(source: str, index: int) -> bool:
    cursor = _previous_nonspace(source, index)
    if cursor < 0:
        return True
    previous = source[cursor]
    if previous in "([{=,:;!&|?+-*%^~<>":
        return True
    if previous == ")" and _ends_control_condition(source, cursor):
        return True
    if previous == "}":
        opening = _matching_open(source, cursor, "{", "}")
        before = _previous_nonspace(source, opening) if opening is not None else -1
        if before >= 0 and source[before] == ")":
            return _ends_control_condition(source, before)
    end = cursor + 1
    while cursor >= 0 and (source[cursor].isalnum() or source[cursor] in "_$"):
        cursor -= 1
    return source[cursor + 1 : end] in {
        "await",
        "case",
        "delete",
        "do",
        "else",
        "return",
        "throw",
        "typeof",
        "void",
        "yield",
    }


def _executable_javascript(source: str) -> str:
    code: list[str] = []
    state = "code"
    quote = ""
    regex_class = False
    template_expressions: list[int] = []
    index = 0
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and following == "/":
                code.extend((" ", " "))
                state = "line_comment"
                index += 2
                continue
            if char == "/" and following == "*":
                code.extend((" ", " "))
                state = "block_comment"
                index += 2
                continue
            if char == "/" and _starts_regex_literal("".join(code), len(code)):
                code.append(" ")
                state = "regex"
                regex_class = False
            elif char in {"'", '"'}:
                code.append(" ")
                state = "string"
                quote = char
            elif char == chr(96):
                code.append(" ")
                state = "template"
            elif template_expressions and char == "{":
                template_expressions[-1] += 1
                code.append(char)
            elif template_expressions and char == "}":
                template_expressions[-1] -= 1
                code.append(" ")
                if template_expressions[-1] == 0:
                    template_expressions.pop()
                    state = "template"
            else:
                code.append(char)
        elif state == "line_comment":
            code.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "code"
        elif state == "block_comment":
            code.append("\n" if char == "\n" else " ")
            if char == "*" and following == "/":
                code.append(" ")
                state = "code"
                index += 2
                continue
        elif state == "string":
            code.append("\n" if char == "\n" else " ")
            if char == "\\" and following:
                code.append("\n" if following == "\n" else " ")
                index += 2
                continue
            if char == quote:
                state = "code"
        elif state == "template":
            code.append("\n" if char == "\n" else " ")
            if char == "\\" and following:
                code.append("\n" if following == "\n" else " ")
                index += 2
                continue
            if char == chr(96):
                state = "code"
            elif char == "$" and following == "{":
                code.append(" ")
                template_expressions.append(1)
                state = "code"
                index += 2
                continue
        else:
            code.append("\n" if char == "\n" else " ")
            if char == "\\" and following:
                code.append("\n" if following == "\n" else " ")
                index += 2
                continue
            if char == "[" and not regex_class:
                regex_class = True
            elif char == "]" and regex_class:
                regex_class = False
            elif char == "/" and not regex_class:
                index += 1
                while index < len(source) and source[index].isalpha():
                    code.append(" ")
                    index += 1
                state = "code"
                continue
        index += 1
    return "".join(code)


def _unified_exec_source(name: str, arguments: object) -> str | None:
    if name != "exec" and not name.endswith("__exec"):
        return None
    if isinstance(arguments, str):
        return arguments
    if isinstance(arguments, dict):
        source = arguments.get("input")
        return source if isinstance(source, str) else None
    return None


@criterion(description="agent invoked {tool} at least {min_count} time(s)", shared=True)
def tool_invoked(
    workspace: Path,
    tool: str,
    min_count: int = 1,
    path: str = "/logs/agent/trajectory.json",
) -> bool:
    """Match native calls and executable calls inside Codex unified_exec."""

    del workspace
    trajectory = Path(path)
    if not trajectory.is_file():
        return False
    try:
        data = json.loads(trajectory.read_text())
    except json.JSONDecodeError, UnicodeDecodeError, OSError, RecursionError:
        return False
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        return False

    expression = re.compile(
        rf"\btools\.(?:[A-Za-z_][A-Za-z0-9_]*__)*{re.escape(tool)}\s*\("
    )
    count = 0
    for step in data["steps"]:
        if not isinstance(step, dict):
            continue
        calls = step.get("tool_calls") or []
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            name = str(call.get("function_name", ""))
            if name == tool or name.endswith(f"__{tool}"):
                count += 1
                continue
            source = _unified_exec_source(name, call.get("arguments", {}))
            if source is not None:
                count += len(expression.findall(_executable_javascript(source)))
    return count >= min_count
