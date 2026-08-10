"""Diagnostic process criteria for the cross-system audit."""

import rewardkit as rk

TRAJECTORY = "/logs/agent/trajectory.json"

rk.tool_invoked(
    "list_activities",
    path=TRAJECTORY,
    name="opened_clio_activities",
    weight=2.0,
)
rk.tool_invoked(
    "list_notes",
    path=TRAJECTORY,
    name="opened_clio_notes",
    weight=1.0,
)
rk.tool_invoked(
    "search_threads",
    path=TRAJECTORY,
    name="searched_mail",
    weight=2.0,
)
rk.tool_invoked(
    "slack_search_channels",
    path=TRAJECTORY,
    name="listed_slack_conversations",
    weight=1.0,
)
rk.tool_invoked(
    "slack_read_channel",
    path=TRAJECTORY,
    name="read_slack_conversations",
    weight=3.0,
)
rk.tool_invoked(
    "slack_search_users",
    path=TRAJECTORY,
    name="resolved_slack_senders",
    weight=1.0,
)
rk.trajectory_turn_count(
    max_turns=240,
    path=TRAJECTORY,
    name="turn_efficiency",
    weight=3.0,
)
