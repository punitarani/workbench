"""Safe criteria for the vanished-clause Reward Kit dimensions."""

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
        "document_path",
        "dropped_clause",
        "dropped_in_version",
        "author",
        "date",
        "change_comment",
        "clean_documents",
        "unreviewed_revisions",
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


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS or not all(
        isinstance(document.get(key), str)
        for key in (
            "document_path",
            "dropped_clause",
            "author",
            "date",
            "change_comment",
        )
    ):
        return False
    clean, unreviewed = (
        document.get("clean_documents"),
        document.get("unreviewed_revisions"),
    )
    return (
        _integer(document.get("dropped_in_version"))
        and isinstance(clean, list)
        and all(_integer(value) for value in clean)
        and isinstance(unreviewed, list)
        and all(isinstance(value, str) for value in unreviewed)
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


def _version(value: object) -> str:
    text = str(value).strip().upper()
    return text if text.startswith("LEGAL!") else f"LEGAL!{text}"


def _counter(values: object, versions: bool = False) -> Counter[object]:
    if not isinstance(values, list):
        return Counter()
    return Counter(_version(value) if versions else value for value in values)


def _f1(got: Counter[object], want: Counter[object]) -> float:
    hits = sum((got & want).values())
    if not hits:
        return 0.0
    precision, recall = hits / sum(got.values()), hits / sum(want.values())
    return 2 * precision * recall / (precision + recall)


@criterion(description="{key} equals the certified value", shared=True)
def field_equals(workspace: Path, path: str, key: str, expected: object) -> bool:
    return _submitted(workspace, path).get(key) == expected


@criterion(description="{key} contains a certified marker", shared=True)
def field_marker(workspace: Path, path: str, key: str, markers: list[str]) -> bool:
    value = _submitted(workspace, path).get(key)
    return isinstance(value, str) and any(
        marker.lower() in value.lower() for marker in markers
    )


@criterion(description="{key} multiset F1", shared=True)
def set_f1(
    workspace: Path, path: str, key: str, expected: list[object], versions: bool = False
) -> float:
    return _f1(
        _counter(_submitted(workspace, path).get(key), versions),
        _counter(expected, versions),
    )


@criterion(description="{key} exact certified multiset", shared=True)
def exact_set(
    workspace: Path, path: str, key: str, expected: list[object], versions: bool = False
) -> bool:
    return _counter(_submitted(workspace, path).get(key), versions) == _counter(
        expected, versions
    )


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
