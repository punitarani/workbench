"""Deterministic weighted grader for the operative-deadline task.

Runs in the agent's workspace (cwd), reads deadline.json, writes reward
JSON to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

FIELDS = (
    "operative_date",
    "operative_time",
    "correction_ts",
    "superseded_dates",
    "supersessions",
)


def grade(workspace: Path) -> dict:
    truth = json.loads(GROUND_TRUTH.read_text())
    weights = truth["weights"]
    deliverable = workspace / "deadline.json"

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

    date_score = (
        1.0
        if str(submitted.get("operative_date", "")).strip() == truth["operative_date"]
        else 0.0
    )
    time_text = str(submitted.get("operative_time", "")).lower().replace(" ", "")
    time_score = (
        1.0
        if any(time_text.startswith(p) for p in truth["operative_time_prefixes"])
        else 0.0
    )
    ts_score = (
        1.0
        if str(submitted.get("correction_ts", ""))
        .strip()
        .startswith(truth["correction_ts_prefix"])
        else 0.0
    )

    superseded = submitted.get("superseded_dates")
    superseded = superseded if isinstance(superseded, list) else []
    expected = truth["superseded_dates"]
    matched = sum(
        1
        for position, want in enumerate(expected)
        if position < len(superseded) and str(superseded[position]).strip() == want
    )
    superseded_score = matched / len(expected)

    claimed = submitted.get("supersessions")
    claimed = claimed if isinstance(claimed, list) else []
    by_date: dict = {}
    for entry in claimed:
        if isinstance(entry, dict):
            by_date.setdefault(str(entry.get("invalidated", "")).strip(), entry)
    hits = sum(
        1
        for want in truth["supersessions"]
        if str(by_date.get(want["invalidated"], {}).get("by", ""))
        .strip()
        .startswith(want["by_prefix"])
    )
    supersessions_score = hits / len(truth["supersessions"])

    parts = [
        {"part": "operative_date", "score": weights["operative_date"] * date_score},
        {"part": "operative_time", "score": weights["operative_time"] * time_score},
        {"part": "correction_ts", "score": weights["correction_ts"] * ts_score},
        {
            "part": "superseded_dates",
            "score": weights["superseded_dates"] * superseded_score,
        },
        {
            "part": "supersessions",
            "score": weights["supersessions"] * supersessions_score,
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
        print(f"  {part['part']:18} {part['score']:.3f} / {part['max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
