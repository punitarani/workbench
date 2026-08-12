"""Safe criteria for the standard-drift Reward Kit dimensions."""

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
        "playbook_path",
        "ndas",
        "silent_versions",
        "term",
        "residuals",
        "versions_reviewed",
        "substantive_versions",
        "notices_only_versions",
        "unchanged_versions",
        "covered_substantive_versions",
        "silent_substantive_versions",
        "covering_email_count",
        "version_audit",
    }
)
CLAUSE_FIELDS = frozenset(
    {"playbook_standard", "practice", "document_path", "version", "date"}
)
VERSION_AUDIT_FIELDS = frozenset(
    {"version_id", "document_path", "date", "change_class", "email_ids"}
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


def _valid_version_audit_row(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != VERSION_AUDIT_FIELDS:
        return False
    email_ids = value.get("email_ids")
    return (
        all(
            isinstance(value.get(key), str)
            for key in ("version_id", "document_path", "date", "change_class")
        )
        and value.get("change_class") in {"substantive", "notices_only", "unchanged"}
        and isinstance(email_ids, list)
        and all(isinstance(item, str) for item in email_ids)
    )


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS or not isinstance(
        document.get("playbook_path"), str
    ):
        return False
    ndas = document.get("ndas")
    if not isinstance(ndas, dict) or not all(
        isinstance(path, str) and status in {"conforms", "deviates"}
        for path, status in ndas.items()
    ):
        return False
    silent = document.get("silent_versions")
    if not isinstance(silent, list) or not all(
        isinstance(item, str) for item in silent
    ):
        return False
    if not all(
        _integer(document.get(key))
        for key in (
            "versions_reviewed",
            "substantive_versions",
            "notices_only_versions",
            "unchanged_versions",
            "covered_substantive_versions",
            "silent_substantive_versions",
            "covering_email_count",
        )
    ):
        return False
    version_audit = document.get("version_audit")
    if not isinstance(version_audit, list) or not all(
        _valid_version_audit_row(item) for item in version_audit
    ):
        return False
    for key in ("term", "residuals"):
        clause = document.get(key)
        if not isinstance(clause, dict) or set(clause) != CLAUSE_FIELDS:
            return False
        if not all(
            isinstance(clause.get(field), str)
            for field in ("playbook_standard", "practice", "document_path", "date")
        ) or not _integer(clause.get("version")):
            return False
    return True


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


def _counter(values: object) -> Counter[str]:
    if not isinstance(values, list):
        return Counter()
    return Counter(_version(value) for value in values)


def _f1(got: Counter[object], want: Counter[object]) -> float:
    hits = sum((got & want).values())
    if not hits:
        return 0.0
    precision = hits / sum(got.values())
    recall = hits / sum(want.values())
    return 2 * precision * recall / (precision + recall)


@criterion(description="{key} exactly equals the certified value", shared=True)
def field_equals(workspace: Path, path: str, key: str, expected: object) -> bool:
    return _submitted(workspace, path).get(key) == expected


@criterion(description="{key}.{field} contains a certified marker", shared=True)
def clause_marker(
    workspace: Path,
    path: str,
    key: str,
    field: str,
    markers: list[str],
    rejects: list[str] | None = None,
) -> bool:
    """A certified marker, and none of the contrasting side's markers.

    The standard and the practice are the two halves of a drift finding, and
    they contradict each other: three years against five, refuse residuals
    against accept them. Marker matching alone cannot tell a finding from a
    hedge that recites both, and a hedge is what an agent writes when it did
    not read the redline. ``rejects`` carries the other half's markers, so a
    value answering both questions answers neither.
    """

    clause = _submitted(workspace, path).get(key)
    if not isinstance(clause, dict):
        return False
    value = str(clause.get(field, "")).lower()
    if any(marker.lower() in value for marker in rejects or ()):
        return False
    return any(marker.lower() in value for marker in markers)


@criterion(description="{key}.{field} exactly equals the certified value", shared=True)
def clause_equals(
    workspace: Path, path: str, key: str, field: str, expected: object
) -> bool:
    clause = _submitted(workspace, path).get(key)
    return isinstance(clause, dict) and clause.get(field) == expected


def _nda_counter(values: object) -> Counter[str]:
    if not isinstance(values, dict):
        return Counter()
    return Counter(
        f"{str(path).strip()}\0{str(status).strip().lower()}"
        for path, status in values.items()
    )


@criterion(description="NDA certification F1", shared=True)
def nda_f1(workspace: Path, path: str, expected: dict[str, str]) -> float:
    return _f1(
        _nda_counter(_submitted(workspace, path).get("ndas")), _nda_counter(expected)
    )


@criterion(description="NDA certification exact", shared=True)
def nda_exact(workspace: Path, path: str, expected: dict[str, str]) -> bool:
    return _nda_counter(_submitted(workspace, path).get("ndas")) == _nda_counter(
        expected
    )


@criterion(description="silent version F1", shared=True)
def version_f1(workspace: Path, path: str, key: str, expected: list[str]) -> float:
    return _f1(_counter(_submitted(workspace, path).get(key)), _counter(expected))


@criterion(description="silent versions exact", shared=True)
def version_exact(workspace: Path, path: str, key: str, expected: list[str]) -> bool:
    return _counter(_submitted(workspace, path).get(key)) == _counter(expected)


def _version_audit_counter(values: object) -> Counter[object]:
    if not isinstance(values, list):
        return Counter()
    return Counter(
        (
            _version(item["version_id"]),
            item["document_path"],
            item["date"],
            item["change_class"],
            tuple(sorted(item["email_ids"])),
        )
        for item in values
        if _valid_version_audit_row(item)
    )


@criterion(description="version classification and email ledger F1", shared=True)
def version_audit_f1(workspace: Path, path: str, expected: list[object]) -> float:
    return _f1(
        _version_audit_counter(_submitted(workspace, path).get("version_audit")),
        _version_audit_counter(expected),
    )


@criterion(description="exact version classification and email ledger", shared=True)
def version_audit_exact(workspace: Path, path: str, expected: list[object]) -> bool:
    return _version_audit_counter(
        _submitted(workspace, path).get("version_audit")
    ) == _version_audit_counter(expected)


@criterion(
    description="version audit aggregates and silent partition reconcile", shared=True
)
def version_audit_reconciles(workspace: Path, path: str) -> bool:
    document = _submitted(workspace, path)
    version_audit = document.get("version_audit")
    # An empty audit reconciles with itself vacuously: every count is zero,
    # the silent partition is empty, and every equality below holds. That is
    # not a reconciliation, it is the absence of one, so it earns nothing.
    if not isinstance(version_audit, list) or not version_audit:
        return False
    classes = Counter(
        item["change_class"] for item in version_audit if _valid_version_audit_row(item)
    )
    if sum(classes.values()) != len(version_audit):
        return False
    silent = [
        item["version_id"]
        for item in version_audit
        if item["change_class"] == "substantive" and not item["email_ids"]
    ]
    covered = sum(
        item["change_class"] == "substantive" and bool(item["email_ids"])
        for item in version_audit
    )
    return (
        document.get("versions_reviewed") == len(version_audit)
        and document.get("substantive_versions") == classes["substantive"]
        and document.get("notices_only_versions") == classes["notices_only"]
        and document.get("unchanged_versions") == classes["unchanged"]
        and document.get("covered_substantive_versions") == covered
        and document.get("silent_substantive_versions") == len(silent)
        and document.get("covering_email_count")
        == sum(len(item["email_ids"]) for item in version_audit)
        and _counter(document.get("silent_versions")) == _counter(silent)
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
            if name == tool or name.endswith(f"__{tool}"):
                return True
            source = _unified_exec_source(name, call.get("arguments", {}))
            if source is not None and expression.search(_executable_javascript(source)):
                return True
    return False
