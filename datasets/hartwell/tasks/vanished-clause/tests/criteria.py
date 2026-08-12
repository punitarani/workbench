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
        "revisions_reviewed",
        "covered_revisions",
        "unreviewed_revision_count",
        "covering_communications",
        "revision_audit",
    }
)
REVISION_FIELDS = frozenset(
    {
        "version_id",
        "document_number",
        "document_path",
        "date",
        "coverage_status",
        "email_ids",
        "public_slack_ts",
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


def _valid_revision(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != REVISION_FIELDS:
        return False
    if not all(
        isinstance(value.get(key), str)
        for key in ("version_id", "document_path", "date", "coverage_status")
    ):
        return False
    email_ids = value.get("email_ids")
    public_slack_ts = value.get("public_slack_ts")
    return (
        _integer(value.get("document_number"))
        and value.get("coverage_status") in {"covered", "unreviewed"}
        and isinstance(email_ids, list)
        and all(isinstance(item, str) for item in email_ids)
        and isinstance(public_slack_ts, list)
        and all(isinstance(item, str) for item in public_slack_ts)
    )


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
    revision_audit = document.get("revision_audit")
    return (
        _integer(document.get("dropped_in_version"))
        and all(
            _integer(document.get(key))
            for key in (
                "revisions_reviewed",
                "covered_revisions",
                "unreviewed_revision_count",
                "covering_communications",
            )
        )
        and isinstance(clean, list)
        and all(_integer(value) for value in clean)
        and isinstance(unreviewed, list)
        and all(isinstance(value, str) for value in unreviewed)
        and isinstance(revision_audit, list)
        and all(_valid_revision(value) for value in revision_audit)
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


def _revision_counter(values: object) -> Counter[object]:
    if not isinstance(values, list):
        return Counter()
    return Counter(
        (
            _version(item["version_id"]),
            item["document_number"],
            item["document_path"],
            item["date"],
            item["coverage_status"],
            tuple(sorted(item["email_ids"])),
            tuple(sorted(item["public_slack_ts"])),
        )
        for item in values
        if _valid_revision(item)
    )


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
def field_marker(
    workspace: Path, path: str, key: str, markers: list[str], max_chars: int = 0
) -> bool:
    """A certified marker, in a value short enough to be an answer.

    ``max_chars`` is what stops a blob. Substring matching cannot tell
    "Marcus Liang" from a paste of every editor in the repository, and a
    field that identifies one author has to identify one author.
    """

    value = _submitted(workspace, path).get(key)
    if not isinstance(value, str):
        return False
    value = value.strip()
    if max_chars and len(value) > max_chars:
        return False
    return any(marker.lower() in value.lower() for marker in markers)


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


@criterion(description="revision evidence ledger multiset F1", shared=True)
def revision_audit_f1(workspace: Path, path: str, expected: list[object]) -> float:
    return _f1(
        _revision_counter(_submitted(workspace, path).get("revision_audit")),
        _revision_counter(expected),
    )


@criterion(description="exact certified revision evidence ledger", shared=True)
def exact_revision_audit(workspace: Path, path: str, expected: list[object]) -> bool:
    return _revision_counter(
        _submitted(workspace, path).get("revision_audit")
    ) == _revision_counter(expected)


@criterion(
    description="ledger aggregates and unreviewed partition reconcile", shared=True
)
def ledger_reconciles(workspace: Path, path: str) -> bool:
    document = _submitted(workspace, path)
    revision_audit = document.get("revision_audit")
    # An empty ledger reconciles with itself vacuously: every count is zero,
    # the unreviewed partition is empty, and every equality below holds. That
    # is not a reconciliation, it is the absence of one, so it earns nothing.
    if not isinstance(revision_audit, list) or not revision_audit:
        return False
    covered = 0
    unreviewed: list[str] = []
    communications = 0
    for item in revision_audit:
        if not _valid_revision(item):
            return False
        citations = len(item["email_ids"]) + len(item["public_slack_ts"])
        if item["coverage_status"] == "covered":
            if citations == 0:
                return False
            covered += 1
        else:
            if citations != 0:
                return False
            unreviewed.append(item["version_id"])
        communications += citations
    return (
        document.get("revisions_reviewed") == len(revision_audit)
        and document.get("covered_revisions") == covered
        and document.get("unreviewed_revision_count") == len(unreviewed)
        and document.get("covering_communications") == communications
        and _counter(document.get("unreviewed_revisions"), versions=True)
        == _counter(unreviewed, versions=True)
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
