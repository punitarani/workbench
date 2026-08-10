"""Shared criteria for the Hartwell graders.

Reward Kit ships no normalized multiset criterion, numeric tolerance, or marker
matching. ``set_f1`` gives a near miss proportional credit while
``exact_set`` preserves a small certification premium. Together they replace
the exact-set cliffs without changing any field's total weight.

The marker helpers preserve the prior name matching. This changes the shape
of partial credit, not what constitutes a correct answer.

Every criterion here is ``shared=True``: Reward Kit rejects root-level
criteria that are not, because a nested layout would otherwise silently drop
them.
"""

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
        "cutoff_date",
        "total_minutes",
        "entry_count",
        "entries",
        "minutes_by_timekeeper",
        "timekeepers",
        "challenged_by",
        "challenge_date",
        "unsupported_days",
    }
)
ENTRY_FIELDS = frozenset({"id", "date", "minutes"})
UNSUPPORTED_DAY_FIELDS = frozenset(
    {"date", "entry_ids", "entry_count", "minutes", "billed_cents"}
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


def _valid_contract(document: dict[str, object]) -> bool:
    if set(document) != PUBLIC_FIELDS:
        return False
    if not isinstance(document.get("cutoff_date"), str):
        return False
    if not _integer(document.get("total_minutes")) or not _integer(
        document.get("entry_count")
    ):
        return False
    entries = document.get("entries")
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != ENTRY_FIELDS:
            return False
        if (
            not _integer(entry.get("id"))
            or not isinstance(entry.get("date"), str)
            or not _integer(entry.get("minutes"))
        ):
            return False
    minutes_by_timekeeper = document.get("minutes_by_timekeeper")
    if not isinstance(minutes_by_timekeeper, dict) or not all(
        isinstance(name, str) and _integer(minutes)
        for name, minutes in minutes_by_timekeeper.items()
    ):
        return False
    timekeepers = document.get("timekeepers")
    if not isinstance(timekeepers, list) or not all(
        isinstance(name, str) for name in timekeepers
    ):
        return False
    if not isinstance(document.get("challenged_by"), str) or not isinstance(
        document.get("challenge_date"), str
    ):
        return False
    unsupported_days = document.get("unsupported_days")
    if not isinstance(unsupported_days, list):
        return False
    for day in unsupported_days:
        if not isinstance(day, dict) or set(day) != UNSUPPORTED_DAY_FIELDS:
            return False
        if (
            not isinstance(day.get("date"), str)
            or not _integer_list(day.get("entry_ids"))
            or not _integer(day.get("entry_count"))
            or not _integer(day.get("minutes"))
            or not _integer(day.get("billed_cents"))
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


@criterion(
    description="{key}: F1 against the certified multiset",
    shared=True,
)
def set_f1(
    workspace: Path,
    path: str,
    key: str,
    expected: list[object],
    fields: tuple[str, ...] | None = None,
) -> float:
    """Harmonic mean of precision and recall over a multiset-valued field.

    Partial credit is the point: a near-miss has to score near one, and a
    shotgun answer has to score near zero. F1 does both — listing everything
    drives precision to the base rate, listing six of seven scores 0.923.
    """

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
    """The certification claim, kept as its own criterion.

    Some answers go back to a client as a single statement — one entry listed
    whose day does have support and the audit is worthless. That semantics
    deserves a bonus, not the whole grade.
    """

    return _as_multiset(
        _submitted(workspace, path).get(key), fields
    ) == _expected_multiset(expected, fields)


@criterion(
    description="{key} within {tol} of {expected}",
    shared=True,
)
def numeric_close(
    workspace: Path, path: str, key: str, expected: float, tol: float = 0.0
) -> bool:
    """A figure, graded against a stated tolerance rather than by equality.

    ``tol = 0`` is exact, which is what a minute count off real entries needs;
    the parameter exists so derived figures do not have to be.
    """

    value = _submitted(workspace, path).get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
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


@criterion(description="{key} == {expected}", shared=True)
def field_equals(workspace: Path, path: str, key: str, expected: str) -> bool:
    return str(_submitted(workspace, path).get(key, "")).strip() == expected


@criterion(description="{key} names one of {markers}", shared=True)
def field_names_any(workspace: Path, path: str, key: str, markers: list[str]) -> bool:
    """A person named however the agent chose to name them."""

    value = str(_submitted(workspace, path).get(key, "")).lower()
    return any(marker in value for marker in markers)


def _maximum_matches(candidates: list[set[int]]) -> int:
    matched_submissions: dict[int, int] = {}

    def assign(submission: int, seen: set[int]) -> bool:
        for expected in sorted(candidates[submission]):
            if expected in seen:
                continue
            seen.add(expected)
            previous = matched_submissions.get(expected)
            if previous is None or assign(previous, seen):
                matched_submissions[expected] = submission
                return True
        return False

    for submission in range(len(candidates)):
        assign(submission, set())
    return len(matched_submissions)


def _normalized_f1(hits: int, submitted: int, expected: int) -> float:
    if not expected:
        return 1.0 if not submitted else 0.0
    if not submitted or not hits:
        return 0.0
    precision = hits / submitted
    recall = hits / expected
    return 2 * precision * recall / (precision + recall)


def _name_candidates(names: list[str], marker_sets: list[list[str]]) -> list[set[int]]:
    return [
        {
            index
            for index, markers in enumerate(marker_sets)
            if all(marker.lower() in name.lower() for marker in markers)
        }
        for name in names
    ]


def _map_candidates(
    mapping: dict[str, object], expected: list[list[object]]
) -> list[set[int]]:
    candidates: list[set[int]] = []
    for name, submitted_value in mapping.items():
        matches: set[int] = set()
        for index, pair in enumerate(expected):
            markers, expected_value = pair
            if not isinstance(markers, list):
                continue
            if submitted_value == expected_value and all(
                str(marker).lower() in name.lower() for marker in markers
            ):
                matches.add(index)
        candidates.append(matches)
    return candidates


@criterion(description="{key}: marker-aware F1 for expected names", shared=True)
def marker_list_f1(
    workspace: Path, path: str, key: str, marker_sets: list[list[str]]
) -> float:
    values = _submitted(workspace, path).get(key)
    names = (
        [value for value in values if isinstance(value, str)]
        if isinstance(values, list)
        else []
    )
    hits = _maximum_matches(_name_candidates(names, marker_sets))
    return _normalized_f1(hits, len(names), len(marker_sets))


@criterion(description="{key}: exactly the expected names by markers", shared=True)
def exact_marker_list(
    workspace: Path, path: str, key: str, marker_sets: list[list[str]]
) -> bool:
    values = _submitted(workspace, path).get(key)
    names = (
        [value for value in values if isinstance(value, str)]
        if isinstance(values, list)
        else []
    )
    hits = _maximum_matches(_name_candidates(names, marker_sets))
    return hits == len(names) == len(marker_sets)


@criterion(description="{key}: marker-aware F1 for name/value pairs", shared=True)
def marker_map_f1(
    workspace: Path, path: str, key: str, expected: list[list[object]]
) -> float:
    mapping = _submitted(workspace, path).get(key)
    mapping = mapping if isinstance(mapping, dict) else {}
    candidates = _map_candidates(mapping, expected)
    hits = _maximum_matches(candidates)
    return _normalized_f1(hits, len(mapping), len(expected))


@criterion(
    description="{key}: exactly the expected name/value pairs by markers", shared=True
)
def exact_marker_map(
    workspace: Path, path: str, key: str, expected: list[list[object]]
) -> bool:
    mapping = _submitted(workspace, path).get(key)
    mapping = mapping if isinstance(mapping, dict) else {}
    hits = _maximum_matches(_map_candidates(mapping, expected))
    return hits == len(mapping) == len(expected)


@criterion(description="{path} is an object carrying every required field", shared=True)
def has_fields(workspace: Path, path: str, fields: list[str]) -> bool:
    submitted = _submitted(workspace, path)
    return bool(submitted) and all(field in submitted for field in fields)


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
    """Whether a named MCP tool was actually called, in either trajectory shape.

    Reward Kit's ``trajectory_tool_used`` matches ``function_name``, which is
    right for adapters that emit one ATIF tool call per tool. Codex run with
    ``--enable unified_exec`` does not: every tool, MCP servers included, is
    reached as ``tools.<name>(...)`` inside a JavaScript blob passed to a
    single ``exec`` call, so the only function name in the trajectory is
    ``exec`` and the built-in criterion is structurally blind to it.

    This criterion is a superset: it matches the function name (bare or
    namespaced ``server__tool``) and actual ``tools.<name>(`` expressions in
    unified-exec source. A prose mention is not evidence of invocation.
    """

    trajectory = Path(path)
    if not trajectory.is_file():
        return False
    try:
        data = json.loads(trajectory.read_text())
    except json.JSONDecodeError, UnicodeDecodeError, OSError:
        return False

    expression = re.compile(
        rf"\btools\.(?:[A-Za-z_][A-Za-z0-9_]*__)*{re.escape(tool)}\s*\("
    )
    count = 0
    for step in data.get("steps", []):
        for call in step.get("tool_calls") or []:
            name = str(call.get("function_name", ""))
            if name == tool or name.endswith(f"__{tool}"):
                count += 1
                continue
            arguments = call.get("arguments", {})
            text = arguments if isinstance(arguments, str) else json.dumps(arguments)
            count += len(expression.findall(text))
    return count >= min_count
