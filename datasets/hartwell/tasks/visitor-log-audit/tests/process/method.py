"""Diagnostic process criteria for the visitor-log audit."""

import rewardkit as rk

TRAJECTORY = "/logs/agent/trajectory.json"

rk.tool_invoked(
    "slack_search_channels",
    path=TRAJECTORY,
    name="listed_dm_lanes",
    weight=2.0,
)
rk.tool_invoked(
    "slack_read_channel",
    path=TRAJECTORY,
    name="opened_dm_lanes",
    weight=5.0,
)
rk.tool_invoked(
    "slack_search_users",
    path=TRAJECTORY,
    name="resolved_people",
    weight=1.0,
)
rk.tool_invoked(
    "search_threads",
    path=TRAJECTORY,
    name="checked_directed_mail",
    weight=3.0,
)
rk.trajectory_turn_count(
    max_turns=160,
    path=TRAJECTORY,
    name="turn_efficiency",
    weight=3.0,
)
