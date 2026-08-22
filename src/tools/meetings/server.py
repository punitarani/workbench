"""Meeting notes: a read-only surface over captured transcripts.

Modelled on the shape every meeting-notetaker product converges on —
Otter, Gong, Fireflies, Granola all expose the same three reads: list the
meetings, open one whole, and search across what was said. This is *not*
claimed as byte-parity with a captured vendor API, unlike the five
systems that mirror a specific official MCP server; it is the common
shape, named the way those products name things.

Deliberately three reads and no writes. A notetaker is a record of what
was said, and an agent that could edit it could edit the evidence.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from tools.db import connect_readonly
from tools.framework import (
    PEOPLE_TABLE,
    MCPServer,
    Person,
    UnknownRefError,
    read_epoch,
)
from tools.meetings.tables import MEETINGS, PARTICIPANTS, UTTERANCES

# The list is an index and the transcript is the text. Returning every
# word from the list would make the index cost what reading everything
# costs, which is exactly the shape that lets one call flatten a corpus.
_MAX_MEETINGS = 250
_MAX_HITS = 250


def _people(connection: sqlite3.Connection) -> dict[str, Person]:
    return {
        person.person_id: person
        for person in PEOPLE_TABLE.select(connection, order_by="person_id")
    }


def _speaker(people: dict[str, Person], person_id: str) -> dict[str, str]:
    """A speaker as a principal, degrading rather than raising.

    A transcript can name somebody the directory no longer carries — a
    departure inside a six-month window is ordinary — and raising there
    would lose a whole meeting over one display name.
    """

    person = people.get(person_id)
    return (
        {"email": person.email_address, "name": person.name}
        if person is not None
        else {"email": "", "name": person_id}
    )


def _moment(epoch: datetime, seconds: int) -> str:
    return (epoch + timedelta(seconds=seconds)).isoformat()


def _bound(value: str, epoch: datetime) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=epoch.tzinfo)
    return int((parsed - epoch).total_seconds())


def _paged(items: list, page_size: int, page_token: str | None, cap: int):
    size = min(max(page_size, 1), cap)
    offset = max(int(page_token), 0) if page_token else 0
    exhausted = offset + size >= len(items)
    return items[offset : offset + size], (None if exhausted else str(offset + size))


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_meetings(
        startTime: str | None = None,
        endTime: str | None = None,
        participant: str | None = None,
        pageSize: int = 100,
        pageToken: str | None = None,
    ) -> dict:
        """List meetings that were captured, oldest first. startTime and
        endTime are ISO-8601 bounds on when the meeting was held;
        participant is an email address. Returns each meeting's id, title,
        times, who was there, and how much was said — not the words. Read
        those with get_transcript."""
        with connect_readonly(db_path) as connection:
            epoch = read_epoch(connection)
            people = _people(connection)
            rows = sorted(
                MEETINGS.select(connection, order_by="started"),
                key=lambda m: (m.started, m.meeting_id),
            )
            present: dict[str, list[str]] = {}
            for row in PARTICIPANTS.select(connection, order_by="person_id"):
                present.setdefault(row.meeting_id, []).append(row.person_id)
        after = None if startTime is None else _bound(startTime, epoch)
        before = None if endTime is None else _bound(endTime, epoch)
        wanted = None
        if participant is not None:
            needle = participant.strip().casefold()
            wanted = next(
                (
                    p.person_id
                    for p in people.values()
                    if p.email_address.casefold() == needle
                ),
                participant,
            )
        items = []
        for meeting in rows:
            if after is not None and meeting.ended < after:
                continue
            if before is not None and meeting.started > before:
                continue
            here = present.get(meeting.meeting_id, [])
            if wanted is not None and wanted not in here:
                continue
            items.append(
                {
                    "meetingId": meeting.meeting_id,
                    "eventId": meeting.calendar_event_id,
                    "title": meeting.title,
                    "start": _moment(epoch, meeting.started),
                    "end": _moment(epoch, meeting.ended),
                    "turnCount": meeting.turn_count,
                    "wordCount": meeting.word_count,
                    "participants": [_speaker(people, p) for p in here],
                }
            )
        page, token = _paged(items, pageSize, pageToken, _MAX_MEETINGS)
        return {"meetings": page, "nextPageToken": token}

    @server.tool()
    def get_transcript(meetingId: str) -> dict:
        """Read what was said in one meeting: every turn in order, with the
        speaker. This is the record of the meeting, not a summary of it."""
        with connect_readonly(db_path) as connection:
            epoch = read_epoch(connection)
            people = _people(connection)
            found = MEETINGS.select(connection, where={"meeting_id": meetingId})
            if not found:
                # Refusing beats returning an empty transcript: a meeting
                # that convened and produced no speech is a real state
                # here, and the two must not look alike.
                raise UnknownRefError(f"no meeting {meetingId}")
            meeting = found[0]
            turns = UTTERANCES.select(
                connection, where={"meeting_id": meetingId}, order_by="position"
            )
            here = [
                p.person_id
                for p in PARTICIPANTS.select(
                    connection, where={"meeting_id": meetingId}, order_by="person_id"
                )
            ]
        return {
            "meetingId": meeting.meeting_id,
            "eventId": meeting.calendar_event_id,
            "title": meeting.title,
            "start": _moment(epoch, meeting.started),
            "end": _moment(epoch, meeting.ended),
            "turnCount": meeting.turn_count,
            "wordCount": meeting.word_count,
            "participants": [_speaker(people, p) for p in here],
            "turns": [
                {
                    "position": t.position,
                    "speaker": _speaker(people, t.speaker),
                    "text": t.text,
                }
                for t in turns
            ],
        }

    @server.tool()
    def search_transcripts(
        query: str, pageSize: int = 100, pageToken: str | None = None
    ) -> dict:
        """Find turns whose text contains `query`, case-insensitively, so a
        phrase can be traced back to the room it was said in and the person
        who said it."""
        needle = (query or "").lower()
        with connect_readonly(db_path) as connection:
            epoch = read_epoch(connection)
            people = _people(connection)
            titles = {
                m.meeting_id: (m.title, m.started)
                for m in MEETINGS.select(connection, order_by="meeting_id")
            }
            turns = UTTERANCES.select(connection, order_by="position")
        items = [
            {
                "meetingId": t.meeting_id,
                "position": t.position,
                "speaker": _speaker(people, t.speaker),
                "text": t.text,
                "title": titles.get(t.meeting_id, ("", 0))[0],
                "start": _moment(epoch, titles.get(t.meeting_id, ("", 0))[1]),
            }
            for t in turns
            if needle in (t.text or "").lower()
        ]
        items.sort(key=lambda hit: (hit["start"], hit["meetingId"], hit["position"]))
        page, token = _paged(items, pageSize, pageToken, _MAX_HITS)
        return {"hits": page, "nextPageToken": token}
