"""Grading for the time allocation review: totals, a set, and per-row figures."""

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

ROWS = "commitments"
# A row is a person *and* an engagement. Keyed on either alone, a
# hundred and ninety-seven rows collapse to seventeen or to thirteen,
# and the grader silently marks a fraction of the work as all of it.
KEY = ("ref", "due_date")


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
