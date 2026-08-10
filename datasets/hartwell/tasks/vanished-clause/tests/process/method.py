"""Diagnostic process criteria for vanished-clause."""

import rewardkit as rk

P = "/logs/agent/trajectory.json"
rk.tool_invoked("search_workspaces", path=P, name="enumerated_workspaces", weight=2.0)
rk.tool_invoked(
    "get_container_children", path=P, name="enumerated_documents", weight=3.0
)
rk.tool_invoked("get_document_versions", path=P, name="walked_all_versions", weight=6.0)
rk.tool_invoked("search_threads", path=P, name="checked_mail_mentions", weight=2.0)
rk.tool_invoked(
    "slack_search_public", path=P, name="checked_public_mentions", weight=2.0
)
rk.trajectory_turn_count(max_turns=420, path=P, name="turn_efficiency", weight=3.0)
