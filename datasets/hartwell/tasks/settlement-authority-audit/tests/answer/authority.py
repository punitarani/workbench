"""Answer criteria for settlement-authority-audit."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "authority.json"

rk.identity_fields(D, T, name="matter_identity", weight=3.0)
rk.role_fields(D, T, name="matter_roles", weight=3.0)
for key in ("proposal_count", "authorized_count", "breach_count"):
    rk.field_equals(D, key, T[key], name=key, weight=1.0)
rk.breach_f1(D, T["breach_message_ids"], name="breach_ids.f1", weight=8.1)
rk.breach_exact(D, T["breach_message_ids"], name="breach_ids.certified", weight=0.9)
rk.timeline_f1(D, T["authority_timeline"], name="authority_timeline.f1", weight=19.8)
rk.timeline_exact(
    D, T["authority_timeline"], name="authority_timeline.certified", weight=2.2
)
rk.proposal_f1(D, T["proposal_audit"], name="proposal_audit.f1", weight=50.4)
rk.proposal_exact(
    D, T["proposal_audit"], name="proposal_audit.certified", weight=5.6
)
rk.exact_schema(D, name="deliverable_format", weight=4.0)
