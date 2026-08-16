"""Answer criteria for the file-room review.

The row set is the whole repository, so naming it is easy and the marks
sit on the per-document facts: who wrote it, how many versions it has,
who reviewed it, who outside the firm has seen it. That is deliberate —
a task whose answer is a short list of interesting rows scores one or
zero, and says nothing about how much of the work the agent actually did.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "work_product_review.json"

rk.scalar(D, "documents_total", T["documents_total"], name="total", weight=1.0)
rk.scalar(D, "reviewed_count", T["reviewed_count"], name="reviewed", weight=2.0)
rk.scalar(D, "unreviewed_count", T["unreviewed_count"], name="unreviewed", weight=1.5)
rk.scalar(
    D,
    "reached_client_count",
    T["reached_client_count"],
    name="reached_client",
    weight=2.0,
)
rk.scalar(
    D,
    "never_attached_count",
    T["never_attached_count"],
    name="never_attached",
    weight=1.5,
)
rk.flagged_f1(D, T["documents"], name="documents.f1", weight=2.0)
rk.row_fields(
    D,
    T["documents"],
    ["workspace", "author", "versions", "reviewed", "reached_client"],
    name="row_facts",
    weight=6.0,
)
