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
        "notice_audit",
    }
)
SUPERSESSION_FIELDS = frozenset({"invalidated", "by"})
NOTICE_FIELDS = frozenset(
    {
        "message_id",
        "surface",
        "cites_date",
        "operative_when_sent",
        "classification",
    }
)
CLASSIFICATIONS = frozenset({"current", "stale", "correction"})


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
    if not isinstance(supersessions, list) or not all(
        isinstance(record, dict)
        and set(record) == SUPERSESSION_FIELDS
        and isinstance(record.get("invalidated"), str)
        and isinstance(record.get("by"), str)
        for record in supersessions
    ):
        return False
    audit = document.get("notice_audit")
    return isinstance(audit, list) and all(
        isinstance(row, dict)
        and set(row) == NOTICE_FIELDS
        and all(isinstance(row.get(key), str) for key in NOTICE_FIELDS)
        for row in audit
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


def _notice_counter(values: object) -> Counter[str]:
    """One key per (message, date named, judgement) the audit records.

    Identities are normalized the same way ``stale_calendar_refs`` are, so
    a Slack ts written with or without its fractional part is the same
    row rather than a free extra.
    """

    if not isinstance(values, list):
        return Counter()
    return Counter(
        "\0".join(
            (
                _reference(row["message_id"]),
                str(row["surface"]).strip().lower(),
                str(row["cites_date"]).strip(),
                str(row["operative_when_sent"]).strip(),
                str(row["classification"]).strip().lower(),
            )
        )
        for row in values
        if isinstance(row, dict) and set(row) == NOTICE_FIELDS
    )


@criterion(description="notice audit F1", shared=True)
def notice_audit_f1(workspace: Path, path: str, expected: list[object]) -> float:
    return _f1(
        _notice_counter(_submitted(workspace, path).get("notice_audit")),
        _notice_counter(expected),
    )


@criterion(description="notice audit exact", shared=True)
def notice_audit_exact(workspace: Path, path: str, expected: list[object]) -> bool:
    return _notice_counter(
        _submitted(workspace, path).get("notice_audit")
    ) == _notice_counter(expected)


@criterion(description="notice audit is internally consistent", shared=True)
def notice_audit_reconciles(workspace: Path, path: str) -> bool:
    """Does the audit agree with the rest of the deliverable?

    Checked against the submission's own claims, never the oracle, so
    this pays for coherence rather than for a second copy of the answer.
    A non-empty ledger is required: over an empty one every quantifier
    below is vacuously true, which would pay most for doing least.
    """

    document = _submitted(workspace, path)
    audit = document.get("notice_audit")
    if not isinstance(audit, list) or not audit:
        return False
    known = {str(value) for value in document.get("superseded_dates") or ()}
    known.add(str(document.get("operative_date")))
    for row in audit:
        if row["classification"] not in CLASSIFICATIONS:
            return False
        if row["cites_date"] not in known:
            return False
        if row["surface"] not in {"gmail", "slack"}:
            return False
        # A citation is current exactly when it names the date that was
        # operative as it was sent; stale is the strict complement.
        same = row["cites_date"] == row["operative_when_sent"]
        if row["classification"] == "current" and not same:
            return False
        if row["classification"] == "stale" and same:
            return False
    stale_rows = Counter(
        _reference(row["message_id"])
        for row in audit
        if row["classification"] == "stale"
    )
    return stale_rows == _reference_counter(document.get("stale_calendar_refs"))


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
    workspace: Path,
    tool: str,
    path: str = "/logs/agent/trajectory.json",
    also_satisfied_by: tuple[str, ...] = (),
) -> bool:
    """Did the trajectory reach ``tool`` -- or a tool that subsumes it?

    Matching is exact by default, because "was this tool called" is the
    honest reading. ``also_satisfied_by`` names tools whose contract
    already covers this one, so a registration can accept them without
    every criterion silently going fuzzy: ``slack_search_public_and_private``
    searches everything ``slack_search_public`` does, and an agent that
    called it did check public chat.
    """

    del workspace
    try:
        data = json.loads(Path(path).read_text())
    except ValueError, UnicodeDecodeError, OSError, RecursionError:
        return False
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        return False
    accepted = (tool, *also_satisfied_by)
    expressions = [
        re.compile(rf"\btools\.(?:[A-Za-z_]\w*__)*{re.escape(name)}\s*\(")
        for name in accepted
    ]
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
            if any(
                name == candidate or name.endswith(f"__{candidate}")
                for candidate in accepted
            ):
                return True
            if source is None:
                continue
            javascript = _executable_javascript(source)
            if any(expression.search(javascript) for expression in expressions):
                return True
    return False
