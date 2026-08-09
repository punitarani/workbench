"""Cross-database coherence: every reference in any projected database must
resolve. Coherence is inherited from the single world log; this check proves
the projections preserved it."""

import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class CoherenceFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    database: str
    detail: str


def _missing(connection: sqlite3.Connection, sql: str, known: set[str]) -> set[str]:
    return {
        row[0]
        for row in connection.execute(sql)
        if row[0] is not None and row[0] not in known
    }


def check_coherence(state_dir: Path) -> tuple[CoherenceFinding, ...]:
    findings: list[CoherenceFinding] = []

    def flag(database: str, detail: str) -> None:
        findings.append(CoherenceFinding(database=database, detail=detail))

    connections = {
        name: sqlite3.connect(state_dir / f"{name}.db")
        for name in ("mail", "chat", "dms", "matters")
    }
    try:
        people: set[str] = set()
        for name, connection in connections.items():
            people |= {r[0] for r in connection.execute("SELECT person_id FROM people")}

        documents = {
            r[0]
            for r in connections["dms"].execute("SELECT document_id FROM documents")
        }

        mail = connections["mail"]
        for ref in _missing(mail, "SELECT sender FROM messages", people):
            flag("mail", f"unknown sender {ref}")
        for ref in _missing(mail, "SELECT person_id FROM recipients", people):
            flag("mail", f"unknown recipient {ref}")
        message_ids = {r[0] for r in mail.execute("SELECT message_id FROM messages")}
        for ref in _missing(mail, "SELECT in_reply_to FROM messages", message_ids):
            flag("mail", f"reply to unknown message {ref}")
        for ref in _missing(mail, "SELECT document_id FROM attachments", documents):
            flag("mail", f"attachment references unknown document {ref}")

        chat = connections["chat"]
        conversation_ids = {
            r[0] for r in chat.execute("SELECT conversation_id FROM conversations")
        }
        for ref in _missing(chat, "SELECT person_id FROM members", people):
            flag("chat", f"unknown member {ref}")
        for ref in _missing(chat, "SELECT sender FROM messages", people):
            flag("chat", f"unknown sender {ref}")
        for ref in _missing(
            chat, "SELECT conversation_id FROM messages", conversation_ids
        ):
            flag("chat", f"message in unknown conversation {ref}")

        dms = connections["dms"]
        for ref in _missing(dms, "SELECT author FROM revisions", people):
            flag("dms", f"unknown author {ref}")
        for ref in _missing(dms, "SELECT document_id FROM revisions", documents):
            flag("dms", f"revision of unknown document {ref}")

        matters = connections["matters"]
        ticket_ids = {r[0] for r in matters.execute("SELECT ticket_id FROM tickets")}
        for column in ("requester", "assignee"):
            for ref in _missing(matters, f"SELECT {column} FROM tickets", people):
                flag("matters", f"unknown {column} {ref}")
        for table in ("history", "comments"):
            for ref in _missing(matters, f"SELECT ticket_id FROM {table}", ticket_ids):
                flag("matters", f"{table} row for unknown ticket {ref}")
            for ref in _missing(matters, f"SELECT actor FROM {table}", people):
                flag("matters", f"unknown actor {ref} in {table}")
    finally:
        for connection in connections.values():
            connection.close()

    return tuple(findings)
