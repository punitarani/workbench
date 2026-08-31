"""Grading for the completion-claims review.

This docstring named the time allocation review until 2026-08-22, and so did nine
other tasks': the file was copied and the prose was not. The KEY comment below
travelled with it, asserting that a row is "a person and an engagement" and citing
197 rows collapsing to 17 -- facts about a different task's corpus, sitting in the
one file whose job is to justify THIS task's key."""

import sys
from pathlib import Path

from rewardkit import criterion

_HERE = Path(__file__).resolve().parent
# `criteria_base.py` sits at the dataset root in the tree and beside this
# file in a built bundle, where `tests/` has been lifted out and the root is
# not there at all. Both go on the path, because with only one of them the
# import dies before a single criterion runs and the whole task reads as a
# build failure rather than as a grader that never loaded.
sys.path[:0] = [str(_HERE), str(_HERE.parents[2])]

from criteria_base import (  # noqa: E402
    grade_row_f1,
    grade_row_fields,
    grade_scalar,
    grade_schema,
    oracle,
)

# Read off the oracle rather than restated here: a hand-kept copy fails
# correct answers the day the report changes shape, which is exactly what it
# did once -- the list still named a key the report had dropped.
TOP = frozenset(oracle(_HERE))

ROWS = "claims"
# One row per ref. It is an identifier the record states, and across this oracle's 110
# rows it is already unique (110 distinct values), so nothing is composed onto it. Row
# F1 would not show a bad key: both sides dedupe identically and it still reads 1.000,
# so the loss appears only as a ceiling no agent can reach.
KEY = ("ref",)


@criterion(shared=True, description="deliverable parses with the required fields")
def schema_ok(workspace: Path, path: str) -> bool:
    return grade_schema(workspace, path, TOP)


@criterion(shared=True, description="{field} matches")
def scalar(workspace: Path, path: str, field: str, expected, tol: float = 0.0) -> bool:
    return grade_scalar(workspace, path, field, expected, tol)


@criterion(shared=True, description="the row set, F1 against the truth")
def flagged_f1(workspace: Path, path: str, expected: list) -> float:
    return grade_row_f1(workspace, path, ROWS, KEY, expected)


@criterion(shared=True, description="per-row figures")
def row_fields(workspace: Path, path: str, expected: list, spec: dict) -> float:
    return grade_row_fields(workspace, path, ROWS, KEY, expected, spec)
