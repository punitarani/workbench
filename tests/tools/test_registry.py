"""The plugin contract: one registry line per system drives everything else."""

import pytest
from pydantic import BaseModel

from workbench.core.errors import WorkbenchError
from workbench.tools import REGISTRY, build_server, get_system, server_specs
from workbench.tools.db import Table
from workbench.tools.framework import ToolContractError, ToolSystem


class NoteRow(BaseModel):
    note_id: str


NOTES = Table("notes", NoteRow)


def _noop_project(events, connection) -> None:
    pass


def _noop_register(server, db_path) -> None:
    pass


def system(**overrides) -> ToolSystem:
    base = dict(
        name="notes",
        handled_tags=("note.created", "person.record"),
        tables=(NOTES,),
        project=_noop_project,
        register=_noop_register,
    )
    return ToolSystem(**{**base, **overrides})


def test_registry_systems_are_well_formed() -> None:
    names = [s.name for s in REGISTRY]
    assert len(set(names)) == len(names)
    for s in REGISTRY:
        assert s.handled_tags
        assert s.tables
        assert "person.record" in s.handled_tags


def test_offstage_tags_cannot_be_declared() -> None:
    with pytest.raises(ToolContractError, match="sim"):
        system(handled_tags=("sim.wake", "person.record"))


def test_person_record_must_be_declared() -> None:
    with pytest.raises(ToolContractError, match="person.record"):
        system(handled_tags=("note.created",))


def test_tables_are_required_and_must_not_shadow_people() -> None:
    with pytest.raises(ToolContractError):
        system(tables=())
    with pytest.raises(ToolContractError, match="people"):
        system(tables=(Table("people", NoteRow),))


def test_server_specs_cover_the_registry() -> None:
    specs = server_specs()
    assert set(specs) == {s.name for s in REGISTRY}
    for name, spec in specs.items():
        assert spec["command"] == "python3"
        assert spec["args"][:2] == ["-m", "workbench.tools.serve"]
        assert spec["args"][-2:] == ["--db", f"state/{name}.db"]


def test_unknown_system_errors() -> None:
    with pytest.raises(WorkbenchError, match="rolodex"):
        get_system("rolodex")
    with pytest.raises(WorkbenchError, match="rolodex"):
        build_server("rolodex", db_path=None)
