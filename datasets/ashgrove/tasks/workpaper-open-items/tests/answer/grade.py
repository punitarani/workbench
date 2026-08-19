"""Answer criteria for the working-paper open items.

The weight sits on the row set and the per-row facts, because the task is
whether an agent opens all eighty-five workbooks or samples them, and a
sampled library shows up first as missing rows.

`workbooks_read` and `sheets_read` carry real weight of their own, and
they are the only two figures here that are pure enumeration: they are
right if and only if the whole library was walked, and they cannot be
recovered by being clever about the rows.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "open_items.json"

rk.scalar(
    D, "workbooks_read", T["workbooks_read"], 0, name="workbooks_read", weight=2.0
)
rk.scalar(D, "sheets_read", T["sheets_read"], 0, name="sheets_read", weight=2.0)
rk.scalar(
    D, "open_items_total", T["open_items_total"], 0, name="open_items_total", weight=2.0
)
rk.scalar(
    D,
    "workbooks_with_open_items",
    T["workbooks_with_open_items"],
    0,
    name="workbooks_with_open_items",
    weight=1.0,
)
rk.scalar(D, "top_status", T["top_status"], name="top_status", weight=1.0)
rk.scalar(
    D, "earliest_due_date", T["earliest_due_date"], name="earliest_due_date", weight=1.0
)
rk.flagged_f1(D, T["open_items"], name="open_items.f1", weight=5.0)
rk.row_fields(
    D,
    T["open_items"],
    {"status": 0, "owner": 0, "due_date": 0},
    name="row_facts",
    weight=6.0,
)
