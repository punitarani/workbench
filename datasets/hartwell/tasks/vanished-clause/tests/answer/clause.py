"""Answer criteria for vanished-clause."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
D = "clause.json"
rk.field_equals(D, "document_path", T["document_path"], weight=5.0)
rk.field_marker(D, "dropped_clause", T["clause_markers"], weight=7.0)
rk.field_equals(D, "dropped_in_version", T["dropped_in_version"], weight=9.0)
rk.field_marker(D, "author", T["author_markers"], weight=4.0)
rk.field_equals(D, "date", T["date"], weight=5.0)
rk.field_marker(D, "change_comment", T["comment_markers"], weight=5.0)
rk.set_f1(
    D, "clean_documents", T["clean_documents"], name="clean_documents.f1", weight=24.3
)
rk.exact_set(
    D,
    "clean_documents",
    T["clean_documents"],
    name="clean_documents.certified",
    weight=2.7,
)
rk.set_f1(
    D,
    "unreviewed_revisions",
    T["unreviewed_revisions"],
    versions=True,
    name="unreviewed_revisions.f1",
    weight=27.0,
)
rk.exact_set(
    D,
    "unreviewed_revisions",
    T["unreviewed_revisions"],
    versions=True,
    name="unreviewed_revisions.certified",
    weight=3.0,
)
rk.exact_schema(D, name="deliverable_format", weight=8.0)
