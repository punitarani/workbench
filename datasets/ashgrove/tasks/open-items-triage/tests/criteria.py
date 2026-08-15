"""Grading for open-items triage: counts, set membership, and per-item fields.

Partial credit is real — an agent that finds six of seven open threads
has done most of the work — but the exact-set bonus is what separates a
careful sweep from a good guess.
"""

import json
from pathlib import Path

from rewardkit import criterion

MAX_BYTES = 200_000
TOP_FIELDS = frozenset(
    {
        "threads_reviewed",
        "awaiting_firm_count",
        "closed_by_client_courtesy",
        "awaiting_firm",
    }
)
ITEM_FIELDS = frozenset(
    {"thread_id", "message_id", "client", "subject", "messages_in_thread"}
)


def _submitted(workspace: Path, path: str) -> dict | None:
    deliverable = workspace / path
    if not deliverable.is_file() or deliverable.stat().st_size > MAX_BYTES:
        return None
    try:
        got = json.loads(deliverable.read_text(encoding="utf-8"))
    except ValueError, UnicodeDecodeError:
        return None
    return got if isinstance(got, dict) else None


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
    got = _submitted(workspace, path)
    return got is not None and set(got) == TOP_FIELDS


@criterion(shared=True, description="{field} matches")
def count_matches(workspace: Path, path: str, field: str, expected: int) -> bool:
    got = _submitted(workspace, path)
    return got is not None and got.get(field) == expected


@criterion(shared=True, description="awaiting threads, F1 against the true set")
def awaiting_f1(workspace: Path, path: str, expected: list) -> float:
    got = _submitted(workspace, path)
    if got is None:
        return 0.0
    return _f1(
        {str(i.get("thread_id")) for i in _items(got)},
        {str(i["thread_id"]) for i in expected},
    )


@criterion(shared=True, description="awaiting set is exactly right")
def awaiting_exact(workspace: Path, path: str, expected: list) -> bool:
    got = _submitted(workspace, path)
    if got is None:
        return False
    return {str(i.get("thread_id")) for i in _items(got)} == {
        str(i["thread_id"]) for i in expected
    }


@criterion(shared=True, description="per-thread details are right")
def item_fields(workspace: Path, path: str, expected: list) -> float:
    """Every field of every correctly-identified thread must agree."""

    got = _submitted(workspace, path)
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
    got = _submitted(workspace, path)
    if got is None:
        return False
    ids = [str(i.get("thread_id")) for i in _items(got)]
    return ids == sorted(ids)
