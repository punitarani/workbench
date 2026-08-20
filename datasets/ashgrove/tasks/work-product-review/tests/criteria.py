"""Grading for the follow-through review: counts, a set, and per-row facts."""

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

ROWS = "documents"
# Name *and* workspace. Two different documents are both called
# "Single Audit Playbook" — one in `firm` by Imogen Carraway at four
# versions, one in `engagements` by Victor Alade at one — and keyed on
# the name alone the second shadows the first. The oracle itself then
# scored 0.976 against this grader, so a perfect answer was capped
# below full marks and the missing quarter-point was charged to the
# agent.
KEY = ("document_number",)


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
def row_fields(workspace: Path, path: str, expected: list, fields: list) -> float:
    # Named without tolerances: every field here is a string or a flag,
    # and an exact comparison is what the task means by a match.
    spec = dict.fromkeys(fields, 0.0)
    return grade_row_fields(workspace, path, ROWS, KEY, expected, spec)
