"""Grading shared by every task in this dataset, in one file.

Twenty-eight near-identical copies of this logic exist across the older
datasets, differing only in which oracle key they read. Each carries the
same corrections, applied by hand, and a fix to one has never reached the
others — the bool branch below was added to a single copy after a
reference answer scored 0.571 against its own criteria.

A task's own `criteria.py` supplies three constants and imports the rest:

    from criteria_base import *          # noqa: F403
    ROWS = "commitments"
    KEY = ("ref", "due_date")
    FIELDS = {"author": 0.0, "hours": 0.005}

Everything here is the *reward* half. Presentation and process checks
belong in a diagnostic dimension that informs without moving the number.

Four rules are encoded, each because its absence cost a measurement:

**Normalize by the truth set, never by the submission.** Iterating what
the agent sent and skipping unmatched rows makes under-reporting free —
three perfect rows out of a hundred scores 1.000.

**Cap the invented-row penalty.** A wrong answer must not wipe out work
that was right; a cliff to zero says nothing about what the agent knew.

**Booleans before numbers.** `bool` is a subclass of `int`, and a
tolerance comparison rejects it outright, scoring every boolean field
zero including the correct ones.

**Nothing expected and nothing invented is a correct answer**, not a
zero. A task whose world held no findings used to fail its own reference
answer.
"""

import json
from pathlib import Path

from rewardkit import criterion

MAX_BYTES = 300_000

# Read off the oracle rather than restated here. A hand-kept copy of the
# field list fails every correct answer the day the report changes shape,
# which is exactly what it did once — the list still named a key the
# report had dropped.
_ORACLE = json.loads((Path(__file__).resolve().parent / "oracle.json").read_text())
TOP = frozenset(_ORACLE)


def submitted(workspace: Path, path: str) -> dict | None:
    deliverable = workspace / path
    if not deliverable.is_file() or deliverable.stat().st_size > MAX_BYTES:
        return None
    try:
        got = json.loads(deliverable.read_text(encoding="utf-8"))
    except ValueError, UnicodeDecodeError:
        return None
    return got if isinstance(got, dict) else None


def _keyed(rows: list, key: tuple[str, ...]) -> dict:
    return {
        tuple(str(r.get(k)).strip().casefold() for k in key): r
        for r in rows
        if isinstance(r, dict)
    }


def _close(a, b, tol) -> bool:
    if b is None:
        return a is None
    if a is None or isinstance(a, bool):
        return False
    return isinstance(a, (int, float)) and abs(float(a) - float(b)) <= tol


def _matches(have, want, tol: float) -> bool:
    """One field, by the rule its type implies.

    Booleans first, deliberately: `bool` subclasses `int`, so a numeric
    tolerance check rejects `True` outright and scores every boolean
    field zero — including the correct ones. A reference answer graded
    0.571 against its own criteria until this ordering existed.
    """

    if isinstance(want, bool):
        return isinstance(have, bool) and have == want
    if isinstance(want, str):
        return str(have).strip().casefold() == want.strip().casefold()
    if isinstance(want, list):
        return [str(x) for x in (have or [])] == [str(x) for x in want]
    if isinstance(want, dict):
        return have == want
    return _close(have, want, tol)


@criterion(shared=True, description="deliverable parses with the required fields")
def schema_ok(workspace: Path, path: str) -> bool:
    got = submitted(workspace, path)
    return got is not None and set(got) == TOP


@criterion(shared=True, description="{field} matches")
def scalar(workspace: Path, path: str, field: str, expected, tol: float = 0.0) -> bool:
    got = submitted(workspace, path)
    if got is None:
        return False
    mine = got.get(field)
    if isinstance(expected, str) or expected is None:
        return (str(mine).strip().casefold() if mine is not None else None) == (
            expected.strip().casefold() if isinstance(expected, str) else expected
        )
    if isinstance(expected, (dict, list)):
        return mine == expected
    return _close(mine, expected, tol)


@criterion(shared=True, description="the row set, F1 against the truth")
def row_f1(workspace: Path, path: str, rows: str, key: list, expected: list) -> float:
    got = submitted(workspace, path)
    if got is None:
        return 0.0
    submitted_rows = got.get(rows)
    if not isinstance(submitted_rows, list):
        return 0.0
    mine = set(_keyed(submitted_rows, tuple(key)))
    want = set(_keyed(expected, tuple(key)))
    if not want:
        return 1.0 if not mine else 0.0
    hit = len(mine & want)
    if not hit:
        return 0.0
    precision, recall = hit / len(mine), hit / len(want)
    return 2 * precision * recall / (precision + recall)


@criterion(shared=True, description="per-row figures")
def row_fields(
    workspace: Path, path: str, rows: str, key: list, expected: list, spec: dict
) -> float:
    """Every field of every expected row, with a per-field tolerance.

    Iterates the *oracle's* rows. Iterating the submission and skipping
    unmatched ones makes under-reporting free: three perfect rows out of
    a hundred would score 1.000.
    """

    got = submitted(workspace, path)
    if got is None:
        return 0.0
    submitted_rows = got.get(rows)
    mine = _keyed(
        submitted_rows if isinstance(submitted_rows, list) else [], tuple(key)
    )
    checked = matched = 0
    for row in expected:
        theirs = mine.get(tuple(str(row[k]).strip().casefold() for k in key), {})
        for field, tol in spec.items():
            checked += 1
            matched += _matches(theirs.get(field), row[field], tol)
    extra = len(set(mine) - set(_keyed(expected, tuple(key))))
    # Invented rows cost, but cannot wipe out work that is correct: a
    # cliff to zero tells the reader nothing about what the agent knew.
    penalty = min(extra * len(spec), checked // 2)
    if not checked:
        # Nothing expected and nothing invented is a correct answer. This
        # said the opposite, so a task whose world held no findings failed
        # its own reference answer.
        return 0.0 if mine else 1.0
    return max(0.0, (matched - penalty) / checked)


__all__ = [
    "MAX_BYTES",
    "TOP",
    "row_f1",
    "row_fields",
    "scalar",
    "schema_ok",
    "submitted",
]
