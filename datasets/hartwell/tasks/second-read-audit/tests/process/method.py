"""Diagnostic process criteria for second-read-audit."""

import rewardkit as rk

P = "/logs/agent/trajectory.json"
rk.tool_invoked("slack_search_channels", path=P, name="listed_dm_lanes", weight=2.0)
rk.tool_invoked("slack_read_channel", path=P, name="walked_dm_lanes", weight=5.0)
rk.tool_invoked("slack_search_users", path=P, name="resolved_people", weight=2.0)
rk.tool_invoked("search_threads", path=P, name="checked_mail_window", weight=3.0)
rk.trajectory_turn_count(max_turns=160, path=P, name="turn_efficiency", weight=3.0)
