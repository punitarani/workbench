"""Answer criteria for the self-review review.

The weight sits on the three booleans per row, because the whole task is
whether an agent keeps them apart. `review_claimed` is a fact about prose,
`independently_reviewed` is a fact about authorship, and conflating them
costs exactly the ten documents where they disagree.

`self_review_risk_count` and `at_risk` carry real weight for the same
reason: they are the two figures that only come out right if the ten are
found, and they are what a quality partner would actually read.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "self_review.json"

rk.scalar(D, "documents_total", T["documents_total"], 0, name="documents_total",
          weight=1.0)
rk.scalar(D, "review_claimed_count", T["review_claimed_count"], 0,
          name="review_claimed_count", weight=2.0)
rk.scalar(D, "independently_reviewed_count", T["independently_reviewed_count"], 0,
          name="independently_reviewed_count", weight=2.0)
rk.scalar(D, "self_review_risk_count", T["self_review_risk_count"], 0,
          name="self_review_risk_count", weight=2.5)
rk.scalar(D, "unreviewed_and_unclaimed_count", T["unreviewed_and_unclaimed_count"], 0,
          name="unreviewed_and_unclaimed", weight=1.0)
rk.scalar(D, "at_risk", T["at_risk"], name="at_risk", weight=2.5)
rk.flagged_f1(D, T["documents"], name="documents.f1", weight=2.0)
rk.row_fields(
    D,
    T["documents"],
    {
        "document": 0,
        "preparer": 0,
        "versions": 0,
        "distinct_authors": 0,
        "review_claimed": 0,
        "independently_reviewed": 0,
        "self_review_risk": 0,
    },
    name="row_facts",
    weight=7.0,
)
