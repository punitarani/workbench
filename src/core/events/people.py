from typing import Literal

from core.events._base import Payload
from core.ids import OrgId, PersonId


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
    organization: OrgId | None = None


class OrganizationRecordPayload(Payload):
    kind: Literal["org.record"]
    org_id: OrgId
    name: str
    category: Literal["client", "vendor", "court", "opposing", "other"]
