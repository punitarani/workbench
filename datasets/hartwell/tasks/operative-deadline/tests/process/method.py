"""Diagnostic process criteria for operative-deadline."""

import rewardkit as rk

P = "/logs/agent/trajectory.json"
rk.tool_invoked("search_threads", path=P, name="read_clerk_notices", weight=4.0)
rk.tool_invoked("list_matters", path=P, name="resolved_matter_number", weight=2.0)
rk.tool_invoked(
    "slack_search_public_and_private",
    path=P,
    name="checked_private_correction",
    weight=5.0,
)
rk.tool_invoked("slack_search_public", path=P, name="checked_stale_chat", weight=2.0)
rk.trajectory_turn_count(max_turns=100, path=P, name="turn_efficiency", weight=3.0)
