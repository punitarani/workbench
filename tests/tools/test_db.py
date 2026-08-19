"""The typed data layer: Pydantic row models are the schema."""

import sqlite3
from pathlib import Path
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel

from tools.db import (
    Id,
    Query,
    Ref,
    SchemaError,
    Table,
    connect_readonly,
    create_db,
)


class Song(BaseModel):
    song_id: Annotated[str, Id("song")]
    album_id: Annotated[str | None, Ref("album")]
    title: str
    plays: int
    rating: float
    mood: Literal["calm", "loud"]


SONGS = Table("songs", Song, primary_key=("song_id",))


def sample(**overrides) -> Song:
    base = dict(
        song_id="sng-1",
        album_id=None,
        title="Silence",
        plays=3,
        rating=4.5,
        mood="calm",
    )
    return Song(**{**base, **overrides})


def test_ddl_derives_types_nullability_and_checks() -> None:
    ddl = SONGS.ddl()
    assert "song_id TEXT NOT NULL" in ddl
    assert "album_id TEXT," in ddl
    assert "plays INTEGER NOT NULL" in ddl
    assert "rating REAL NOT NULL" in ddl
    assert "mood TEXT NOT NULL CHECK (mood IN ('calm', 'loud'))" in ddl
    assert "PRIMARY KEY (song_id)" in ddl


def test_composite_primary_key() -> None:
    class Revision(BaseModel):
        document_id: str
        revision: int

    table = Table("revisions", Revision, primary_key=("document_id", "revision"))
    assert "PRIMARY KEY (document_id, revision)" in table.ddl()


def test_unknown_primary_key_column_is_rejected() -> None:
    with pytest.raises(SchemaError, match="nope"):
        Table("songs", Song, primary_key=("nope",))


def test_unsupported_annotation_is_rejected() -> None:
    class Bad(BaseModel):
        values: list[str]

    with pytest.raises(SchemaError, match="values"):
        Table("bad", Bad)


def test_insert_and_select_round_trip_models(tmp_path: Path) -> None:
    db = tmp_path / "songs.db"
    with create_db(db, (SONGS,)) as connection:
        SONGS.insert(connection, [sample(), sample(song_id="sng-2", mood="loud")])
    rows = SONGS.select(connect_readonly(db), order_by="song_id")
    assert [r.song_id for r in rows] == ["sng-1", "sng-2"]
    assert isinstance(rows[0], Song)
    assert rows[0].album_id is None
    assert rows[1].mood == "loud"


def test_select_filters_with_where(tmp_path: Path) -> None:
    db = tmp_path / "songs.db"
    with create_db(db, (SONGS,)) as connection:
        SONGS.insert(connection, [sample(), sample(song_id="sng-2", mood="loud")])
        loud = SONGS.select(connection, where={"mood": "loud"})
        assert [r.song_id for r in loud] == ["sng-2"]


def test_select_rejects_unknown_columns(tmp_path: Path) -> None:
    db = tmp_path / "songs.db"
    with create_db(db, (SONGS,)) as connection:
        with pytest.raises(SchemaError, match="ghost"):
            SONGS.select(connection, where={"ghost": "x"})
        with pytest.raises(SchemaError, match="ghost"):
            SONGS.select(connection, order_by="ghost")


def test_insert_rejects_foreign_rows(tmp_path: Path) -> None:
    class Impostor(BaseModel):
        song_id: str

    db = tmp_path / "songs.db"
    with create_db(db, (SONGS,)) as connection:
        with pytest.raises(SchemaError, match="Song"):
            SONGS.insert(connection, [Impostor(song_id="sng-3")])


def test_query_returns_validated_models(tmp_path: Path) -> None:
    class MoodCount(BaseModel):
        mood: str
        n: int

    by_mood = Query(
        MoodCount,
        "SELECT mood, COUNT(*) AS n FROM songs WHERE plays >= ? GROUP BY mood",
    )
    db = tmp_path / "songs.db"
    with create_db(db, (SONGS,)) as connection:
        SONGS.insert(
            connection,
            [sample(), sample(song_id="sng-2"), sample(song_id="sng-3", mood="loud")],
        )
        counts = by_mood.run(connection, 0)
    assert {(c.mood, c.n) for c in counts} == {("calm", 2), ("loud", 1)}
    assert all(isinstance(c, MoodCount) for c in counts)


def test_id_and_ref_metadata_are_discoverable() -> None:
    assert SONGS.ids() == {"song_id": Id("song")}
    assert SONGS.refs() == {"album_id": Ref("album")}


def test_create_db_replaces_existing_file(tmp_path: Path) -> None:
    db = tmp_path / "songs.db"
    with create_db(db, (SONGS,)) as connection:
        SONGS.insert(connection, [sample()])
    with create_db(db, (SONGS,)):
        pass
    assert SONGS.select(connect_readonly(db)) == []


def test_readonly_connection_refuses_writes(tmp_path: Path) -> None:
    db = tmp_path / "songs.db"
    with create_db(db, (SONGS,)):
        pass
    with pytest.raises(sqlite3.OperationalError):
        connect_readonly(db).execute("INSERT INTO songs (song_id) VALUES ('x')")


def test_bool_columns_round_trip(tmp_path: Path) -> None:
    """bool subclasses int, so the affinity map needs its own entry; SQLite
    stores it as 0/1 and pydantic restores the type on the way out."""

    class Flagged(BaseModel):
        flag_id: str
        billable: bool
        waived: bool | None

    table = Table("flags", Flagged, primary_key=("flag_id",))
    assert "billable INTEGER NOT NULL" in table.ddl()
    assert "waived INTEGER," in table.ddl()

    db = tmp_path / "flags.db"
    with create_db(db, (table,)) as connection:
        table.insert(
            connection,
            [
                Flagged(flag_id="a", billable=True, waived=None),
                Flagged(flag_id="b", billable=False, waived=True),
            ],
        )
    rows = table.select(connect_readonly(db), order_by="flag_id")
    assert [r.billable for r in rows] == [True, False]
    assert [r.waived for r in rows] == [None, True]
