"""Meeting notes: captured transcripts become meetings.db.

The firm's notetaker. Separate from the calendar on purpose, because it
is separate in every real workplace — the diary is Google's and the
transcript is Otter's — and because the calendar system mirrors Google's
official MCP surface tool for tool, which three extra tools would break.
"""

from tools.framework import ToolSystem
from tools.meetings.project import project
from tools.meetings.server import register
from tools.meetings.tables import MEETINGS, PARTICIPANTS, UTTERANCES

SYSTEM = ToolSystem(
    name="meetings",
    handled_tags=(
        "meeting.transcript",
        # The titles a meeting is listed under come from the diary, and
        # are recovered from the log rather than by reading another
        # system's database.
        "calendar.event.scheduled",
        "person.record",
    ),
    tables=(MEETINGS, UTTERANCES, PARTICIPANTS),
    project=project,
    register=register,
    directory_tool=False,
)

__all__ = ["SYSTEM"]
