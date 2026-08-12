"""Answer criteria for vanished-clause."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
ORACLE = json.loads(
    (Path(__file__).resolve().parent.parent / "oracle.json").read_text()
)
D = "clause.json"
# A person's name, with room for a handle or an email address.
NAME_MAX_CHARS = 64
# Named, because six of these criteria would otherwise share two auto-names
# and reward-details.json could not say which field failed.
rk.field_equals(
    D, "document_path", T["document_path"], name="document_path", weight=2.0
)
rk.field_marker(
    D, "dropped_clause", T["clause_markers"], name="dropped_clause", weight=3.0
)
rk.field_equals(
    D,
    "dropped_in_version",
    T["dropped_in_version"],
    name="dropped_in_version",
    weight=3.0,
)
rk.field_marker(
    D,
    "author",
    T["author_markers"],
    # One editor's name. Generous next to "Marcus Liang", far short of a
    # paste of everyone who ever touched the repository.
    max_chars=NAME_MAX_CHARS,
    name="author",
    weight=2.0,
)
rk.field_equals(D, "date", T["date"], name="date", weight=2.0)
rk.field_marker(
    D, "change_comment", T["comment_markers"], name="change_comment", weight=2.0
)
rk.set_f1(
    D, "clean_documents", T["clean_documents"], name="clean_documents.f1", weight=8.1
)
rk.exact_set(
    D,
    "clean_documents",
    T["clean_documents"],
    name="clean_documents.certified",
    weight=0.9,
)
rk.set_f1(
    D,
    "unreviewed_revisions",
    T["unreviewed_revisions"],
    versions=True,
    name="unreviewed_revisions.f1",
    weight=5.4,
)
rk.exact_set(
    D,
    "unreviewed_revisions",
    T["unreviewed_revisions"],
    versions=True,
    name="unreviewed_revisions.certified",
    weight=0.6,
)
for field in (
    "revisions_reviewed",
    "covered_revisions",
    "unreviewed_revision_count",
    "covering_communications",
):
    rk.field_equals(D, field, ORACLE[field], name=field, weight=1.0)
rk.revision_audit_f1(D, ORACLE["revision_audit"], name="revision_audit.f1", weight=54.9)
rk.exact_revision_audit(
    D, ORACLE["revision_audit"], name="revision_audit.certified", weight=6.1
)
rk.ledger_reconciles(D, name="ledger_reconciles", weight=3.0)
rk.exact_schema(D, name="deliverable_format", weight=3.0)
