"""Diagnostic process criteria for client-departure-postmortem."""

import rewardkit as rk

P = "/logs/agent/trajectory.json"
rk.tool_invoked("slack_search_public", path=P, name="searched_internal_arc", weight=3.0)
rk.tool_invoked("search_threads", path=P, name="walked_client_mail", weight=4.0)
rk.tool_invoked("get_matter", path=P, name="checked_matter", weight=2.0)
rk.tool_invoked("search_documents", path=P, name="found_letter", weight=2.0)
rk.trajectory_turn_count(max_turns=40, path=P, name="turn_efficiency", weight=3.0)
