"""Row models and tables for the meeting-notes database.

Times are simulated seconds, like every other projection; the served
ISO-8601 moments derive from the shared meta table's epoch.
"""

from typing import Annotated

from pydantic import BaseModel

from tools.db import Id, Ref, Table


class Meeting(BaseModel):
    """A meeting the notetaker captured, and how much was said in it.

    `calendar_event_id` is nullable because a meeting can convene without
    one — the world's referee opens a meeting from a convene event, and
    the diary entry it came from may have been quarantined or absent.
    """

    meeting_id: Annotated[str, Id("meeting")]
    calendar_event_id: Annotated[str | None, Ref("calendar.event")] = None
    title: str
    started: int
    ended: int
    turn_count: int
    word_count: int


class Utterance(BaseModel):
    """One person speaking once. `position` orders them within a meeting.

    Order is the meeting. "Thursday is tight" means nothing except after
    the sentence that proposed Thursday, so the position is a column
    rather than an accident of insertion.
    """

    meeting_id: Annotated[str, Ref("meeting")]
    position: int
    speaker: Annotated[str, Ref("person")]
    text: str


class Participant(BaseModel):
    meeting_id: Annotated[str, Ref("meeting")]
    person_id: Annotated[str, Ref("person")]


MEETINGS = Table("meetings", Meeting, primary_key=("meeting_id",))
UTTERANCES = Table("utterances", Utterance, primary_key=("meeting_id", "position"))
PARTICIPANTS = Table(
    "participants", Participant, primary_key=("meeting_id", "person_id")
)
