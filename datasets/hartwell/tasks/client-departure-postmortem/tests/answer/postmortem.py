"""Answer criteria for client-departure-postmortem."""

import json
from pathlib import Path

import rewardkit as rk

TRUTH = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
D = "postmortem.json"
rk.field_equals(
    D, "first_negative_signal_date", TRUTH["first_negative_signal_date"], weight=4.0
)
rk.field_prefix(
    D, "first_negative_signal_ts", TRUTH["first_negative_signal_ts_prefix"], weight=7.0
)
rk.field_prefix(D, "happy_update_ts", TRUTH["happy_update_ts_prefix"], weight=4.0)
rk.field_equals(
    D, "happy_update_reactions", TRUTH["happy_update_reactions"], weight=2.0
)
rk.field_equals(
    D,
    "first_negative_signal_reactions",
    TRUTH["first_negative_signal_reactions"],
    weight=2.0,
)
rk.ordered_similarity(
    D, "reaction_trajectory", TRUTH["reaction_trajectory"], weight=8.0
)
rk.field_equals(D, "matter_closed_date", TRUTH["matter_closed_date"], weight=6.0)
rk.field_equals(
    D, "termination_email_date", TRUTH["termination_email_date"], weight=4.0
)
rk.field_suffix(D, "disengagement_letter_path", TRUTH["letter_path_suffix"], weight=4.0)
rk.set_f1(
    D,
    "unanswered_client_emails",
    TRUTH["unanswered_client_emails"],
    name="unanswered_client_emails.f1",
    weight=50.4,
)
rk.exact_set(
    D,
    "unanswered_client_emails",
    TRUTH["unanswered_client_emails"],
    name="unanswered_client_emails.certified",
    weight=5.6,
)
rk.exact_schema(D, name="deliverable_format", weight=3.0)
