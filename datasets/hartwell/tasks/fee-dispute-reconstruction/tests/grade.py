"""Deterministic weighted grader for the fee-dispute-reconstruction task.

Runs in the agent's workspace (cwd), reads dispute.json, writes reward
JSON to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

FIELDS = (
    "cutoff_date",
    "total_minutes",
    "entry_count",
    "entries",
    "minutes_by_timekeeper",
    "timekeepers",
    "challenged_by",
    "challenge_date",
    "unsupported_entry_ids",
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
    deliverable = workspace / "dispute.json"

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

    cutoff_score = (
        1.0
        if str(submitted.get("cutoff_date", "")).strip() == truth["cutoff_date"]
        else 0.0
    )
    minutes_score = (
        1.0 if submitted.get("total_minutes") == truth["total_minutes"] else 0.0
    )
    count_score = 1.0 if submitted.get("entry_count") == truth["entry_count"] else 0.0

    claimed = submitted.get("entries")
    claimed = claimed if isinstance(claimed, list) else []
    truth_keys = {(e["id"], e["date"], e["minutes"]) for e in truth["entries"]}
    claimed_keys = {key for key in (_entry_key(entry) for entry in claimed) if key}
    hits = len(truth_keys & claimed_keys)
    extras = len(claimed_keys - truth_keys)
    entries_score = max(0, hits - extras) / len(truth_keys)

    by_keeper = submitted.get("minutes_by_timekeeper")
    by_keeper = by_keeper if isinstance(by_keeper, dict) else {}
    split_found = 0
    for markers, minutes in truth["minutes_by_timekeeper_markers"]:
        for name, value in by_keeper.items():
            named = str(name).lower()
            if all(marker in named for marker in markers) and value == minutes:
                split_found += 1
                break
    split_score = split_found / len(truth["minutes_by_timekeeper_markers"])

    keepers = submitted.get("timekeepers")
    keepers = [str(k).lower() for k in keepers] if isinstance(keepers, list) else []
    found = sum(
        1
        for markers in truth["timekeeper_markers"]
        if any(all(m in keeper for m in markers) for keeper in keepers)
    )
    keeper_score = found / len(truth["timekeeper_markers"])

    challenged = str(submitted.get("challenged_by", "")).lower()
    challenged_score = (
        1.0 if any(m in challenged for m in truth["challenged_by_markers"]) else 0.0
    )
    date_score = (
        1.0
        if str(submitted.get("challenge_date", "")).strip() == truth["challenge_date"]
        else 0.0
    )

    truth_orphans = set(truth["unsupported_entry_ids"])
    claimed_orphans = _id_set(submitted.get("unsupported_entry_ids"))
    orphan_hits = len(truth_orphans & claimed_orphans)
    orphan_extras = len(claimed_orphans - truth_orphans)
    orphan_score = max(0, orphan_hits - orphan_extras) / len(truth_orphans)

    parts = [
        {"part": "cutoff_date", "score": weights["cutoff_date"] * cutoff_score},
        {"part": "total_minutes", "score": weights["total_minutes"] * minutes_score},
        {"part": "entry_count", "score": weights["entry_count"] * count_score},
        {"part": "entries", "score": weights["entries"] * entries_score},
        {
            "part": "minutes_by_timekeeper",
            "score": weights["minutes_by_timekeeper"] * split_score,
        },
        {"part": "timekeepers", "score": weights["timekeepers"] * keeper_score},
        {"part": "challenged_by", "score": weights["challenged_by"] * challenged_score},
        {"part": "challenge_date", "score": weights["challenge_date"] * date_score},
        {
            "part": "unsupported_entry_ids",
            "score": weights["unsupported_entry_ids"] * orphan_score,
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
        print(f"  {part['part']:20} {part['score']:.3f} / {part['max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
