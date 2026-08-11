"""Diagnostic process criteria for settlement-authority-audit."""

import rewardkit as rk

P = "/logs/agent/trajectory.json"
rk.tool_invoked("list_matters", path=P, name="resolved_matter", weight=2.0)
rk.tool_invoked("search_threads", path=P, name="reviewed_negotiation_mail", weight=5.0)
rk.tool_invoked(
    "slack_search_public_and_private",
    path=P,
    name="reviewed_phone_authority",
    weight=5.0,
)
rk.trajectory_turn_count(max_turns=90, path=P, name="turn_efficiency", weight=3.0)
