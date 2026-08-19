"""Grading for the follow-through review: counts, a set, and per-row facts."""

import json
from pathlib import Path

from rewardkit import criterion

MAX_BYTES = 300_000
# Read off the oracle rather than restated here: a hand-kept copy fails
# correct answers the day the report grows a field.
TOP = frozenset(
    json.loads((Path(__file__).resolve().parent / "oracle.json").read_text())
)
ROWS = "documents"
# Name *and* workspace. Two different documents are both called
# "Single Audit Playbook" — one in `firm` by Imogen Carraway at four
# versions, one in `engagements` by Victor Alade at one — and keyed on
# the name alone the second shadows the first. The oracle itself then
# scored 0.976 against this grader, so a perfect answer was capped
# below full marks and the missing quarter-point was charged to the
# agent.
KEY = ("document_number",)


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


@criterion(shared=True, description="deliverable parses with the required fields")
def schema_ok(workspace: Path, path: str) -> bool:
    got = _submitted(workspace, path)
    return got is not None and set(got) == TOP


@criterion(shared=True, description="{field} matches")
def scalar(workspace: Path, path: str, field: str, expected) -> bool:
    got = _submitted(workspace, path)
    return got is not None and got.get(field) == expected


@criterion(shared=True, description="the document set, F1 against the truth")
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


@criterion(shared=True, description="per-document facts")
def row_fields(workspace: Path, path: str, expected: list, fields: list) -> float:
    """Author, workspace, and whether it moved internally at all.

    An invented row costs, but cannot wipe out work that is correct: a
    cliff to zero says nothing about what the agent actually knew.
    """

    got = _submitted(workspace, path)
    if got is None:
        return 0.0
    mine = _rows(got)
    checked = matched = 0
    for row in expected:
        theirs = mine.get(tuple(str(row[k]).strip().casefold() for k in KEY), {})
        for field in fields:
            checked += 1
            want, have = row[field], theirs.get(field)
            if isinstance(want, str):
                matched += str(have).strip().casefold() == want.strip().casefold()
            else:
                matched += have == want
    extra = len(
        set(mine) - {tuple(str(r[k]).strip().casefold() for k in KEY) for r in expected}
    )
    penalty = min(extra * len(fields), checked // 2)
    # Nothing expected and nothing invented is a correct answer, not a
    # zero. `flagged_f1` has always said so; this said the opposite, so a
    # task whose world held no findings failed its own reference answer.
    if not checked:
        return 0.0 if mine else 1.0
    return max(0.0, (matched - penalty) / checked)
