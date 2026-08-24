"""Project meeting transcripts into the meeting-notes database.

`meeting.transcript` has been a validated world event from the beginning
— in `TAG_REGISTRY`, banded in `docs/fidelity/bands.json` at a floor of
0.30, documented in `docs/WORKBENCH.md` — and until this module existed,
**no projection, no table, no file and no tool served a single one**. A
six-month recording of a twenty-one-person law firm held 723 transcripts,
3,662 turns and 255,889 words, roughly 30% of everything anyone there
said or wrote, and an agent could read every email and every message in
the firm without learning what was decided in any room.

Nothing failed, because nothing looked. The tell was there to be read:
`simulation/persona/memory_stream.py` had a handler for the payload and
the projection layer did not.
"""

import sqlite3
from collections.abc import Sequence

from core.events import Event
from core.events.meetings import MeetingTranscriptPayload
from tools.meetings.tables import (
    MEETINGS,
    PARTICIPANTS,
    UTTERANCES,
    Meeting,
    Participant,
    Utterance,
)

# What a meeting is called when the transcript carries no title of its
# own. Deliberately plain: an invented title would be a fact about the
# world that nobody in the world ever wrote.
_UNTITLED = "Meeting"


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    meetings: dict[str, Meeting] = {}
    utterances: list[Utterance] = []
    participants: list[Participant] = []

    # Titles come from the diary, which is projected by a different system
    # into a different database, so they are recovered here from the same
    # log rather than by reading across surfaces.
    titles: dict[str, str] = {}
    for event in events:
        payload = event.payload
        if getattr(payload, "kind", None) == "calendar.event.scheduled":
            titles[payload.calendar_event_id] = payload.title

    for event in events:
        payload = event.payload
        if not isinstance(payload, MeetingTranscriptPayload):
            continue
        turns = payload.turns
        meetings[payload.meeting_id] = Meeting(
            meeting_id=payload.meeting_id,
            calendar_event_id=payload.calendar_event_id,
            title=titles.get(payload.calendar_event_id or "", _UNTITLED),
            started=int(payload.started),
            ended=int(payload.ended),
            turn_count=len(turns),
            word_count=sum(len((turn.text or "").split()) for turn in turns),
        )
        utterances.extend(
            Utterance(
                meeting_id=payload.meeting_id,
                position=position,
                speaker=turn.speaker,
                text=turn.text,
            )
            for position, turn in enumerate(turns)
        )
        participants.extend(
            Participant(meeting_id=payload.meeting_id, person_id=person)
            for person in payload.attendees
        )

    MEETINGS.insert(connection, meetings.values())
    UTTERANCES.insert(connection, utterances)
    PARTICIPANTS.insert(connection, participants)
