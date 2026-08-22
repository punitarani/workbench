"""What was said in the room has to reach a surface.

`meeting.transcript` has been a validated world event from the beginning
— in `TAG_REGISTRY`, banded in `docs/fidelity/bands.json` at a floor of
0.30, documented in `docs/WORKBENCH.md` — and no projection, no table, no
file and no tool served a single one. A six-month recording of a
twenty-one-person law firm held **723 transcripts, 3,662 turns and
255,889 words, roughly 30% of everything anyone there said or wrote**,
and an agent could read every email and every message in the firm without
learning what was decided in any room.

Nothing failed, because nothing looked. This is the largest instance in
this tree of a capability with no caller, and the tell was there to read:
`simulation/persona/memory_stream.py` had a handler for the payload and
the projection layer did not.

The notetaker is its own system rather than three extra tools on the
calendar, for the same reason it is its own product in every real
workplace — and because the calendar system mirrors Google's official MCP
surface tool for tool, which its parity test enforces.
"""

import json
import sqlite3
from pathlib import Path

import pytest
from projection_fixtures import coherent_events

from core.events import Event
from core.events.meetings import MeetingTranscriptPayload, TranscriptTurn
from tools.framework import build_server, project_system
from tools.meetings import SYSTEM

SPOKEN = "mtg-000001"
SILENT = "mtg-000002"


def _events() -> list[Event]:
    base = coherent_events()
    seq = max(e.seq for e in base)
    spoken = MeetingTranscriptPayload(
        kind="meeting.transcript",
        meeting_id=SPOKEN,
        calendar_event_id=None,
        attendees=("per-daniel-reyes", "per-jess-alvarez", "per-tom-okafor"),
        started=36000,
        ended=39600,
        turns=(
            TranscriptTurn(
                speaker="per-daniel-reyes",
                text="I will take the redline and have it back Thursday.",
            ),
            TranscriptTurn(
                speaker="per-jess-alvarez",
                text="Thursday is tight, the client wants it Wednesday.",
            ),
            TranscriptTurn(
                speaker="per-tom-okafor",
                text="Wednesday works if I clear the conflicts check today.",
            ),
        ),
    )
    quiet = MeetingTranscriptPayload(
        kind="meeting.transcript",
        meeting_id=SILENT,
        calendar_event_id=None,
        attendees=("per-daniel-reyes",),
        started=90000,
        ended=93600,
        turns=(),
    )
    return [
        *base,
        Event(
            seq=seq + 1,
            event_id=f"evt-{seq + 1:06d}",
            time=39600,
            tag=spoken.kind,
            source="gm",
            payload=spoken,
        ),
        Event(
            seq=seq + 2,
            event_id=f"evt-{seq + 2:06d}",
            time=93600,
            tag=quiet.kind,
            source="gm",
            payload=quiet,
        ),
    ]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "meetings.db"
    project_system(SYSTEM, _events(), path)
    return path


@pytest.fixture
def server(db_path: Path):
    return build_server(SYSTEM, db_path)


async def call(server, name: str, arguments: dict | None = None) -> dict:
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


def test_the_system_declares_the_tag() -> None:
    """The offstage boundary means an undeclared tag cannot reach the
    database at all, so declaring it is what makes the rest possible."""

    assert "meeting.transcript" in SYSTEM.handled_tags


def test_turns_reach_the_database_in_order(db_path: Path) -> None:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = connection.execute(
        "SELECT position, speaker, text FROM utterances WHERE meeting_id=? "
        "ORDER BY position",
        (SPOKEN,),
    ).fetchall()
    assert [r[0] for r in rows] == [0, 1, 2]
    assert rows[0][1] == "per-daniel-reyes"
    assert "redline" in rows[0][2]
    # Order is the meeting. "Thursday is tight" means nothing except after
    # the sentence that proposed Thursday.
    assert "Thursday is tight" in rows[1][2]


