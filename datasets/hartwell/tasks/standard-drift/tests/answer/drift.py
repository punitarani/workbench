"""Answer criteria for standard-drift."""

import json
from pathlib import Path

import rewardkit as rk

TRUTH = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
ORACLE = json.loads(
    (Path(__file__).resolve().parent.parent / "oracle.json").read_text()
)
DELIVERABLE = "drift.json"

rk.field_equals(DELIVERABLE, "playbook_path", TRUTH["playbook_path"], weight=2.0)
rk.nda_f1(DELIVERABLE, TRUTH["ndas"], name="ndas.f1", weight=8.1)
rk.nda_exact(DELIVERABLE, TRUTH["ndas"], name="ndas.certified", weight=0.9)
rk.version_f1(
    DELIVERABLE,
    "silent_versions",
    TRUTH["silent_versions"],
    name="silent_versions.f1",
    weight=5.4,
)
rk.version_exact(
    DELIVERABLE,
    "silent_versions",
    TRUTH["silent_versions"],
    name="silent_versions.certified",
    weight=0.6,
)
for clause_name, clause in TRUTH["clauses"].items():
    # Each half rejects the other half's markers: the certified standard and
    # the certified practice contradict each other, so a value carrying both
    # is a hedge rather than a finding.
    rk.clause_marker(
        DELIVERABLE,
        clause_name,
        "playbook_standard",
        clause["standard_markers"],
        rejects=clause["practice_markers"],
        name=f"{clause_name}.standard",
        weight=0.5,
    )
    rk.clause_marker(
        DELIVERABLE,
        clause_name,
        "practice",
        clause["practice_markers"],
        rejects=clause["standard_markers"],
        name=f"{clause_name}.practice",
        weight=1.5,
    )
    rk.clause_equals(
        DELIVERABLE,
        clause_name,
        "document_path",
        clause["document_path"],
        name=f"{clause_name}.document",
        weight=1.5,
    )
    rk.clause_equals(
        DELIVERABLE,
        clause_name,
        "version",
        clause["version"],
        name=f"{clause_name}.version",
        weight=1.5,
    )
    rk.clause_equals(
        DELIVERABLE,
        clause_name,
        "date",
        clause["date"],
        name=f"{clause_name}.date",
        weight=1.0,
    )
for field in (
    "versions_reviewed",
    "substantive_versions",
    "notices_only_versions",
    "unchanged_versions",
    "covered_substantive_versions",
    "silent_substantive_versions",
    "covering_email_count",
    "authorized_substantive_versions",
    "unauthorized_substantive_versions",
    "late_authorized_substantive_versions",
):
    rk.field_equals(DELIVERABLE, field, ORACLE[field], name=field, weight=1.0)
rk.version_audit_f1(
    DELIVERABLE, ORACLE["version_audit"], name="version_audit.f1", weight=49.2
)
rk.version_audit_exact(
    DELIVERABLE,
    ORACLE["version_audit"],
    name="version_audit.certified",
    weight=5.8,
)
rk.version_audit_reconciles(DELIVERABLE, name="version_audit_reconciles", weight=3.0)
rk.exact_schema(DELIVERABLE, name="deliverable_format", weight=3.0)
