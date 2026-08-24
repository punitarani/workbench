"""A table nothing ever writes is a surface that is permanently blank.

`meeting.transcript` was a recorded event kind that no tool system read:
723 transcripts reachable by nobody. This is the same shape one level down
— a table a system *declares*, that its projection and its tools both never
write, so every query against it returns the empty set forever and no
integrity check can tell that from a genuinely empty corpus.

Nothing catches it on its own, because every existing check looks at one
side. The table exists and is created, so no query errors. The server's
read is correct — it faithfully reports nothing. Coherence asks whether
references resolve, and a table with no rows has none to dangle. The
projection tests assert the databases match the registry, which they do:
the file is there and one of its tables is empty.

**Two writers count, and conflating them would make this a false gate.**
Ten of this registry's tables are written only by the agent-facing tools —
`drafts`, `sent_messages`, `added_reactions`, `imanage.actions` — and are
empty in a fresh projection *by design*, because they record what the agent
does rather than what the firm did. A check demanding the projection fill
those would report ten defects that are not defects, which is the failure
this suite has spent a long time removing from its own gates. So a table
passes if either the projection or the server writes it, and fails only
when neither has ever heard of it.

**A gap this does not catch, recorded here because it was found by writing
it.** `event_recurrence` passes: `create_event` writes it. But the
projection never does, so although the workplace spec declares the firm's
eight standing meetings `daily` or `weekly`, and `compile.py` generates
them from exactly that, the recorded calendar serves `recurrence: []` on
every event. The world knows these meetings recur, generates them because
they recur, and then serves a calendar on which nothing does. An agent
asked which meetings are standing has to infer it from repetition. That is
a fidelity gap rather than a dead table, and it belongs to the calendar
projection, not here.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tools import REGISTRY

_SRC = Path(__file__).resolve().parents[2] / "src" / "tools"


def _names_used(system_name: str, module: str) -> set[str]:
    """Every bare name mentioned anywhere in one of a system's modules."""

    path = _SRC / system_name / f"{module}.py"
    tree = ast.parse(path.read_text())
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }


def _table_constant_names(system_name: str) -> dict[str, str]:
    """Map a system's `Table` constant names to the SQL table they define."""

    tree = ast.parse((_SRC / system_name / "tables.py").read_text())
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if getattr(call.func, "id", None) != "Table" or not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = first.value
    return found


def test_every_declared_table_is_written_by_its_projection() -> None:
    """A table the recording cannot fill is a surface that is always empty.

    Deliberately static, and deliberately generous: it asks only whether the
    projection module *mentions* the table constant at all. A projection
    that names a table and writes it conditionally still passes; one that
    has never heard of it cannot. That is the whole failure — nobody forgot
    a branch, the write was never written.
    """

    orphans: list[str] = []
    for system in REGISTRY:
        constants = _table_constant_names(system.name)
        used = _names_used(system.name, "project") | _names_used(system.name, "server")
        by_sql_name = {sql: const for const, sql in constants.items()}
        for table in system.tables:
            constant = by_sql_name.get(table.name)
            if constant is None:
                continue  # defined elsewhere; the shared people table
            if constant not in used:
                orphans.append(f"{system.name}.{table.name} ({constant})")

    assert not orphans, (
        f"these tables are declared by a tool system and never written by its "
        f"projection, so the recorded world serves them empty forever: "
        f"{orphans}. Either project the data or drop the table — a schema the "
        "corpus cannot fill reads as a supported surface and is a blank."
    )


def test_the_check_can_see_the_tables() -> None:
    """Guard the guard.

    The assertion above is a loop over parsed constants, and a parse that
    silently finds nothing makes it vacuous — which is exactly the failure
    mode this file exists to catch, one level up.
    """

    assert len(REGISTRY) > 3
    total = sum(len(_table_constant_names(system.name)) for system in REGISTRY)
    assert total > 10, total
    assert "CALENDAR_EVENTS" in _table_constant_names("calendar")
    assert "CALENDAR_EVENTS" in _names_used("calendar", "project")
