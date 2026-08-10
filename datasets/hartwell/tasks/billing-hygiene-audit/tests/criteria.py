"""Safe shared criteria for the billing hygiene Reward Kit dimensions."""

import json
import math
import re
from pathlib import Path

from rewardkit import criterion

MAX_DELIVERABLE_BYTES = 1_000_000


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


def _submitted(workspace: Path, path: str) -> dict[str, object]:
    deliverable = workspace / path
    try:
        if (
            not deliverable.is_file()
            or deliverable.stat().st_size > MAX_DELIVERABLE_BYTES
        ):
            return {}
        loaded = json.loads(deliverable.read_text())
    except ValueError, UnicodeDecodeError, OSError:
        return {}
    return loaded if isinstance(loaded, dict) and _finite_json(loaded) else {}


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
    return str(value).strip()


def _canonical(item: object, fields: tuple[str, ...] | None) -> str | None:
    if fields is None:
        if isinstance(item, dict | list):
            return None
        return repr(_canonical_value(item))
    if not isinstance(item, dict):
        return None
    return repr(tuple(_canonical_value(item.get(field, "")) for field in fields))


def _as_set(values: object, fields: tuple[str, ...] | None) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {
        member
        for member in (_canonical(item, fields) for item in values)
        if member is not None
    }


def _expected_set(expected: list[object], fields: tuple[str, ...] | None) -> set[str]:
    return {
        member
        for member in (_canonical(item, fields) for item in expected)
        if member is not None
    }


@criterion(description="{key}: F1 against the certified set", shared=True)
def set_f1(
    workspace: Path,
    path: str,
    key: str,
    expected: list[object],
    fields: tuple[str, ...] | None = None,
) -> float:
    got = _as_set(_submitted(workspace, path).get(key), fields)
    want = _expected_set(expected, fields)
    if not want:
        return 1.0 if not got else 0.0
    hits = len(got & want)
    if not hits:
        return 0.0
    precision = hits / len(got)
    recall = hits / len(want)
    return 2 * precision * recall / (precision + recall)


@criterion(
    description="{key}: exactly the certified set, no misses and no extras",
    shared=True,
)
def exact_set(
    workspace: Path,
    path: str,
    key: str,
    expected: list[object],
    fields: tuple[str, ...] | None = None,
) -> bool:
    return _as_set(_submitted(workspace, path).get(key), fields) == _expected_set(
        expected, fields
    )


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


@criterion(
    description=(
        "{path} has exactly the public fields and every {record_key} record has "
        "exactly its public fields"
    ),
    shared=True,
)
def exact_schema(
    workspace: Path,
    path: str,
    fields: list[str],
    record_key: str,
    record_fields: tuple[str, ...],
) -> bool:
    submitted = _submitted(workspace, path)
    if set(submitted) != set(fields):
        return False
    records = submitted.get(record_key)
    if not isinstance(records, list):
        return False
    expected_record_fields = set(record_fields)
    return all(
        isinstance(record, dict) and set(record) == expected_record_fields
        for record in records
    )


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
    except json.JSONDecodeError, UnicodeDecodeError, OSError:
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
            arguments = call.get("arguments", {})
            text = arguments if isinstance(arguments, str) else json.dumps(arguments)
            count += len(expression.findall(text))
    return count >= min_count
