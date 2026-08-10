"""Process: did the agent actually do the work, and at what cost.

Grading only the deliverable cannot tell a reconstruction from a guess. The
failure audit found an episode that never opened a single DM on a task whose
instruction names DMs as the trap and still submitted an answer, and another
that quit at 31% of its budget — neither is visible in the JSON. Reward Kit's
trajectory criteria make method gradeable: which surfaces were actually
queried, and how many turns it took.

The turn budget replaces the old hard call cap. That cap was a cliff — one
call over and the episode scored as if it had never tried — and Harbor has no
equivalent anyway. ``trajectory_turn_count`` decays linearly instead, so
inefficiency costs something proportionate. The reference tool path is 49
calls; 60 turns is a generous ceiling over that, reaching zero at 120.

The four surface criteria use ``tool_invoked`` from tests/criteria.py rather
than Reward Kit's ``trajectory_tool_used``: under Codex's ``unified_exec``
every tool call is a ``tools.<name>()`` expression inside one ``exec`` blob,
so the built-in — which matches ATIF ``function_name`` — never fires. Our
criterion matches the function name *and* the arguments, so it reads both
shapes. Tool names are the servers' own, read from the registered surface.
"""

import rewardkit as rk

# Bind-mounted from the trial directory, written by the agent adapter before
# verification runs. Reward Kit's default (/logs/trajectory.json) is one level
# up from where Harbor actually puts it.
TRAJECTORY = "/logs/agent/trajectory.json"

# The time entries themselves: no route to the disputed minutes avoids this.
rk.tool_invoked(
    "list_activities",
    min_count=1,
    path=TRAJECTORY,
    name="opened_clio_activities",
    weight=2.0,
)

# The challenger exists only in the mail record.
rk.tool_invoked(
    "search_threads",
    min_count=1,
    path=TRAJECTORY,
    name="searched_mail",
    weight=2.0,
)

# The cutoff date is stated in exactly one place: a #billing channel post.
rk.tool_invoked(
    "slack_read_channel",
    min_count=1,
    path=TRAJECTORY,
    name="read_slack_channel",
    weight=2.0,
)

# The support audit's hardest days are covered only inside a DM. Channel
# search never returns them, so an agent that never runs the DM-inclusive
# search cannot have checked every surface — whatever its answer says.
rk.tool_invoked(
    "slack_search_public_and_private",
    min_count=1,
    path=TRAJECTORY,
    name="searched_slack_dms",
    weight=3.0,
)

rk.trajectory_turn_count(
    max_turns=60,
    path=TRAJECTORY,
    name="turn_efficiency",
    weight=3.0,
)
