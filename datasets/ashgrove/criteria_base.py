"""Grading shared by every Ashgrove task, in one file.

Seventeen near-identical copies of this logic used to live under
`tasks/*/tests/criteria.py`, differing only in which list they graded and
what named a row. Each carried the same corrections, applied by hand, and
a fix to one never reached the others. When this file was extracted the
copies had already drifted: `row_fields` existed in five variants and
`scalar` in four, and the boolean branch in `matches` -- added after a
reference answer scored 0.571 against its own criteria -- was present in
seven copies of fifteen. The eight without it were one boolean column
away from grading their own reference answer wrong.

These are plain functions, not criteria. A task's `criteria.py` binds its
own rows and row key into the `@criterion` declarations Reward Kit
registers, because each task weighs its criteria differently and those
weights are a measured property of the task, not something to genericize.
Nothing here reads a global a task set: `rows` and `key` are arguments.

The oracle is passed in rather than read off `__file__`. This module is
imported from two places -- the dataset root, where no oracle sits beside
it, and a task's `tests/` directory, where the build copies it so the
container is self-contained -- and only one of them could satisfy a
`__file__`-relative read.

Four rules are encoded, each because its absence cost a measurement:

**Normalize by the truth set, never by the submission.** Iterating what
the agent sent and skipping unmatched rows makes under-reporting free --
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

MAX_BYTES = 300_000


def oracle(here: Path) -> dict:
    """The committed answer key sitting beside a task's criteria."""

    return json.loads((here / "oracle.json").read_text(encoding="utf-8"))


def submitted(workspace: Path, path: str, max_bytes: int = MAX_BYTES) -> dict | None:
    """The deliverable, or None if it is missing, oversized or not an object.

    `max_bytes` is a per-task guard rather than a constant: the two tasks
    whose reports are a page of counts cap at 200_000, and widening them
    to the register tasks' 300_000 would change what a pathological
    submission scores.
    """

    deliverable = workspace / path
    if not deliverable.is_file() or deliverable.stat().st_size > max_bytes:
        return None
    try:
        got = json.loads(deliverable.read_text(encoding="utf-8"))
    except ValueError, UnicodeDecodeError:
        return None
    return got if isinstance(got, dict) else None


def close(a, b, tol) -> bool:
    if b is None:
        return a is None
    if a is None or isinstance(a, bool):
        return False
    return isinstance(a, (int, float)) and abs(float(a) - float(b)) <= tol


def matches(have, want, tol: float) -> bool:
    """One field, by the rule its type implies.

    Booleans first, deliberately: `bool` subclasses `int`, so a numeric
    tolerance check rejects `True` outright and scores every boolean
    field zero -- including the correct ones. A reference answer graded
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
    return close(have, want, tol)


def keyed(rows: list, key: tuple[str, ...]) -> dict:
    """Rows indexed by the fields that together name exactly one of them.

    A key that distinguishes fewer rows than exist caps the achievable
    score below 1.0 for reasons no agent can fix, and row F1 will not
    show it -- both sides dedupe identically and it still reads 1.000.
    """

    return {
        tuple(str(r.get(k)).strip().casefold() for k in key): r
        for r in rows
        if isinstance(r, dict)
    }


def _row_key(row: dict, key: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row[k]).strip().casefold() for k in key)


def _f1(mine: set, want: set) -> float:
    if not want:
        return 1.0 if not mine else 0.0
    hit = len(mine & want)
    if not hit:
        return 0.0
    precision, recall = hit / len(mine), hit / len(want)
    return 2 * precision * recall / (precision + recall)


def grade_schema(workspace: Path, path: str, top: frozenset) -> bool:
    got = submitted(workspace, path)
    return got is not None and set(got) == top


def grade_scalar(
    workspace: Path, path: str, field: str, expected, tol: float = 0.0
) -> bool:
    got = submitted(workspace, path)
    if got is None:
        return False
    mine = got.get(field)
    if isinstance(expected, str) or expected is None:
        return (str(mine).strip().casefold() if mine is not None else None) == (
            expected.strip().casefold() if isinstance(expected, str) else expected
        )
    if isinstance(expected, (dict, list)):
        # Lists compare by equality, like dicts. Without this branch a list
        # fell through to the numeric comparison and returned False for
        # every value including the right one -- the reference answer
        # scored 0.000 against its own grader, which is exactly what the
        # grading guard exists to catch before a rollout pays for it.
        return mine == expected
    return close(mine, expected, tol)


def grade_row_f1(
    workspace: Path, path: str, rows: str, key: tuple[str, ...], expected: list
) -> float:
    got = submitted(workspace, path)
    if got is None:
        return 0.0
    submitted_rows = got.get(rows)
    if not isinstance(submitted_rows, list):
        return 0.0
    return _f1(set(keyed(submitted_rows, key)), set(keyed(expected, key)))


def grade_id_f1(workspace: Path, path: str, field: str, expected: list) -> float:
    """F1 over a list of bare identifiers, rather than over rows."""

    got = submitted(workspace, path)
    if got is None or not isinstance(got.get(field), list):
        return 0.0
    return _f1({str(x) for x in got[field]}, {str(x) for x in expected})


def grade_row_fields(
    workspace: Path,
    path: str,
    rows: str,
    key: tuple[str, ...],
    expected: list,
    spec: dict,
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
    mine = keyed(submitted_rows if isinstance(submitted_rows, list) else [], key)
    checked = matched = 0
    for row in expected:
        theirs = mine.get(_row_key(row, key), {})
        for field, tol in spec.items():
            checked += 1
            matched += matches(theirs.get(field), row[field], tol)
    extra = len(set(mine) - {_row_key(r, key) for r in expected})
    # Invented rows cost, but they cannot wipe out work that is correct:
    # a cliff to zero tells the reader nothing about what the agent knew.
    penalty = min(extra * len(spec), checked // 2)
    if not checked:
        # Nothing expected and nothing invented is a correct answer. This
        # said the opposite, so a task whose world held no findings failed
        # its own reference answer.
        return 0.0 if mine else 1.0
    return max(0.0, (matched - penalty) / checked)


__all__ = [
    "MAX_BYTES",
    "close",
    "grade_id_f1",
    "grade_row_f1",
    "grade_row_fields",
    "grade_scalar",
    "grade_schema",
    "keyed",
    "matches",
    "oracle",
    "submitted",
]
