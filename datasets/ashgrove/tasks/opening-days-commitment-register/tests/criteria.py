"""Grading for the opening-days commitment register.

This docstring named the time allocation review until 2026-08-22, and so did nine
other tasks': the file was copied and the prose was not. The KEY comment below
travelled with it, asserting that a row is "a person and an engagement" and citing
197 rows collapsing to 17 -- facts about a different task's corpus, sitting in the
one file whose job is to justify THIS task's key."""

import json
from pathlib import Path

from rewardkit import criterion

MAX_BYTES = 300_000
# Read off the oracle rather than restated here: a hand-kept copy fails
# correct answers the day the report changes shape, which is exactly what
# it did — this list still named `client_rows` after the report moved to
# threads, and every right answer would have failed the schema check.
TOP = frozenset(
    json.loads((Path(__file__).resolve().parent / "oracle.json").read_text())
)
ROWS = "commitments"
# A row is ref plus due date, and both halves are load-bearing: across this oracle's
# 71 rows, ref alone yields 60; due_date alone yields 7. Keying on due_date alone
# would merge 64 rows into their neighbours and mark a fraction of the work as all of
# it. Row F1 would not show a bad key: both sides dedupe identically and it still
# reads 1.000, so the loss appears only as a ceiling no agent can reach.
KEY = ("ref", "due_date")


def _submitted(workspace: Path, path: str) -> dict | None:
    deliverable = workspace / path
    if not deliverable.is_file() or deliverable.stat().st_size > MAX_BYTES:
        return None
    try:
        got = json.loads(deliverable.read_text(encoding="utf-8"))
    except ValueError, UnicodeDecodeError:
        return None
    return got if isinstance(got, dict) else None


def _rows(got: dict) -> dict:
    rows = got.get(ROWS)
    if not isinstance(rows, list):
        return {}
    return {
        tuple(str(r.get(k)).strip().casefold() for k in KEY): r
        for r in rows
        if isinstance(r, dict)
    }


def _close(a, b, tol) -> bool:
    if b is None:
        return a is None
    if a is None or isinstance(a, bool):
        return False
    return isinstance(a, (int, float)) and abs(float(a) - float(b)) <= tol


@criterion(shared=True, description="deliverable parses with the required fields")
def schema_ok(workspace: Path, path: str) -> bool:
    got = _submitted(workspace, path)
    return got is not None and set(got) == TOP


@criterion(shared=True, description="{field} matches")
def scalar(workspace: Path, path: str, field: str, expected, tol: float = 0.0) -> bool:
    got = _submitted(workspace, path)
    if got is None:
        return False
    mine = got.get(field)
    if isinstance(expected, str) or expected is None:
        return (str(mine).strip().casefold() if mine is not None else None) == (
            expected.strip().casefold() if isinstance(expected, str) else expected
        )
    if isinstance(expected, dict):
        return mine == expected
    return _close(mine, expected, tol)


@criterion(shared=True, description="the row set, F1 against the truth")
def flagged_f1(workspace: Path, path: str, expected: list) -> float:
    got = _submitted(workspace, path)
    if got is None:
        return 0.0
    mine = set(_rows(got))
    want = {tuple(str(r[k]).strip().casefold() for k in KEY) for r in expected}
    if not want:
        return 1.0 if not mine else 0.0
    hit = len(mine & want)
    if not hit:
        return 0.0
    precision, recall = hit / len(mine), hit / len(want)
    return 2 * precision * recall / (precision + recall)


@criterion(shared=True, description="per-row figures")
def row_fields(workspace: Path, path: str, expected: list, spec: dict) -> float:
    """Every field of every expected row, with a per-field tolerance.

    Rows the record does not contain are penalised: an invented row is as
    wrong as a missing one.
    """

    got = _submitted(workspace, path)
    if got is None:
        return 0.0
    mine = _rows(got)
    checked = matched = 0
    for row in expected:
        theirs = mine.get(tuple(str(row[k]).strip().casefold() for k in KEY), {})
        for field, tol in spec.items():
            checked += 1
            want = row[field]
            have = theirs.get(field)
            if isinstance(want, str):
                matched += str(have).strip().casefold() == want.strip().casefold()
            elif isinstance(want, list):
                matched += [str(x) for x in (have or [])] == [str(x) for x in want]
            else:
                matched += _close(have, want, tol)
    extra = len(
        set(mine) - {tuple(str(r[k]).strip().casefold() for k in KEY) for r in expected}
    )
    # Invented rows cost, but they cannot wipe out work that is correct:
    # a cliff to zero tells the reader nothing about what the agent knew.
    penalty = min(extra * len(spec), checked // 2)
    # Nothing expected and nothing invented is a correct answer, not a
    # zero. `flagged_f1` has always said so; this said the opposite, so a
    # task whose world held no findings failed its own reference answer.
    if not checked:
        return 0.0 if mine else 1.0
    return max(0.0, (matched - penalty) / checked)
