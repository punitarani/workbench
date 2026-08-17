"""Answer criteria for the commitment register.

The weight sits on the two things this task is actually about: finding the
rows at all, and getting each one's facts right. Nearly two hundred
commitments are scattered through the bodies of three hundred messages and
nothing else in the firm records them, so recall is the work and `f1`
is where it is measured.

The scalars are exact on purpose. A count is right or it is wrong, and a
register that is one row short reports a wrong total — that is the honest
consequence of a missed message, not a trick. They carry a third of the
weight between them so that a near-miss on the rows costs something without
costing everything.

Dates are compared as strings because they are strings: `2026-01-09` is
either the day the promise falls due or it is not, and there is no
tolerance that makes a Thursday partly a Friday.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "commitments.json"

rk.scalar(D, "messages_read", T["messages_read"], 0, name="messages_read", weight=1.0)
rk.scalar(
    D,
    "commitments_total",
    T["commitments_total"],
    0,
    name="commitments_total",
    weight=1.5,
)
rk.scalar(
    D,
    "messages_with_commitment",
    T["messages_with_commitment"],
    0,
    name="messages_with_commitment",
    weight=1.5,
)
rk.scalar(
    D, "busiest_due_date", T["busiest_due_date"], name="busiest_due_date", weight=1.0
)
rk.scalar(D, "top_made_to", T["top_made_to"], name="top_made_to", weight=1.0)
# The register itself: did the agent find the promises. Keyed on message
# and due date together, because one message can promise two dates and a
# key on either alone would score half the work as all of it.
rk.flagged_f1(D, T["commitments"], name="commitments.f1", weight=5.0)
rk.row_fields(
    D,
    T["commitments"],
    {"author": 0, "sent_date": 0, "made_to": 0},
    name="row_facts",
    weight=6.0,
)
