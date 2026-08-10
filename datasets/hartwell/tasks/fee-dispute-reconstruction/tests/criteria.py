"""Shared criteria for the Hartwell graders.

Reward Kit ships no normalized set criterion, numeric tolerance, or marker
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
import re
from pathlib import Path

from rewardkit import criterion


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
    """The deliverable, or an empty mapping when it is missing or malformed.

    A grader that raises on a missing file turns "the agent produced nothing"
    into a verifier crash, which Harbor reports as an error rather than a
    zero. Absence is an answer; it scores zero.
    """

    deliverable = workspace / path
    if not deliverable.is_file():
        return {}
    try:
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
    """One comparable string per set member.

    Scalars normalize through ``str`` so 439 and "439" are the same entry.
    Records compare on the named fields only, so a submission carrying extra
    keys is neither rewarded nor punished for them.
    """

    if fields is None:
        if isinstance(item, (dict, list)):
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


@criterion(
    description="{key}: F1 against the certified set",
    shared=True,
)
def set_f1(
    workspace: Path,
    path: str,
    key: str,
    expected: list[object],
    fields: tuple[str, ...] | None = None,
) -> float:
    """Harmonic mean of precision and recall over a set-valued field.

    Partial credit is the point: a near-miss has to score near one, and a
    shotgun answer has to score near zero. F1 does both — listing everything
    drives precision to the base rate, listing six of seven scores 0.923.
    """

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
    """The certification claim, kept as its own criterion.

    Some answers go back to a client as a single statement — one entry listed
    whose day does have support and the audit is worthless. That semantics
    deserves a bonus, not the whole grade.
    """

    return _as_set(_submitted(workspace, path).get(key), fields) == _expected_set(
        expected, fields
    )


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


@criterion(description="{key}: share of the expected names present", shared=True)
def marker_list_recall(
    workspace: Path, path: str, key: str, marker_sets: list[list[str]]
) -> float:
    """Recall over a list of people, matched by name fragments.

    Names are free text — "Marcus Liang", "M. Liang", "liang, marcus" — so the
    grader matches fragments rather than a canonical form, exactly as the
    legacy grader did.
    """

    values = _submitted(workspace, path).get(key)
    values = (
        [str(value).lower() for value in values] if isinstance(values, list) else []
    )
    if not marker_sets:
        return 1.0
    found = sum(
        1
        for markers in marker_sets
        if any(all(marker in value for marker in markers) for value in values)
    )
    return found / len(marker_sets)


@criterion(
    description="{key}: share of the expected name/value pairs correct", shared=True
)
def marker_map_recall(
    workspace: Path, path: str, key: str, expected: list[list[object]]
) -> float:
    """Recall over a name-keyed mapping of figures.

    Each expected element is ``[[name fragments], value]``: the pair counts
    only when some key matches every fragment *and* carries the right value.
    """

    mapping = _submitted(workspace, path).get(key)
    mapping = mapping if isinstance(mapping, dict) else {}
    if not expected:
        return 1.0
    found = 0
    for markers, value in expected:
        for name, submitted_value in mapping.items():
            if all(marker in str(name).lower() for marker in markers):
                if submitted_value == value:
                    found += 1
                break
    return found / len(expected)


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
