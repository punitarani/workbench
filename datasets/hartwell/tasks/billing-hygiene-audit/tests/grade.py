"""Deterministic weighted grader for the billing-hygiene-audit task.

Runs in the agent's workspace (cwd), reads hygiene.json, writes reward
JSON to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

FIELDS = (
    "entries_reviewed",
    "timekeepers_reviewed",
    "unsupported_entry_ids",
    "unsupported_entries",
    "unsupported_minutes_total",
    "unsupported_timekeepers",
    "phantom_note_ids",
)


def _id_set(values: object) -> set[int]:
    if not isinstance(values, list):
        return set()
    ids: set[int] = set()
    for value in values:
        try:
            ids.add(int(value))
        except TypeError, ValueError:
            continue
    return ids


def _entry_key(entry: object) -> tuple | None:
    if not isinstance(entry, dict):
        return None
    try:
        return (
            int(entry.get("id")),
            str(entry.get("date", "")).strip(),
            int(entry.get("minutes")),
        )
    except TypeError, ValueError:
        return None


def grade(workspace: Path) -> dict:
    truth = json.loads(GROUND_TRUTH.read_text())
    weights = truth["weights"]
    deliverable = workspace / "hygiene.json"

    submitted: dict = {}
    format_ok = False
    if deliverable.exists():
        try:
            submitted = json.loads(deliverable.read_text())
            format_ok = isinstance(submitted, dict) and all(
                field in submitted for field in FIELDS
            )
        except json.JSONDecodeError:
            submitted = {}
    if not isinstance(submitted, dict):
        submitted = {}

    reviewed_score = (
        1.0 if submitted.get("entries_reviewed") == truth["entries_reviewed"] else 0.0
    )
    keeper_count_score = (
        1.0
        if submitted.get("timekeepers_reviewed") == truth["timekeepers_reviewed"]
        else 0.0
    )

    # The core reconciliation is certified as a whole: exact set or zero.
    truth_ids = set(truth["unsupported_entry_ids"])
    claimed_ids = _id_set(submitted.get("unsupported_entry_ids"))
    ids_score = 1.0 if claimed_ids == truth_ids else 0.0

    claimed = submitted.get("unsupported_entries")
    claimed = claimed if isinstance(claimed, list) else []
    truth_keys = {
        (e["id"], e["date"], e["minutes"]) for e in truth["unsupported_entries"]
    }
    claimed_keys = {key for key in (_entry_key(entry) for entry in claimed) if key}
    hits = len(truth_keys & claimed_keys)
    extras = len(claimed_keys - truth_keys)
    entries_score = max(0, hits - extras) / len(truth_keys)

    minutes_score = (
        1.0
        if submitted.get("unsupported_minutes_total")
        == truth["unsupported_minutes_total"]
        else 0.0
    )

    # Marker-matched, extras penalized: enumerating every timekeeper earns 0.
    keepers = submitted.get("unsupported_timekeepers")
    keepers = [str(k).lower() for k in keepers] if isinstance(keepers, list) else []
    found = sum(
        1
        for markers in truth["timekeeper_markers"]
        if any(all(m in keeper for m in markers) for keeper in keepers)
    )
    keeper_extras = sum(
        1
        for keeper in keepers
        if not any(
            all(m in keeper for m in markers) for markers in truth["timekeeper_markers"]
        )
    )
    keeper_score = max(0, found - keeper_extras) / len(truth["timekeeper_markers"])

    truth_notes = set(truth["phantom_note_ids"])
    claimed_notes = _id_set(submitted.get("phantom_note_ids"))
    note_hits = len(truth_notes & claimed_notes)
    note_extras = len(claimed_notes - truth_notes)
    notes_score = max(0, note_hits - note_extras) / len(truth_notes)

    parts = [
        {
            "part": "entries_reviewed",
            "score": weights["entries_reviewed"] * reviewed_score,
        },
        {
            "part": "timekeepers_reviewed",
            "score": weights["timekeepers_reviewed"] * keeper_count_score,
        },
        {
            "part": "unsupported_entry_ids",
            "score": weights["unsupported_entry_ids"] * ids_score,
        },
        {
            "part": "unsupported_entries",
            "score": weights["unsupported_entries"] * entries_score,
        },
        {
            "part": "unsupported_minutes_total",
            "score": weights["unsupported_minutes_total"] * minutes_score,
        },
        {
            "part": "unsupported_timekeepers",
            "score": weights["unsupported_timekeepers"] * keeper_score,
        },
        {
            "part": "phantom_note_ids",
            "score": weights["phantom_note_ids"] * notes_score,
        },
        {"part": "format", "score": weights["format"] if format_ok else 0.0},
    ]
    for part in parts:
        part["max"] = weights[part["part"]]
        part["score"] = round(part["score"], 4)

    total = round(sum(part["score"] for part in parts), 4)
    return {"score": total, "parts": parts}


def main() -> int:
    reward = grade(Path.cwd())
    log_dir = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "reward.json").write_text(json.dumps(reward, indent=2) + "\n")
    print(f"reward: {reward['score']}")
    for part in reward["parts"]:
        print(f"  {part['part']:24} {part['score']:.3f} / {part['max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
