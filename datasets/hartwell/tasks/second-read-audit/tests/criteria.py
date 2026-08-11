"""Safe criteria for the second-read Reward Kit dimensions."""

import json
import math
import os
import re
import stat
from collections import Counter
from pathlib import Path

from rewardkit import criterion

MAX_DELIVERABLE_BYTES = 1_000_000
PUBLIC_FIELDS = frozenset(
    {
        "requests_reviewed",
        "conversations_reviewed",
        "unanswered_request_ts",
        "unanswered_requests",
        "answered_same_day",
        "answered_next_working_day",
        "unanswered_by_deadline",
        "came_back_later",
        "unanswered_askers",
        "response_audit",
    }
)
REQUEST_FIELDS = frozenset({"ts", "date", "asked_by", "asked_of"})
RESPONSE_FIELDS = frozenset(
    {
        "request_ts",
        "request_date",
        "asked_by",
        "asked_of",
        "first_response_surface",
        "first_response_id",
        "first_response_at",
        "outcome",
    }
)


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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


def _valid_response(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != RESPONSE_FIELDS:
        return False
    if not all(isinstance(value.get(field), str) for field in RESPONSE_FIELDS):
        return False
    surface = value.get("first_response_surface")
    if surface not in {"slack", "gmail", "none"} or value.get("outcome") not in {
        "same_day",
        "next_working_day",
        "unanswered",
    }:
        return False
    first_response_id = value.get("first_response_id")
    first_response_at = value.get("first_response_at")
    if surface == "none":
        return first_response_id == "" and first_response_at == ""
    return first_response_id != "" and first_response_at != ""


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS or not all(
        _integer(document.get(key))
        for key in (
            "requests_reviewed",
            "conversations_reviewed",
            "answered_same_day",
            "answered_next_working_day",
            "unanswered_by_deadline",
        )
    ):
        return False
    for key in ("unanswered_request_ts", "came_back_later", "unanswered_askers"):
        values = document.get(key)
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            return False
    requests = document.get("unanswered_requests")
    if not isinstance(requests, list) or not all(
        isinstance(record, dict)
        and set(record) == REQUEST_FIELDS
        and all(isinstance(record.get(field), str) for field in REQUEST_FIELDS)
        for record in requests
    ):
        return False
    response_audit = document.get("response_audit")
    return isinstance(response_audit, list) and all(
        _valid_response(record) for record in response_audit
    )


def _submitted(workspace: Path, path: str) -> dict[str, object]:
    descriptor = -1
    try:
        descriptor = os.open(workspace / path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > MAX_DELIVERABLE_BYTES
        ):
            return {}
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            contents = stream.read(MAX_DELIVERABLE_BYTES + 1)
        if len(contents) > MAX_DELIVERABLE_BYTES:
            return {}
        loaded = json.loads(contents.decode())
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


def _seconds(value: object) -> str:
    return str(value).strip().split(".")[0]


def _f1(got: Counter[str], want: Counter[str]) -> float:
    hits = sum((got & want).values())
    if not hits:
        return 0.0
    precision, recall = hits / sum(got.values()), hits / sum(want.values())
    return 2 * precision * recall / (precision + recall)


def _seconds_counter(values: object) -> Counter[str]:
    return (
        Counter(_seconds(value) for value in values)
        if isinstance(values, list)
        else Counter()
    )


def _request_counter(values: object) -> Counter[str]:
    if not isinstance(values, list):
        return Counter()
    return Counter(
        f"{_seconds(record['ts'])}\0{record['date'].strip()}\0{record['asked_by'].strip().lower()}\0{record['asked_of'].strip().lower()}"
        for record in values
        if isinstance(record, dict) and set(record) == REQUEST_FIELDS
    )


def _truth_request_counter(expected: list[dict[str, str]]) -> Counter[str]:
    return Counter(
        f"{record['ts_prefix']}\0{record['date']}\0{record['asked_by'].lower()}\0{record['asked_of'].lower()}"
        for record in expected
    )


def _marker(value: str, marker_sets: list[list[str]]) -> str:
    lowered = value.strip().lower()
    for markers in marker_sets:
        if all(marker in lowered for marker in markers):
            return "\0".join(markers)
    return f"extra\0{lowered}"


def _marker_counter(values: object, marker_sets: list[list[str]]) -> Counter[str]:
    return (
        Counter(_marker(value, marker_sets) for value in values)
        if isinstance(values, list)
        else Counter()
    )


@criterion(description="{key} equals the certified count", shared=True)
def field_equals(workspace: Path, path: str, key: str, expected: object) -> bool:
    return _submitted(workspace, path).get(key) == expected


@criterion(description="timestamp multiset F1", shared=True)
def timestamp_f1(workspace: Path, path: str, key: str, expected: list[str]) -> float:
    return _f1(
        _seconds_counter(_submitted(workspace, path).get(key)), Counter(expected)
    )


@criterion(description="timestamp multiset exact", shared=True)
def timestamp_exact(workspace: Path, path: str, key: str, expected: list[str]) -> bool:
    return _seconds_counter(_submitted(workspace, path).get(key)) == Counter(expected)


@criterion(description="request record F1", shared=True)
def request_f1(workspace: Path, path: str, expected: list[dict[str, str]]) -> float:
    return _f1(
        _request_counter(_submitted(workspace, path).get("unanswered_requests")),
        _truth_request_counter(expected),
    )


@criterion(description="request records exact", shared=True)
def request_exact(workspace: Path, path: str, expected: list[dict[str, str]]) -> bool:
    return _request_counter(
        _submitted(workspace, path).get("unanswered_requests")
    ) == _truth_request_counter(expected)


@criterion(description="asker marker F1", shared=True)
def marker_f1(workspace: Path, path: str, expected: list[list[str]]) -> float:
    want = Counter("\0".join(markers) for markers in expected)
    return _f1(
        _marker_counter(_submitted(workspace, path).get("unanswered_askers"), expected),
        want,
    )


@criterion(description="asker markers exact", shared=True)
def marker_exact(workspace: Path, path: str, expected: list[list[str]]) -> bool:
    want = Counter("\0".join(markers) for markers in expected)
    return (
        _marker_counter(_submitted(workspace, path).get("unanswered_askers"), expected)
        == want
    )


def _response_counter(values: object) -> Counter[str]:
    if not isinstance(values, list):
        return Counter()
    return Counter(
        "\0".join(
            (
                record["request_ts"].strip(),
                record["request_date"].strip(),
                record["asked_by"].strip().lower(),
                record["asked_of"].strip().lower(),
                record["first_response_surface"],
                record["first_response_id"].strip(),
                record["first_response_at"].strip(),
                record["outcome"],
            )
        )
        for record in values
        if _valid_response(record)
    )


@criterion(description="complete first-response audit F1", shared=True)
def response_audit_f1(workspace: Path, path: str, expected: list[object]) -> float:
    return _f1(
        _response_counter(_submitted(workspace, path).get("response_audit")),
        _response_counter(expected),
    )


@criterion(description="exact certified first-response audit", shared=True)
def response_audit_exact(workspace: Path, path: str, expected: list[object]) -> bool:
    return _response_counter(
        _submitted(workspace, path).get("response_audit")
    ) == _response_counter(expected)


@criterion(
    description="response audit aggregates and exception sets reconcile", shared=True
)
def response_audit_reconciles(workspace: Path, path: str) -> bool:
    document = _submitted(workspace, path)
    response_audit = document.get("response_audit")
    if not isinstance(response_audit, list) or not all(
        _valid_response(record) for record in response_audit
    ):
        return False
    outcomes = Counter(record["outcome"] for record in response_audit)
    unanswered = [
        {
            "ts": record["request_ts"],
            "date": record["request_date"],
            "asked_by": record["asked_by"],
            "asked_of": record["asked_of"],
        }
        for record in response_audit
        if record["outcome"] == "unanswered"
    ]
    later = [
        record["request_ts"]
        for record in response_audit
        if record["outcome"] == "next_working_day"
    ]
    return (
        document.get("requests_reviewed") == len(response_audit)
        and document.get("answered_same_day") == outcomes["same_day"]
        and document.get("answered_next_working_day") == outcomes["next_working_day"]
        and document.get("unanswered_by_deadline") == outcomes["unanswered"]
        and _seconds_counter(document.get("unanswered_request_ts"))
        == _seconds_counter([record["ts"] for record in unanswered])
        and _request_counter(document.get("unanswered_requests"))
        == _request_counter(unanswered)
        and _seconds_counter(document.get("came_back_later")) == _seconds_counter(later)
        and Counter(
            str(value).strip().lower()
            for value in document.get("unanswered_askers", [])
        )
        == Counter(record["asked_by"].strip().lower() for record in unanswered)
    )


@criterion(description="exact public schema and types", shared=True)
def exact_schema(workspace: Path, path: str) -> bool:
    return bool(_submitted(workspace, path))


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


@criterion(description="agent invoked {tool}", shared=True)
def tool_invoked(
    workspace: Path, tool: str, path: str = "/logs/agent/trajectory.json"
) -> bool:
    del workspace
    try:
        data = json.loads(Path(path).read_text())
    except ValueError, UnicodeDecodeError, OSError, RecursionError:
        return False
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        return False
    expression = re.compile(rf"\btools\.(?:[A-Za-z_]\w*__)*{re.escape(tool)}\s*\(")
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
            source = _unified_exec_source(name, call.get("arguments", {}))
            if name == tool or name.endswith(f"__{tool}"):
                return True
            if source is not None and expression.search(_executable_javascript(source)):
                return True
    return False
