"""Deterministic weighted grader for the client-departure-postmortem task.

Runs in the agent's workspace (cwd), reads postmortem.json, writes reward
JSON to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

FIELDS = (
    "first_negative_signal_date",
    "happy_update_reactions",
    "first_negative_signal_reactions",
    "matter_closed_date",
    "termination_email_date",
    "disengagement_letter_path",
)


def grade(workspace: Path) -> dict:
    truth = json.loads(GROUND_TRUTH.read_text())
    weights = truth["weights"]
    deliverable = workspace / "postmortem.json"

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

    def date_match(field: str) -> float:
        return 1.0 if str(submitted.get(field, "")).strip() == truth[field] else 0.0

    def count_match(field: str) -> float:
        return 1.0 if submitted.get(field) == truth[field] else 0.0

    letter = str(submitted.get("disengagement_letter_path", "")).strip().lstrip("/")
    letter_score = 1.0 if letter.endswith(truth["letter_path_suffix"]) else 0.0

    parts = [
        {
            "part": "first_negative_signal_date",
            "score": weights["first_negative_signal_date"]
            * date_match("first_negative_signal_date"),
        },
        {
            "part": "happy_update_reactions",
            "score": weights["happy_update_reactions"]
            * count_match("happy_update_reactions"),
        },
        {
            "part": "first_negative_signal_reactions",
            "score": weights["first_negative_signal_reactions"]
            * count_match("first_negative_signal_reactions"),
        },
        {
            "part": "matter_closed_date",
            "score": weights["matter_closed_date"] * date_match("matter_closed_date"),
        },
        {
            "part": "termination_email_date",
            "score": weights["termination_email_date"]
            * date_match("termination_email_date"),
        },
        {
            "part": "disengagement_letter_path",
            "score": weights["disengagement_letter_path"] * letter_score,
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
        print(f"  {part['part']:30} {part['score']:.3f} / {part['max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