async def test_a_meeting_can_be_read_back_whole(server) -> None:
    result = await call(server, "get_transcript", {"meetingId": SPOKEN})
    assert result["turnCount"] == 3
    assert [t["position"] for t in result["turns"]] == [0, 1, 2]
    assert result["turns"][0]["speaker"]["name"] == "Daniel Reyes"
    assert {p["name"] for p in result["participants"]} == {
        "Daniel Reyes",
        "Jess Alvarez",
        "Tom Okafor",
    }


async def test_the_list_is_an_index_not_the_text(server) -> None:
    """Returning every word from the list would make the index cost what
    reading everything costs, which is the shape that lets one call
    flatten a corpus."""

    result = await call(server, "list_meetings")
    ids = [m["meetingId"] for m in result["meetings"]]
    assert SPOKEN in ids and SILENT in ids
    assert "turns" not in result["meetings"][0]
    assert result["meetings"][0]["turnCount"] == 3
    assert result["meetings"][0]["wordCount"] > 0


async def test_a_phrase_traces_back_to_the_room_and_the_speaker(server) -> None:
    result = await call(server, "search_transcripts", {"query": "conflicts check"})
    assert len(result["hits"]) == 1
    hit = result["hits"][0]
    assert hit["meetingId"] == SPOKEN
    assert hit["speaker"]["name"] == "Tom Okafor"
    assert hit["position"] == 2


async def test_search_is_case_insensitive(server) -> None:
    lower = await call(server, "search_transcripts", {"query": "redline"})
    upper = await call(server, "search_transcripts", {"query": "REDLINE"})
    assert len(lower["hits"]) == len(upper["hits"]) == 1


async def test_filtering_by_participant_uses_an_email(server) -> None:
    everyone = await call(server, "list_meetings")
    tom = await call(server, "list_meetings", {"participant": "tom@example.com"})
    assert [m["meetingId"] for m in tom["meetings"]] == [SPOKEN]
    assert len(everyone["meetings"]) > len(tom["meetings"])


async def test_a_meeting_where_nobody_spoke_is_still_a_meeting(server) -> None:
    """Zero turns is a real outcome — a meeting that convened and produced
    no speech — and must not look like a meeting that does not exist."""

    result = await call(server, "get_transcript", {"meetingId": SILENT})
    assert result["turnCount"] == 0
    assert result["turns"] == []


async def test_an_unknown_meeting_is_refused(server) -> None:
    """Refusing beats returning an empty transcript, because the empty
    case above is real and the two must not look alike."""

    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="mtg-999999"):
        await server.call_tool("get_transcript", {"meetingId": "mtg-999999"})


async def test_the_surface_is_crawlable(db_path: Path) -> None:
    """A task may only grade what the tools can spell.

    `analysis.reachability` refuses an oracle naming values no agent could
    obtain, by crawling every read tool: zero-argument tools seed the
    walk, `query`-only searches get an empty query, and single-argument
    getters are followed. This surface is built to satisfy all three —
    `list_meetings` seeds the meeting ids, `get_transcript` is followed
    from them, `search_transcripts` takes a bare query.

    Pinned because it is easy to lose by accident: give `list_meetings` a
    required argument and the crawl seeds nothing, the ids become
    unreachable, and every transcript-based oracle is refused by a gate
    whose message is about the oracle rather than about the tool.
    """

    from analysis.reachability import _collect, _follow, _is_read

    server = build_server(SYSTEM, db_path)
    tools = [tool for tool in await server.list_tools() if _is_read(tool.name)]
    assert {tool.name for tool in tools} == {
        "list_meetings",
        "get_transcript",
        "search_transcripts",
    }

    discovered: set[str] = set()
    for tool in tools:
        required = (tool.input_schema or {}).get("required") or []
        if not required:
            await _collect(server, tool.name, {}, discovered)
        elif required == ["query"]:
            await _collect(server, tool.name, {"query": ""}, discovered)
    assert SPOKEN in discovered, (
        "no meeting id is reachable without already knowing one; a "
        "transcript oracle would be refused as unservable"
    )

    reachable = discovered | await _follow(server, tools, discovered)
    assert any("conflicts check" in value for value in reachable), (
        "what was said is not reachable, so no task may quote it"
    )
