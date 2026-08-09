"""Deterministic weighted grader for the standard-drift task.

Runs in the agent's workspace (cwd), reads drift.json, writes reward JSON
to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

CLAUSE_FIELDS = ("playbook_standard", "practice", "document_path", "version", "date")


def grade(workspace: Path) -> dict:
    truth = json.loads(GROUND_TRUTH.read_text())
    weights = truth["weights"]
    deliverable = workspace / "drift.json"

    submitted: dict = {}
    if deliverable.exists():
        try:
            submitted = json.loads(deliverable.read_text())
        except json.JSONDecodeError:
            submitted = {}
    if not isinstance(submitted, dict):
        submitted = {}
    format_ok = (
        "playbook_path" in submitted
        and isinstance(submitted.get("ndas"), dict)
        and bool(submitted.get("ndas"))
        and all(
            isinstance(submitted.get(name), dict)
            and set(CLAUSE_FIELDS) <= set(submitted[name])
            for name in truth["clauses"]
        )
    )

    parts: list[dict] = []
    path = str(submitted.get("playbook_path", "")).strip()
    parts.append(
        {
            "part": "playbook_path",
            "score": weights["playbook_path"]
            if path == truth["playbook_path"]
            else 0.0,
            "max": weights["playbook_path"],
        }
    )

    # The certification is all-or-nothing: exactly the repository's NDA
    # paths, each with the right call. A dict value counts through its
    # "status" field; unrecognized statuses are wrong.
    claimed = submitted.get("ndas")
    claimed = claimed if isinstance(claimed, dict) else {}
    statuses: dict[str, str] = {}
    for key, value in claimed.items():
        status = value.get("status", "") if isinstance(value, dict) else value
        statuses[str(key).strip()] = str(status).strip().lower()
    survey_ok = set(statuses) == set(truth["ndas"]) and all(
        statuses[path].startswith(verdict[:7])
        for path, verdict in truth["ndas"].items()
    )
    parts.append(
        {
            "part": "nda_survey",
            "score": weights["nda_survey"] if survey_ok else 0.0,
            "max": weights["nda_survey"],
        }
    )

    for name, spec in truth["clauses"].items():
        entry = submitted.get(name)
        entry = entry if isinstance(entry, dict) else {}
        standard = str(entry.get("playbook_standard", "")).lower()
        practice = str(entry.get("practice", "")).lower()
        checks = (
            ("standard", any(m in standard for m in spec["standard_markers"])),
            ("practice", any(m in practice for m in spec["practice_markers"])),
            (
                "document",
                str(entry.get("document_path", "")).strip() == spec["document_path"],
            ),
            ("version", entry.get("version") == spec["version"]),
            ("date", str(entry.get("date", "")).strip() == spec["date"]),
        )
        for part, ok in checks:
            parts.append(
                {
                    "part": f"{name}.{part}",
                    "score": weights[part] if ok else 0.0,
                    "max": weights[part],
                }
            )

    parts.append(
        {
            "part": "format",
            "score": weights["format"] if format_ok else 0.0,
            "max": weights["format"],
        }
    )
    for part in parts:
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
