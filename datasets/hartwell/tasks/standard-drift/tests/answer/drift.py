"""Answer criteria for standard-drift."""

import json
from pathlib import Path

import rewardkit as rk

TRUTH = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
DELIVERABLE = "drift.json"

rk.field_equals(DELIVERABLE, "playbook_path", TRUTH["playbook_path"], weight=3.0)
rk.nda_f1(DELIVERABLE, TRUTH["ndas"], name="ndas.f1", weight=31.5)
rk.nda_exact(DELIVERABLE, TRUTH["ndas"], name="ndas.certified", weight=3.5)
rk.version_f1(
    DELIVERABLE,
    "silent_versions",
    TRUTH["silent_versions"],
    name="silent_versions.f1",
    weight=25.2,
)
rk.version_exact(
    DELIVERABLE,
    "silent_versions",
    TRUTH["silent_versions"],
    name="silent_versions.certified",
    weight=2.8,
)
for clause_name, clause in TRUTH["clauses"].items():
    rk.clause_marker(
        DELIVERABLE,
        clause_name,
        "playbook_standard",
        clause["standard_markers"],
        name=f"{clause_name}.standard",
        weight=1.0,
    )
    rk.clause_marker(
        DELIVERABLE,
        clause_name,
        "practice",
        clause["practice_markers"],
        name=f"{clause_name}.practice",
        weight=3.0,
    )
    rk.clause_equals(
        DELIVERABLE,
        clause_name,
        "document_path",
        clause["document_path"],
        name=f"{clause_name}.document",
        weight=3.0,
    )
    rk.clause_equals(
        DELIVERABLE,
        clause_name,
        "version",
        clause["version"],
        name=f"{clause_name}.version",
        weight=3.0,
    )
    rk.clause_equals(
        DELIVERABLE,
        clause_name,
        "date",
        clause["date"],
        name=f"{clause_name}.date",
        weight=2.0,
    )
rk.exact_schema(DELIVERABLE, name="deliverable_format", weight=10.0)
