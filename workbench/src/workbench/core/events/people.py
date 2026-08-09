from typing import Literal

from workbench.core.events._base import Payload
from workbench.core.ids import PersonId


class PersonRecordPayload(Payload):
    kind: Literal["person.record"]
    person_id: PersonId
    name: str
    email_address: str
    title: str
    department: str
    manager: PersonId | None
    affiliation: Literal["internal", "external"]
    timezone: str
