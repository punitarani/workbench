"""Deterministic weighted grader for the vanished-clause task.

Runs in the agent's workspace (cwd), reads clause.json, writes reward
JSON to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

FIELDS = (
    "document_path",
    "dropped_clause",
    "dropped_in_version",
    "author",
    "date",
    "change_comment",
)


def grade(workspace: Path) -> dict:
    truth = json.loads(GROUND_TRUTH.read_text())
    weights = truth["weights"]
    deliverable = workspace / "clause.json"

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

    path_score = (
        1.0
        if str(submitted.get("document_path", "")).strip() == truth["document_path"]
        else 0.0
    )
    clause = str(submitted.get("dropped_clause", "")).lower()
    clause_score = 1.0 if any(m in clause for m in truth["clause_markers"]) else 0.0
    version_score = (
        1.0
        if submitted.get("dropped_in_version") == truth["dropped_in_version"]
        else 0.0
    )
    author = str(submitted.get("author", "")).lower()
    author_score = 1.0 if any(m in author for m in truth["author_markers"]) else 0.0
    date_score = 1.0 if str(submitted.get("date", "")).strip() == truth["date"] else 0.0
    comment = str(submitted.get("change_comment", "")).lower()
    comment_score = 1.0 if any(m in comment for m in truth["comment_markers"]) else 0.0

    parts = [
        {"part": "document_path", "score": weights["document_path"] * path_score},
        {"part": "dropped_clause", "score": weights["dropped_clause"] * clause_score},
        {
            "part": "dropped_in_version",
            "score": weights["dropped_in_version"] * version_score,
        },
        {"part": "author", "score": weights["author"] * author_score},
        {"part": "date", "score": weights["date"] * date_score},
        {"part": "change_comment", "score": weights["change_comment"] * comment_score},
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
