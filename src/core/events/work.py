from typing import Literal

from pydantic import Field

from core.events._base import Payload
from core.ids import PersonId, TicketId


class TimeLoggedPayload(Payload):
    """A billable or tracked time entry against a matter.

    Money is part of the entry, not prose about it: ``rate_cents`` is the
    hourly rate the time is recorded at and ``billable`` says whether it
    will reach an invoice, so a projection can expose a real charge
    without inferring one. ``rate_cents`` stays optional because tracked
    time (internal work, a fixed-fee matter) legitimately has no rate.
    """

    kind: Literal["work.time.logged"]
    person_id: PersonId
    ticket_id: TicketId
    minutes: int = Field(ge=1)
    note: str
    rate_cents: int | None = Field(default=None, ge=0)
    billable: bool = True

    @property
    def amount_cents(self) -> int | None:
        if self.rate_cents is None or not self.billable:
            return None
        return round(self.rate_cents * self.minutes / 60)
