"""Safe shared criteria for the billing hygiene Reward Kit dimensions."""

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
        "entries_reviewed",
        "timekeepers_reviewed",
        "person_days_reviewed",
        "cleared_by_communication",
        "cleared_no_corroboration",
        "anomalous_timekeeper_days",
        "anomalous_timekeeper_day_count",
        "anomalous_entry_count",
        "anomalous_minutes_total",
        "anomalous_billed_cents_total",
        "phantom_note_ids",
        "daily_review",
    }
)
COUNT_FIELDS = (
    "entries_reviewed",
    "timekeepers_reviewed",
    "person_days_reviewed",
    "cleared_by_communication",
    "cleared_no_corroboration",
    "anomalous_timekeeper_day_count",
    "anomalous_entry_count",
    "anomalous_minutes_total",
    "anomalous_billed_cents_total",
)
ANOMALOUS_DAY_FIELDS = frozenset(
    {"date", "timekeeper", "entry_ids", "matter_numbers", "minutes", "billed_cents"}
)
ANOMALOUS_DAY_FIELD_ORDER = (
    "date",
    "timekeeper",
    "entry_ids",
    "matter_numbers",
    "minutes",
    "billed_cents",
)
DAILY_REVIEW_FIELDS = (
    "date",
    "timekeeper",
    "billable_entry_ids",
    "sent_gmail_ids",
    "sent_slack_ts",
    "corroborated_entry_ids",
    "corroborated_matter_numbers",
    "disposition",
)
DISPOSITIONS = frozenset(
    {"cleared_by_communication", "cleared_no_corroboration", "anomalous"}
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


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _integer_list(value: object) -> bool:
    return isinstance(value, list) and all(_integer(item) for item in value)


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS or any(
        not _integer(document.get(field)) for field in COUNT_FIELDS
    ):
        return False
    days = document.get("anomalous_timekeeper_days")
    if not isinstance(days, list):
        return False
    for day in days:
        if not isinstance(day, dict) or set(day) != ANOMALOUS_DAY_FIELDS:
            return False
        if (
            not isinstance(day.get("date"), str)
            or not isinstance(day.get("timekeeper"), str)
            or not _integer_list(day.get("entry_ids"))
            or not _string_list(day.get("matter_numbers"))
            or not _integer(day.get("minutes"))
            or not _integer(day.get("billed_cents"))
        ):
            return False
    if not _integer_list(document.get("phantom_note_ids")):
        return False
    review = document.get("daily_review")
    if not isinstance(review, list):
        return False
    for record in review:
        if not isinstance(record, dict) or set(record) != set(DAILY_REVIEW_FIELDS):
            return False
        if (
            not isinstance(record.get("date"), str)
            or not isinstance(record.get("timekeeper"), str)
            or not _integer_list(record.get("billable_entry_ids"))
            or not _string_list(record.get("sent_gmail_ids"))
            or not _string_list(record.get("sent_slack_ts"))
            or not _integer_list(record.get("corroborated_entry_ids"))
            or not _string_list(record.get("corroborated_matter_numbers"))
            or record.get("disposition") not in DISPOSITIONS
        ):
            return False
    return True


def _submitted(workspace: Path, path: str) -> dict[str, object]:
    deliverable = workspace / path
    descriptor = -1
    try:
        descriptor = os.open(deliverable, os.O_RDONLY | os.O_NOFOLLOW)
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
        loaded = json.loads(contents.decode("utf-8"))
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
    if value is None:
        return ("null", None)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, float):
        return ("float", value)
    if isinstance(value, str):
        return ("str", value.strip())
    return ("invalid", repr(value))


def _canonical(item: object, fields: tuple[str, ...] | None) -> str | None:
    if fields is None:
        if isinstance(item, dict | list):
            return None
        return repr(_canonical_value(item))
    if not isinstance(item, dict):
        return None
    return repr(tuple(_canonical_value(item.get(field, "")) for field in fields))


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
    description="the daily review reconciles to the population and anomaly summary",
    shared=True,
)
def daily_review_reconciles(workspace: Path, path: str) -> bool:
    submitted = _submitted(workspace, path)
    review = submitted.get("daily_review")
    # An empty workpaper reconciles with itself vacuously: every count is
    # zero, every partition is empty, and every equality below holds. That is
    # not a reconciliation, it is the absence of one, so it earns nothing.
    if not isinstance(review, list) or not review:
        return False
    identities = [(record["date"], record["timekeeper"]) for record in review]
    billable_ids = [
        activity_id for record in review for activity_id in record["billable_entry_ids"]
    ]
    dispositions = Counter(record["disposition"] for record in review)
    anomalous = [record for record in review if record["disposition"] == "anomalous"]
    if any(
        len(record["billable_entry_ids"]) != len(set(record["billable_entry_ids"]))
        or len(record["sent_gmail_ids"]) != len(set(record["sent_gmail_ids"]))
        or len(record["sent_slack_ts"]) != len(set(record["sent_slack_ts"]))
        or len(record["corroborated_entry_ids"])
        != len(set(record["corroborated_entry_ids"]))
        or len(record["corroborated_matter_numbers"])
        != len(set(record["corroborated_matter_numbers"]))
        or not set(record["corroborated_entry_ids"]).issubset(
            record["billable_entry_ids"]
        )
        or bool(record["corroborated_entry_ids"])
        != bool(record["corroborated_matter_numbers"])
        or (
            record["disposition"] == "cleared_by_communication"
            and not (record["sent_gmail_ids"] or record["sent_slack_ts"])
        )
        or (
            record["disposition"] == "cleared_no_corroboration"
            and (
                record["sent_gmail_ids"]
                or record["sent_slack_ts"]
                or record["corroborated_entry_ids"]
            )
        )
        or (
            record["disposition"] == "anomalous"
            and (
                record["sent_gmail_ids"]
                or record["sent_slack_ts"]
                or not record["corroborated_entry_ids"]
            )
        )
        for record in review
    ):
        return False
    submitted_anomalies = submitted.get("anomalous_timekeeper_days")
    if not isinstance(submitted_anomalies, list):
        return False
    summary_keys = Counter(
        (
            record["date"],
            record["timekeeper"],
            tuple(sorted(record["entry_ids"])),
            tuple(sorted(record["matter_numbers"])),
        )
        for record in submitted_anomalies
    )
    ledger_keys = Counter(
        (
            record["date"],
            record["timekeeper"],
            tuple(sorted(record["corroborated_entry_ids"])),
            tuple(sorted(record["corroborated_matter_numbers"])),
        )
        for record in anomalous
    )
    return (
        len(review) == submitted.get("person_days_reviewed")
        and len(identities) == len(set(identities))
        and len({record["timekeeper"] for record in review})
        == submitted.get("timekeepers_reviewed")
        and len(billable_ids) == submitted.get("entries_reviewed")
        and len(billable_ids) == len(set(billable_ids))
        and dispositions["cleared_by_communication"]
        == submitted.get("cleared_by_communication")
        and dispositions["cleared_no_corroboration"]
        == submitted.get("cleared_no_corroboration")
        and dispositions["anomalous"] == submitted.get("anomalous_timekeeper_day_count")
        and sum(len(record["corroborated_entry_ids"]) for record in anomalous)
        == submitted.get("anomalous_entry_count")
        and summary_keys == ledger_keys
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


@criterion(
    description="agent invoked {tool} at least {min_count} time(s)",
    shared=True,
)
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
