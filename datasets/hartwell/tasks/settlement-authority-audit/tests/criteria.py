"""Safe Reward Kit criteria for settlement-authority-audit."""

import json
import math
import os
import re
import stat
from collections import Counter
from datetime import datetime
from pathlib import Path

from rewardkit import criterion

MAX_DELIVERABLE_BYTES = 1_000_000
PUBLIC_FIELDS = frozenset(
    {
        "matter_number",
        "negotiation_alias",
        "client_decision_maker",
        "opposing_counsel",
        "proposal_count",
        "authorized_count",
        "breach_count",
        "breach_message_ids",
        "authority_timeline",
        "proposal_audit",
    }
)
TIMELINE_FIELDS = frozenset(
    {
        "effective_at",
        "surface",
        "source_ids",
        "status",
        "amount_cents",
        "amount_rule",
        "economic_basis",
        "required_terms",
        "prohibited_terms",
        "expires_at",
    }
)
PROPOSAL_FIELDS = frozenset(
    {
        "message_id",
        "sent_at",
        "sender",
        "amount_cents",
        "economic_basis",
        "terms",
        "authority_source_ids",
        "disposition",
    }
)
TERMS = frozenset(
    {
        "mutual_release",
        "general_release",
        "release_unknown_claims",
        "mutual_non_disparagement",
        "confidentiality",
        "no_confidentiality",
        "inventory_transition_60_days",
        "payment_within_10_days",
    }
)
BASES = frozenset({"exclusive", "inclusive", "net_plus_fees"})
DISPOSITIONS = frozenset(
    {
        "authorized",
        "amount_outside_authority",
        "economic_terms_mismatch",
        "authority_revoked",
        "authority_expired",
        "nonmonetary_terms_mismatch",
    }
)


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


def _instant(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp has no offset")
    return int(parsed.timestamp())


def _string_list(value: object, *, allowed: frozenset[str] | None = None) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and item and (allowed is None or item in allowed)
        for item in value
    )


def _valid_timeline(record: object) -> bool:
    if not isinstance(record, dict) or set(record) != TIMELINE_FIELDS:
        return False
    amount = record.get("amount_cents")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        return False
    if record.get("surface") not in {"gmail", "slack"}:
        return False
    if record.get("status") not in {"grant", "hold"}:
        return False
    if record.get("amount_rule") not in {"minimum", "exact", "none"}:
        return False
    if record.get("economic_basis") not in {*BASES, "none"}:
        return False
    if not _string_list(record.get("source_ids")):
        return False
    if not _string_list(record.get("required_terms"), allowed=TERMS):
        return False
    if not _string_list(record.get("prohibited_terms"), allowed=TERMS):
        return False
    effective, expires = record.get("effective_at"), record.get("expires_at")
    if not isinstance(effective, str) or not isinstance(expires, str):
        return False
    try:
        _instant(effective)
        if expires:
            _instant(expires)
    except ValueError, OverflowError:
        return False
    return True


