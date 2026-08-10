"""Safe criteria for the operative-deadline Reward Kit dimensions."""

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
        "operative_date",
        "operative_time",
        "correction_ts",
        "superseded_dates",
        "supersessions",
        "stale_calendar_refs",
    }
)
SUPERSESSION_FIELDS = frozenset({"invalidated", "by"})


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
    if set(document) != PUBLIC_FIELDS or not all(
        isinstance(document.get(key), str)
        for key in ("operative_date", "operative_time", "correction_ts")
    ):
        return False
    dates, supersessions, stale = (
        document.get(key)
        for key in ("superseded_dates", "supersessions", "stale_calendar_refs")
    )
    if not isinstance(dates, list) or not all(
        isinstance(value, str) for value in dates
    ):
        return False
    if not isinstance(stale, list) or not all(
        isinstance(value, str) for value in stale
    ):
        return False
    return isinstance(supersessions, list) and all(
        isinstance(record, dict)
        and set(record) == SUPERSESSION_FIELDS
        and isinstance(record.get("invalidated"), str)
        and isinstance(record.get("by"), str)
        for record in supersessions
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


def _f1(got: Counter[str], want: Counter[str]) -> float:
    hits = sum((got & want).values())
    if not hits:
        return 0.0
    precision, recall = hits / sum(got.values()), hits / sum(want.values())
    return 2 * precision * recall / (precision + recall)


def _seconds(value: object) -> str:
    return str(value).strip().split(".")[0]


def _supersession_counter(values: object) -> Counter[str]:
    if not isinstance(values, list):
        return Counter()
    return Counter(
        f"{record['invalidated']}\0{_seconds(record['by'])}"
        for record in values
        if isinstance(record, dict) and set(record) == SUPERSESSION_FIELDS
    )


def _reference(value: object) -> str:
    text = str(value).strip().lower()
    return text if text.startswith("msg-") else _seconds(text)


def _reference_counter(values: object) -> Counter[str]:
    return (
        Counter(_reference(value) for value in values)
        if isinstance(values, list)
        else Counter()
    )


@criterion(description="{key} equals the certified value", shared=True)
def field_equals(workspace: Path, path: str, key: str, expected: object) -> bool:
    return _submitted(workspace, path).get(key) == expected


@criterion(description="{key} matches an allowed prefix", shared=True)
def field_prefix_any(workspace: Path, path: str, key: str, expected: list[str]) -> bool:
    value = _submitted(workspace, path).get(key)
    return isinstance(value, str) and any(
        value.strip().startswith(prefix) for prefix in expected
    )


@criterion(description="ordered position-aware similarity", shared=True)
def ordered_similarity(
    workspace: Path, path: str, key: str, expected: list[str]
) -> float:
    got = _submitted(workspace, path).get(key)
    if not isinstance(got, list):
        return 0.0
    hits = sum(actual == wanted for actual, wanted in zip(got, expected, strict=False))
    return hits / max(len(got), len(expected)) if got or expected else 1.0


@criterion(description="supersession record F1", shared=True)
def supersession_f1(
    workspace: Path, path: str, expected: list[dict[str, str]]
) -> float:
    got = _supersession_counter(_submitted(workspace, path).get("supersessions"))
    want = Counter(
        f"{record['invalidated']}\0{_seconds(record['by_prefix'])}"
        for record in expected
    )
    return _f1(got, want)


@criterion(description="supersession records exact", shared=True)
def supersession_exact(
    workspace: Path, path: str, expected: list[dict[str, str]]
) -> bool:
    got = _supersession_counter(_submitted(workspace, path).get("supersessions"))
    want = Counter(
        f"{record['invalidated']}\0{_seconds(record['by_prefix'])}"
        for record in expected
    )
    return got == want


def _truth_references(expected: list[dict[str, str]]) -> Counter[str]:
    return Counter(
        record["id"].lower()
        if record["kind"] == "email"
        else _seconds(record["ts_prefix"])
        for record in expected
    )


@criterion(description="stale reference F1", shared=True)
def reference_f1(workspace: Path, path: str, expected: list[dict[str, str]]) -> float:
    return _f1(
        _reference_counter(_submitted(workspace, path).get("stale_calendar_refs")),
        _truth_references(expected),
    )


@criterion(description="stale references exact", shared=True)
def reference_exact(workspace: Path, path: str, expected: list[dict[str, str]]) -> bool:
    return _reference_counter(
        _submitted(workspace, path).get("stale_calendar_refs")
    ) == _truth_references(expected)


@criterion(description="exact public schema and types", shared=True)
def exact_schema(workspace: Path, path: str) -> bool:
    return bool(_submitted(workspace, path))


def _executable_javascript(source: str) -> str:
    code: list[str] = []
    state = "code"
    quote = ""
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
            if char in {"'", '"', chr(96)}:
                code.append(" ")
                state = "string"
                quote = char
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
        else:
            code.append("\n" if char == "\n" else " ")
            if char == "\\" and following:
                code.append("\n" if following == "\n" else " ")
                index += 2
                continue
            if char == quote:
                state = "code"
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
    except ValueError, UnicodeDecodeError, OSError:
        return False
    expression = re.compile(rf"\btools\.(?:[A-Za-z_]\w*__)*{re.escape(tool)}\s*\(")
    for step in data.get("steps", []) if isinstance(data, dict) else []:
        for call in step.get("tool_calls", []) if isinstance(step, dict) else []:
            if not isinstance(call, dict):
                continue
            name = str(call.get("function_name", ""))
            source = _unified_exec_source(name, call.get("arguments", {}))
            if name == tool or name.endswith(f"__{tool}"):
                return True
            if source is not None and expression.search(_executable_javascript(source)):
                return True
    return False
