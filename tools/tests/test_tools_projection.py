"""Registry-level projection invariants over the product systems."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from projection_fixtures import coherent_events

from workbench.tools import REGISTRY, check_coherence, project_all
from workbench.tools.framework import read_epoch

DBS = sorted(f"{system.name}.db" for system in REGISTRY)


def project_fixture(tmp_path: Path) -> Path:
    out = tmp_path / "state"
    project_all(coherent_events(), out)
    return out


def test_every_registered_system_projects(tmp_path: Path) -> None:
    assert DBS == ["calendar.db", "clio.db", "gmail.db", "imanage.db", "slack.db"]
    out = project_fixture(tmp_path)
    assert sorted(p.name for p in out.iterdir()) == DBS


def test_sim_events_never_project(tmp_path: Path) -> None:
    assert not any(
        tag.startswith("sim.") for system in REGISTRY for tag in system.handled_tags
    )
    out = project_fixture(tmp_path)
    for db in out.iterdir():
        with sqlite3.connect(db) as connection:
            tables = [
                r[0]
                for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            ]
            for table in tables:
                for row in connection.execute(f"SELECT * FROM {table}"):  # noqa: S608
                    for value in row:
                        assert "sim." not in str(value)
                        assert "config_hash" not in str(value)


def test_meta_carries_calendar_epoch_and_timezone(tmp_path: Path) -> None:
    """Calendar origin data is onstage; run identity stays offstage."""
    out = project_fixture(tmp_path)
    for name in DBS:
        with sqlite3.connect(out / name) as connection:
            rows = connection.execute("SELECT key, value FROM meta").fetchall()
        assert rows == [
            ("epoch", "2026-03-12T00:00:00-07:00"),
            ("timezone", "America/Los_Angeles"),
        ], name


def test_calendar_timezone_preserves_wall_clock_across_dst(tmp_path: Path) -> None:
    events = coherent_events()
    started = events[0]
    events[0] = started.model_copy(
        update={
            "payload": started.payload.model_copy(
                update={
                    "epoch": "2026-03-02T00:00:00-08:00",
                    "timezone": "America/Los_Angeles",
                }
            )
        }
    )
    chat_index = next(
        index
        for index, event in enumerate(events)
        if getattr(event.payload, "chat_message_id", None) == "chm-000001"
    )
    simulated_time = 7 * 86_400 + 12 * 3_600
    events[chat_index] = events[chat_index].model_copy(update={"time": simulated_time})
    out = tmp_path / "state"
    project_all(events, out)

    with sqlite3.connect(out / "slack.db") as connection:
        epoch = read_epoch(connection)
        [(timestamp,)] = connection.execute(
            "SELECT ts FROM messages WHERE chat_message_id = 'chm-000001'"
        ).fetchall()

    assert epoch.tzinfo == ZoneInfo("America/Los_Angeles")
    assert (epoch + timedelta(seconds=simulated_time)).isoformat() == (
        "2026-03-09T12:00:00-07:00"
    )
    expected = int(
        datetime(2026, 3, 9, 12, tzinfo=ZoneInfo("America/Los_Angeles")).timestamp()
    )
    assert timestamp == f"{expected}.000000"


def test_projection_is_content_deterministic(tmp_path: Path) -> None:
    first = project_fixture(tmp_path / "a")
    second = project_fixture(tmp_path / "b")
    for name in DBS:
        with (
            sqlite3.connect(first / name) as db_a,
            sqlite3.connect(second / name) as db_b,
        ):
            assert list(db_a.iterdump()) == list(db_b.iterdump())


def test_coherence_clean_on_fixture(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    assert check_coherence(out) == ()


def test_coherence_catches_dangling_reference(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    with sqlite3.connect(out / "clio.db") as connection:
        connection.execute(
            "UPDATE matters SET responsible_person='per-ghost' "
            "WHERE responsible_person IS NOT NULL"
        )
    findings = check_coherence(out)
    assert findings, "a dangling person reference must be reported"
    assert any("per-ghost" in f.detail for f in findings)


async def test_servers_render_dates_from_the_workspace_epoch(tmp_path: Path) -> None:
    """A workspace built on a non-default epoch (the hartwell Monday) must
    serve calendar dates derived from its own record, not any constant."""
    import json

    from workbench.tools import build_server

    events = coherent_events()
    started = events[0]
    events[0] = started.model_copy(
        update={
            "payload": started.payload.model_copy(
                update={"epoch": "2026-03-02T00:00:00-08:00"}
            )
        }
    )
    out = tmp_path / "state"
    project_all(events, out)

    gmail = build_server("gmail", out / "gmail.db")
    result = await gmail.call_tool("get_message", {"messageId": "msg-000001"})
    [content] = [c for c in result.content if hasattr(c, "text")]
    message = json.loads(content.text)
    assert message["date"].startswith("2026-03-02T"), message["date"]
    assert message["date"].endswith("-08:00"), message["date"]

    clio = build_server("clio", out / "clio.db")
    result = await clio.call_tool("list_matters", {})
    [content] = [c for c in result.content if hasattr(c, "text")]
    [matter] = json.loads(content.text)["data"]
    assert matter["open_date"] == "2026-03-02", matter
