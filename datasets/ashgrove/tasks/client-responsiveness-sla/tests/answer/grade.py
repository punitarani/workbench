"""Answer criteria for the client responsiveness review.

Graded per thread. Tolerances sit on the hour figures because they are
arithmetic over timestamps the tools serve to the second, and a rounding
difference in the last place is not a wrong answer.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "sla_report.json"

rk.scalar(D, "threads_reviewed", T["threads_reviewed"], 0, name="threads", weight=1.0)
rk.scalar(
    D,
    "threads_with_client_inbound",
    T["threads_with_client_inbound"],
    0,
    name="client_threads",
    weight=1.5,
)
rk.scalar(D, "inbound_total", T["inbound_total"], 0, name="inbound_total", weight=1.5)
rk.scalar(
    D, "unanswered_total", T["unanswered_total"], 0, name="unanswered_total", weight=1.5
)
rk.scalar(
    D,
    "firm_median_reply_hours",
    T["firm_median_reply_hours"],
    0.02,
    name="firm_median_reply_hours",
    weight=1.5,
)
rk.scalar(D, "slowest_thread", T["slowest_thread"], name="slowest_thread", weight=1.0)
rk.flagged_f1(D, T["threads"], name="threads.f1", weight=2.0)
rk.row_fields(
    D,
    T["threads"],
    {
        "client": 0,
        "messages": 0,
        "inbound": 0,
        "unanswered": 0,
        "first_reply_hours": 0.02,
        "longest_reply_hours": 0.02,
    },
    name="row_figures",
    weight=6.0,
)
