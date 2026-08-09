"""Deterministic weighted grader for the visitor-log-audit task.

Runs in the agent's workspace (cwd), reads visitor-log.json, writes reward
JSON to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.

Slack ts is "seconds.counter"; the seconds part is the message's identity
in the record, the counter is a projection artifact, so every ts is graded
on its seconds prefix.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

FIELDS = (
    "requests_reviewed",
    "conversations_reviewed",
    "open_handover_ts",
    "open_handovers",
    "closed_same_day",
    "closed_next_day",
    "open_requesters",
)


def _seconds(value: object) -> str:
    return str(value).strip().split(".")[0]


def _seconds_set(values: object) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {_seconds(value) for value in values}


def _request_key(entry: object) -> tuple[str, str, str, str] | None:
    if not isinstance(entry, dict):
        return None
    return (
        _seconds(entry.get("ts")),
        str(entry.get("date", "")).strip(),
        str(entry.get("asked_by", "")).strip().lower(),
        str(entry.get("asked_of", "")).strip().lower(),
    )


def grade(workspace: Path) -> dict:
    truth = json.loads(GROUND_TRUTH.read_text())
    weights = truth["weights"]
    deliverable = workspace / "visitor-log.json"

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

    def count_match(field: str) -> float:
        return 1.0 if submitted.get(field) == truth[field] else 0.0

    # The core reconciliation is certified as a whole: exact set or zero.
    ts_score = (
        1.0
        if _seconds_set(submitted.get("open_handover_ts"))
        == set(truth["open_handover_ts_prefixes"])
        else 0.0
    )

    claimed = submitted.get("open_handovers")
    claimed = claimed if isinstance(claimed, list) else []
    truth_keys = {
        (
            entry["ts_prefix"],
            entry["date"],
            entry["asked_by"].lower(),
            entry["asked_of"].lower(),
        )
        for entry in truth["open_handovers"]
    }
    claimed_keys = {key for key in (_request_key(entry) for entry in claimed) if key}
    hits = len(truth_keys & claimed_keys)
    extras = len(claimed_keys - truth_keys)
    requests_score = max(0, hits - extras) / len(truth_keys)

    later_truth = set(truth["closed_next_day_prefixes"])
    later_claimed = _seconds_set(submitted.get("closed_next_day"))
    later_hits = len(later_truth & later_claimed)
    later_extras = len(later_claimed - later_truth)
    later_score = max(0, later_hits - later_extras) / len(later_truth)

    # Marker-matched, extras penalized: naming everyone earns 0.
    askers = submitted.get("open_requesters")
    askers = [str(name).lower() for name in askers] if isinstance(askers, list) else []
    found = sum(
        1
        for markers in truth["requester_markers"]
        if any(all(marker in name for marker in markers) for name in askers)
    )
    asker_extras = sum(
        1
        for name in askers
        if not any(
            all(marker in name for marker in markers)
            for markers in truth["requester_markers"]
        )
    )
    asker_score = max(0, found - asker_extras) / len(truth["requester_markers"])

    parts = [
        {
            "part": "requests_reviewed",
            "score": weights["requests_reviewed"] * count_match("requests_reviewed"),
        },
        {
            "part": "conversations_reviewed",
            "score": weights["conversations_reviewed"]
            * count_match("conversations_reviewed"),
        },
        {
            "part": "open_handover_ts",
            "score": weights["open_handover_ts"] * ts_score,
        },
        {
            "part": "open_handovers",
            "score": weights["open_handovers"] * requests_score,
        },
        {
            "part": "closed_same_day",
            "score": weights["closed_same_day"] * count_match("closed_same_day"),
        },
        {"part": "closed_next_day", "score": weights["closed_next_day"] * later_score},
        {
            "part": "open_requesters",
            "score": weights["open_requesters"] * asker_score,
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
