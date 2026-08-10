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
        "came_back_later",
        "unanswered_askers",
    }
)
REQUEST_FIELDS = frozenset({"ts", "date", "asked_by", "asked_of"})


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


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS or not all(
        _integer(document.get(key))
        for key in ("requests_reviewed", "conversations_reviewed", "answered_same_day")
    ):
        return False
    for key in ("unanswered_request_ts", "came_back_later", "unanswered_askers"):
        values = document.get(key)
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            return False
    requests = document.get("unanswered_requests")
    return isinstance(requests, list) and all(
        isinstance(record, dict)
        and set(record) == REQUEST_FIELDS
        and all(isinstance(record.get(field), str) for field in REQUEST_FIELDS)
        for record in requests
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
    except ValueError, UnicodeDecodeError, OSError:
        return {}
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return (
        loaded
        if isinstance(loaded, dict) and _finite_json(loaded) and _valid_contract(loaded)
        else {}
    )


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


@criterion(description="exact public schema and types", shared=True)
def exact_schema(workspace: Path, path: str) -> bool:
    return bool(_submitted(workspace, path))


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
            arguments = call.get("arguments", {})
            text = arguments if isinstance(arguments, str) else json.dumps(arguments)
            if name == tool or name.endswith(f"__{tool}") or expression.search(text):
                return True
    return False
