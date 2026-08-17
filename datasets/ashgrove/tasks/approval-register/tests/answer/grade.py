"""Answer criteria for the approval register.

Weight on the row set and the per-row facts, because the task is whether an
agent applies a six-word list to fifteen hundred messages while a hundred
and seventy-one of them agree, green-light and confirm without ever using
one of the six.

`form_counts` carries real weight: it is where over-admitting shows up
first, since a message let in on the strength of "go ahead" has no form to
put in it.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "approvals.json"

rk.scalar(D, "messages_read", T["messages_read"], 0, name="messages_read", weight=1.0)
rk.scalar(D, "approvals_total", T["approvals_total"], 0, name="approvals_total",
          weight=2.0)
rk.scalar(D, "distinct_approvers", T["distinct_approvers"], 0,
          name="distinct_approvers", weight=1.0)
rk.scalar(D, "form_counts", T["form_counts"], name="form_counts", weight=2.5)
rk.scalar(D, "top_approver", T["top_approver"], name="top_approver", weight=1.0)
rk.flagged_f1(D, T["approvals"], name="approvals.f1", weight=5.0)
rk.row_fields(
    D,
    T["approvals"],
    {"form": 0, "approver": 0, "sent_date": 0, "where": 0},
    name="row_facts",
    weight=6.0,
)
