"""Deterministic weighted grader for the vantage-triage task.

Runs in the agent's workspace (cwd), reads triage.json, writes reward JSON
to $VERIFIER_LOG_DIR (default /logs/verifier). Stdlib only.
"""

import json
import os
import sys
from pathlib import Path

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"


def grade(workspace: Path) -> dict:
    truth = json.loads(GROUND_TRUTH.read_text())
    deliverable = workspace / "triage.json"
    parts: list[dict] = []
    total = 0.0

    submitted: dict = {}
    format_ok = False
    if deliverable.exists():
        try:
            submitted = json.loads(deliverable.read_text()).get("clauses", {})
            format_ok = bool(submitted) and all(
                isinstance(v, dict) and "decision" in v and "basis" in v
                for v in submitted.values()
            )
        except json.JSONDecodeError, AttributeError:
            submitted = {}

    for name, spec in truth["clauses"].items():
        entry = submitted.get(name) or {}
        decision = str(entry.get("decision", "")).strip().lower()
        basis = str(entry.get("basis", "")).lower()
        decision_score = 1.0 if decision in spec["decisions"] else 0.0
        basis_score = (
            1.0 if any(marker in basis for marker in spec["basis_markers"]) else 0.0
        )
        clause_score = spec["weight"] * (
            truth["decision_share"] * decision_score
            + truth["basis_share"] * basis_score
        )
        total += clause_score
        parts.append(
            {
                "clause": name,
                "tier": spec["tier"],
                "decision_ok": decision_score == 1.0,
                "basis_ok": basis_score == 1.0,
                "score": round(clause_score, 4),
                "max": spec["weight"],
            }
        )

    completeness = (
        truth["format_weight"]
        if (format_ok and set(truth["clauses"]) <= set(submitted))
        else 0.0
    )
    total += completeness
    parts.append(
        {"clause": "_format", "score": completeness, "max": truth["format_weight"]}
    )

    return {"score": round(total, 4), "parts": parts}


def main() -> int:
    reward = grade(Path.cwd())
    log_dir = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "reward.json").write_text(json.dumps(reward, indent=2) + "\n")
    print(f"reward: {reward['score']}")
    for part in reward["parts"]:
        print(f"  {part['clause']:18} {part['score']:.3f} / {part['max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