def _valid_proposal(record: object) -> bool:
    if not isinstance(record, dict) or set(record) != PROPOSAL_FIELDS:
        return False
    amount = record.get("amount_cents")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        return False
    if record.get("economic_basis") not in BASES:
        return False
    if record.get("disposition") not in DISPOSITIONS:
        return False
    if not all(
        isinstance(record.get(field), str) and record[field]
        for field in ("message_id", "sent_at", "sender")
    ):
        return False
    if not _string_list(record.get("terms"), allowed=TERMS):
        return False
    if not _string_list(record.get("authority_source_ids")):
        return False
    try:
        _instant(record["sent_at"])
    except ValueError, OverflowError:
        return False
    return True


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS:
        return False
    if not all(
        isinstance(document.get(field), str) and document[field]
        for field in ("matter_number", "negotiation_alias", "client_decision_maker")
    ):
        return False
    if not _string_list(document.get("opposing_counsel")):
        return False
    for field in ("proposal_count", "authorized_count", "breach_count"):
        value = document.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return False
    if not _string_list(document.get("breach_message_ids")):
        return False
    timeline, proposals = (
        document.get("authority_timeline"),
        document.get("proposal_audit"),
    )
    return (
        isinstance(timeline, list)
        and all(_valid_timeline(record) for record in timeline)
        and isinstance(proposals, list)
        and all(_valid_proposal(record) for record in proposals)
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


def _identifier(value: str) -> str:
    text = value.strip().lower()
    if text.startswith("msg-"):
        return text
    return text.split(".")[0]


def _term_list(value: list[str]) -> list[str]:
    return sorted(term.strip().lower() for term in value)


def _timeline_key(record: dict[str, object]) -> str:
    canonical = {
        "effective_at": _instant(record["effective_at"]),
        "surface": str(record["surface"]).lower(),
        "source_ids": sorted(_identifier(value) for value in record["source_ids"]),
        "status": str(record["status"]).lower(),
        "amount_cents": record["amount_cents"],
        "amount_rule": str(record["amount_rule"]).lower(),
        "economic_basis": str(record["economic_basis"]).lower(),
        "required_terms": _term_list(record["required_terms"]),
        "prohibited_terms": _term_list(record["prohibited_terms"]),
        "expires_at": _instant(record["expires_at"]) if record["expires_at"] else 0,
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


def _proposal_key(record: dict[str, object]) -> str:
    canonical = {
        "message_id": _identifier(record["message_id"]),
        "sent_at": _instant(record["sent_at"]),
        "sender": str(record["sender"]).strip().casefold(),
        "amount_cents": record["amount_cents"],
        "economic_basis": str(record["economic_basis"]).lower(),
        "terms": _term_list(record["terms"]),
        "authority_source_ids": sorted(
            _identifier(value) for value in record["authority_source_ids"]
        ),
        "disposition": str(record["disposition"]).lower(),
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


def _counter(values: list[dict[str, object]], key) -> Counter[str]:
    return Counter(key(record) for record in values)


def _f1(got: Counter[str], want: Counter[str]) -> float:
    hits = sum((got & want).values())
    if not hits:
        return 0.0
    precision, recall = hits / sum(got.values()), hits / sum(want.values())
    return 2 * precision * recall / (precision + recall)


@criterion(description="matter identity fields match", shared=True)
def identity_fields(workspace: Path, path: str, expected: dict[str, object]) -> bool:
    got = _submitted(workspace, path)
    return (
        got.get("matter_number") == expected["matter_number"]
        and str(got.get("negotiation_alias", "")).strip().casefold()
        == str(expected["negotiation_alias"]).strip().casefold()
    )


@criterion(description="client and opposing roles match", shared=True)
def role_fields(workspace: Path, path: str, expected: dict[str, object]) -> bool:
    got = _submitted(workspace, path)
    return str(got.get("client_decision_maker", "")).strip().casefold() == str(
        expected["client_decision_maker"]
    ).strip().casefold() and Counter(
        str(value).strip().casefold() for value in got.get("opposing_counsel", [])
    ) == Counter(
        str(value).strip().casefold() for value in expected["opposing_counsel"]
    )


@criterion(description="{key} equals the certified value", shared=True)
def field_equals(workspace: Path, path: str, key: str, expected: object) -> bool:
    return _submitted(workspace, path).get(key) == expected


def _breach_counter(values: object) -> Counter[str]:
    return (
        Counter(_identifier(value) for value in values)
        if isinstance(values, list)
        else Counter()
    )


@criterion(description="breach message-id F1", shared=True)
def breach_f1(workspace: Path, path: str, expected: list[str]) -> float:
    return _f1(
        _breach_counter(_submitted(workspace, path).get("breach_message_ids")),
        _breach_counter(expected),
    )


@criterion(description="breach message ids exact", shared=True)
def breach_exact(workspace: Path, path: str, expected: list[str]) -> bool:
    return _breach_counter(
        _submitted(workspace, path).get("breach_message_ids")
    ) == _breach_counter(expected)


@criterion(description="authority timeline record F1", shared=True)
def timeline_f1(workspace: Path, path: str, expected: list[dict[str, object]]) -> float:
    got = _submitted(workspace, path).get("authority_timeline")
    return _f1(
        _counter(got, _timeline_key) if isinstance(got, list) else Counter(),
        _counter(expected, _timeline_key),
    )


@criterion(description="authority timeline exact", shared=True)
def timeline_exact(
    workspace: Path, path: str, expected: list[dict[str, object]]
) -> bool:
    got = _submitted(workspace, path).get("authority_timeline")
    return isinstance(got, list) and _counter(got, _timeline_key) == _counter(
        expected, _timeline_key
    )


@criterion(description="proposal audit record F1", shared=True)
def proposal_f1(workspace: Path, path: str, expected: list[dict[str, object]]) -> float:
    got = _submitted(workspace, path).get("proposal_audit")
    return _f1(
        _counter(got, _proposal_key) if isinstance(got, list) else Counter(),
        _counter(expected, _proposal_key),
    )


@criterion(description="proposal audit exact", shared=True)
def proposal_exact(
    workspace: Path, path: str, expected: list[dict[str, object]]
) -> bool:
    got = _submitted(workspace, path).get("proposal_audit")
    return isinstance(got, list) and _counter(got, _proposal_key) == _counter(
        expected, _proposal_key
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
    return source[cursor + 1 : end] in {"catch", "for", "if", "switch", "while", "with"}


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
