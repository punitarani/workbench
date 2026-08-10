"""Diagnostic process criteria for standard-drift."""

import rewardkit as rk

TRAJECTORY = "/logs/agent/trajectory.json"
rk.tool_invoked(
    "search_workspaces", path=TRAJECTORY, name="found_firm_workspace", weight=2.0
)
rk.tool_invoked(
    "get_container_children", path=TRAJECTORY, name="enumerated_documents", weight=3.0
)
rk.tool_invoked(
    "get_document_versions", path=TRAJECTORY, name="walked_versions", weight=5.0
)
rk.tool_invoked(
    "search_threads", path=TRAJECTORY, name="checked_covering_mail", weight=2.0
)
rk.trajectory_turn_count(
    max_turns=120, path=TRAJECTORY, name="turn_efficiency", weight=3.0
)
