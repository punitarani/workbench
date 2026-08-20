"""Grading for open-items triage: counts, set membership, and per-item fields.

Partial credit is real — an agent that finds six of seven open threads
has done most of the work — but the exact-set bonus is what separates a
careful sweep from a good guess.
"""

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

from criteria_base import oracle, submitted  # noqa: E402

# Read off the oracle rather than restated here: a hand-kept copy fails
# correct answers the day the report changes shape, which is exactly what it
# did once -- the list still named a key the report had dropped.
TOP_FIELDS = frozenset(oracle(_HERE))


MAX_BYTES = 200_000
ITEM_FIELDS = frozenset(
    {"thread_id", "message_id", "client", "subject", "messages_in_thread"}
)


def _items(got: dict) -> list[dict]:
    items = got.get("awaiting_firm")
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _f1(got: set[str], want: set[str]) -> float:
    if not want:
        return 1.0 if not got else 0.0
    hit = len(got & want)
    if not hit:
        return 0.0
    precision, recall = hit / len(got), hit / len(want)
    return 2 * precision * recall / (precision + recall)


@criterion(shared=True, description="deliverable parses with the required fields")
def schema_ok(workspace: Path, path: str) -> bool:
    got = submitted(workspace, path, MAX_BYTES)
    return got is not None and set(got) == TOP_FIELDS


@criterion(shared=True, description="{field} matches")
def count_matches(workspace: Path, path: str, field: str, expected: int) -> bool:
    got = submitted(workspace, path, MAX_BYTES)
    return got is not None and got.get(field) == expected


@criterion(shared=True, description="awaiting threads, F1 against the true set")
def awaiting_f1(workspace: Path, path: str, expected: list) -> float:
    got = submitted(workspace, path, MAX_BYTES)
    if got is None:
        return 0.0
    return _f1(
        {str(i.get("thread_id")) for i in _items(got)},
        {str(i["thread_id"]) for i in expected},
    )


@criterion(shared=True, description="awaiting set is exactly right")
def awaiting_exact(workspace: Path, path: str, expected: list) -> bool:
    got = submitted(workspace, path, MAX_BYTES)
    if got is None:
        return False
    return {str(i.get("thread_id")) for i in _items(got)} == {
        str(i["thread_id"]) for i in expected
    }


@criterion(shared=True, description="per-thread details are right")
def item_fields(workspace: Path, path: str, expected: list) -> float:
    """Every field of every correctly-identified thread must agree."""

    got = submitted(workspace, path, MAX_BYTES)
    if got is None:
        return 0.0
    want = {str(i["thread_id"]): i for i in expected}
    checked = matched = 0
    for item in _items(got):
        reference = want.get(str(item.get("thread_id")))
        if reference is None:
            continue
        for field in ITEM_FIELDS - {"thread_id"}:
            checked += 1
            mine, theirs = item.get(field), reference[field]
            if isinstance(theirs, str):
                matched += str(mine).strip().casefold() == theirs.strip().casefold()
            else:
                matched += mine == theirs
    return matched / checked if checked else 0.0


@criterion(shared=True, description="sorted by thread id")
def ordered(workspace: Path, path: str) -> bool:
    got = submitted(workspace, path, MAX_BYTES)
    if got is None:
        return False
    ids = [str(i.get("thread_id")) for i in _items(got)]
    return ids == sorted(ids)
