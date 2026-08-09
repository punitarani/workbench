"""Deterministic weighted grader for the redline-provenance task.

Runs in the agent's workspace (cwd), reads provenance.json, writes reward
JSON to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

FIELDS = ("redline_document_path", "author", "revisions", "inbound_draft_revised")


def grade(workspace: Path) -> dict:
    truth = json.loads(GROUND_TRUTH.read_text())
    weights = truth["weights"]
    deliverable = workspace / "provenance.json"

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

    path = str(submitted.get("redline_document_path", "")).strip()
    document_score = 1.0 if path == truth["redline_document_path"] else 0.0

    author = str(submitted.get("author", "")).strip().lower()
    author_score = (
        1.0 if any(marker in author for marker in truth["author_markers"]) else 0.0
    )

    revisions = submitted.get("revisions")
    revisions_ok = (
        isinstance(revisions, list)
        and sorted(r for r in revisions if isinstance(r, int)) == truth["revisions"]
    )
    revisions_score = 1.0 if revisions_ok else 0.0

    inbound = submitted.get("inbound_draft_revised")
    inbound_score = 1.0 if inbound is truth["inbound_draft_revised"] else 0.0

    parts = [
        {"part": "document", "score": weights["document"] * document_score},
        {"part": "author", "score": weights["author"] * author_score},
        {"part": "revisions", "score": weights["revisions"] * revisions_score},
        {"part": "inbound_flag", "score": weights["inbound_flag"] * inbound_score},
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
        print(f"  {part['part']:14} {part['score']:.3f} / {part['max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
