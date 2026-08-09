"""Small shared SQLite helpers for tool projections."""

import sqlite3
from collections.abc import Iterable
from pathlib import Path


def create_db(path: Path, schema: str) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(schema)
    return connection


def insert(
    connection: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
    values: Iterable[tuple],
) -> None:
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        list(values),
    )


PEOPLE_SCHEMA = """
CREATE TABLE people (
    person_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email_address TEXT NOT NULL,
    title TEXT NOT NULL,
    department TEXT NOT NULL,
    affiliation TEXT NOT NULL
);
"""


def project_people(connection: sqlite3.Connection, events) -> None:
    from workbench.core.events.people import PersonRecordPayload

    insert(
        connection,
        "people",
        ("person_id", "name", "email_address", "title", "department", "affiliation"),
        (
            (
                e.payload.person_id,
                e.payload.name,
                e.payload.email_address,
                e.payload.title,
                e.payload.department,
                e.payload.affiliation,
            )
            for e in events
            if isinstance(e.payload, PersonRecordPayload)
        ),
    )
