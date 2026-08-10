"""Safe criteria for the client-departure Reward Kit dimensions."""

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
        "first_negative_signal_date",
        "first_negative_signal_ts",
        "happy_update_ts",
        "happy_update_reactions",
        "first_negative_signal_reactions",
        "reaction_trajectory",
        "matter_closed_date",
        "termination_email_date",
        "disengagement_letter_path",
        "unanswered_client_emails",
    }
)
STRING_FIELDS = (
    "first_negative_signal_date",
    "first_negative_signal_ts",
    "happy_update_ts",
    "matter_closed_date",
    "termination_email_date",
    "disengagement_letter_path",
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


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS or not all(
        isinstance(document.get(field), str) for field in STRING_FIELDS
    ):
        return False
    if not _integer(document.get("happy_update_reactions")) or not _integer(
        document.get("first_negative_signal_reactions")
    ):
        return False
    trajectory = document.get("reaction_trajectory")
    emails = document.get("unanswered_client_emails")
    return (
        isinstance(trajectory, list)
        and all(_integer(value) for value in trajectory)
        and isinstance(emails, list)
        and all(isinstance(value, str) for value in emails)
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


def _counter(values: object) -> Counter[str]:
    if not isinstance(values, list):
        return Counter()
    return Counter(str(value).strip().lower() for value in values)


def _f1(got: Counter[str], want: Counter[str]) -> float:
    hits = sum((got & want).values())
    if not hits:
        return 0.0
    precision, recall = hits / sum(got.values()), hits / sum(want.values())
    return 2 * precision * recall / (precision + recall)


@criterion(description="{key} equals the certified value", shared=True)
def field_equals(workspace: Path, path: str, key: str, expected: object) -> bool:
    return _submitted(workspace, path).get(key) == expected


@criterion(description="{key} starts with the certified identity", shared=True)
def field_prefix(workspace: Path, path: str, key: str, expected: str) -> bool:
    value = _submitted(workspace, path).get(key)
    return isinstance(value, str) and value.strip().startswith(expected)


@criterion(description="{key} ends with the certified repository path", shared=True)
def field_suffix(workspace: Path, path: str, key: str, expected: str) -> bool:
    value = _submitted(workspace, path).get(key)
    return isinstance(value, str) and value.strip().lstrip("/").endswith(expected)


@criterion(description="ordered sequence position-aware similarity", shared=True)
def ordered_similarity(
    workspace: Path, path: str, key: str, expected: list[object]
) -> float:
    got = _submitted(workspace, path).get(key)
    if not isinstance(got, list):
        return 0.0
    hits = sum(actual == wanted for actual, wanted in zip(got, expected, strict=False))
    return hits / max(len(got), len(expected)) if got or expected else 1.0


@criterion(description="{key} multiset F1", shared=True)
def set_f1(workspace: Path, path: str, key: str, expected: list[str]) -> float:
    return _f1(_counter(_submitted(workspace, path).get(key)), _counter(expected))


@criterion(description="{key} exact certified multiset", shared=True)
def exact_set(workspace: Path, path: str, key: str, expected: list[str]) -> bool:
    return _counter(_submitted(workspace, path).get(key)) == _counter(expected)


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
