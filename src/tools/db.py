"""Typed tables over stdlib sqlite3: the Pydantic row model is the schema.

A ``Table`` binds a row model to a table name. DDL, inserts, and reads all
derive from the model, so the schema cannot drift from the types, and every
row entering or leaving a database is validated. Reads that aggregate or
join declare their result shape with ``Query``: SQL in, validated models out.

Column mapping: ``str``/``int``/``float``/``bytes``/``bool`` become TEXT/INTEGER/
REAL/BLOB/INTEGER NOT NULL, ``X | None`` drops NOT NULL, and ``Literal[...]`` of
strings becomes TEXT with a CHECK constraint. ``Annotated`` metadata may
carry ``Id`` (this column exports ids of a kind) or ``Ref`` (this column
references ids of a kind) for the cross-database coherence walk.
"""

import sqlite3
import types
import typing
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from core.errors import WorkbenchError


class SchemaError(WorkbenchError):
    """A row model cannot be expressed as a table, or a query misuses one."""


@dataclass(frozen=True, slots=True)
class Id:
    """This column exports ids of ``kind`` for other columns to reference."""

    kind: str


@dataclass(frozen=True, slots=True)
class Ref:
    """This column references ids of ``kind`` exported by some Id column."""

    kind: str


# bool needs its own entry even though it subclasses int: the lookup is by
# exact type, and SQLite stores booleans as 0/1 INTEGERs.
_AFFINITY = {
    str: "TEXT",
    int: "INTEGER",
    float: "REAL",
    bytes: "BLOB",
    bool: "INTEGER",
}


def _column_ddl(table: str, name: str, annotation: object) -> str:
    base, nullable = annotation, False
    if typing.get_origin(base) in (types.UnionType, typing.Union):
        arms = typing.get_args(base)
        slim = [a for a in arms if a is not type(None)]
        if len(slim) != 1 or len(arms) != 2:
            raise SchemaError(f"{table}.{name}: only ``X | None`` unions map to SQL")
        base, nullable = slim[0], True

    check = ""
    if typing.get_origin(base) is typing.Literal:
        values = typing.get_args(base)
        if not all(isinstance(v, str) for v in values):
            raise SchemaError(f"{table}.{name}: only string Literals map to SQL")
        quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
        sql_type = "TEXT"
        check = f" CHECK ({name} IN ({quoted}))"
    elif base in _AFFINITY:
        sql_type = _AFFINITY[base]
    else:
        raise SchemaError(f"{table}.{name}: unsupported column type {annotation!r}")

    null = "" if nullable else " NOT NULL"
    return f"{name} {sql_type}{null}{check}"


class Table[M: BaseModel]:
    def __init__(
        self, name: str, model: type[M], *, primary_key: tuple[str, ...] = ()
    ) -> None:
        fields = model.model_fields
        for column in primary_key:
            if column not in fields:
                raise SchemaError(f"{name}: primary key column {column!r} not in model")
        self.name = name
        self.model = model
        self.primary_key = primary_key
        self.columns = tuple(fields)
        self._column_lines = tuple(
            _column_ddl(name, column, fields[column].annotation) for column in fields
        )

    def ddl(self) -> str:
        lines = list(self._column_lines)
        if self.primary_key:
            lines.append(f"PRIMARY KEY ({', '.join(self.primary_key)})")
        body = ",\n    ".join(lines)
        return f"CREATE TABLE {self.name} (\n    {body}\n);"

    def insert(self, connection: sqlite3.Connection, rows: Iterable[M]) -> None:
        values = []
        for row in rows:
            if not isinstance(row, self.model):
                raise SchemaError(
                    f"{self.name} rows must be {self.model.__name__}, "
                    f"got {type(row).__name__}"
                )
            dumped = row.model_dump()
            values.append(tuple(dumped[column] for column in self.columns))
        placeholders = ", ".join("?" for _ in self.columns)
        connection.executemany(
            f"INSERT INTO {self.name} ({', '.join(self.columns)}) "
            f"VALUES ({placeholders})",
            values,
        )

    def select(
        self,
        connection: sqlite3.Connection,
        *,
        where: Mapping[str, object] | None = None,
        order_by: str | None = None,
    ) -> list[M]:
        for column in (*(where or ()), *((order_by,) if order_by else ())):
            if column not in self.columns:
                raise SchemaError(f"{self.name} has no column {column!r}")
        sql = f"SELECT {', '.join(self.columns)} FROM {self.name}"
        params: tuple[object, ...] = ()
        if where:
            sql += " WHERE " + " AND ".join(f"{column}=?" for column in where)
            params = tuple(where.values())
        if order_by:
            sql += f" ORDER BY {order_by}"
        return [
            self.model.model_validate(dict(zip(self.columns, row, strict=True)))
            for row in connection.execute(sql, params)
        ]

    def ids(self) -> dict[str, Id]:
        return self._metadata(Id)

    def refs(self) -> dict[str, Ref]:
        return self._metadata(Ref)

    def _metadata[T: (Id, Ref)](self, marker: type[T]) -> dict[str, T]:
        return {
            column: mark
            for column, field in self.model.model_fields.items()
            for mark in field.metadata
            if isinstance(mark, marker)
        }


class Query[M: BaseModel]:
    """A named read with a declared result shape: SQL in, validated models out."""

    def __init__(self, model: type[M], sql: str) -> None:
        self.model = model
        self.sql = sql

    def run(self, connection: sqlite3.Connection, *params: object) -> list[M]:
        cursor = connection.execute(self.sql, params)
        columns = tuple(d[0] for d in cursor.description)
        return [
            self.model.model_validate(dict(zip(columns, row, strict=True)))
            for row in cursor
        ]


def create_db(path: Path, tables: Sequence[Table]) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    for table in tables:
        connection.execute(table.ddl())
    return connection


def connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def connect_readwrite(path: Path) -> sqlite3.Connection:
    """Open an existing database for reads and writes.

    The read-only surface is the default and the norm; this is the narrow
    aperture for tools that mutate world state (an agent completing a workflow),
    graded on the resulting state. ``mode=rw`` requires the file to exist, so a
    tool cannot silently conjure a fresh database by mistyping a path.
    """
    connection = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
    connection.row_factory = sqlite3.Row
    return connection
