"""Calendar: scheduled events, updates, and responses become calendar.db.

Mirrors the read half of Google's official Calendar MCP server
(``list_events``, ``get_event``, ``list_calendars``) over Calendar API v3
response shapes. Calendars are people, keyed by email address.
"""

from workbench.tools.calendar.project import project
from workbench.tools.calendar.server import register
from workbench.tools.calendar.tables import ATTENDEES, CALENDAR_EVENTS
from workbench.tools.framework import ToolSystem

SYSTEM = ToolSystem(
    name="calendar",
    handled_tags=(
        "calendar.event.scheduled",
        "calendar.event.updated",
        "calendar.response",
        "person.record",
    ),
    tables=(CALENDAR_EVENTS, ATTENDEES),
    project=project,
    register=register,
    directory_tool=False,
)
