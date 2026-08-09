from typing import Literal

from pydantic import Field

from workbench.core.events._base import Payload
from workbench.core.ids import PersonId, TicketId


class TimeLoggedPayload(Payload):
    """A billable or tracked time entry against a matter."""

    kind: Literal["work.time.logged"]
    person_id: PersonId
    ticket_id: TicketId
    minutes: int = Field(ge=1)
    note: str
