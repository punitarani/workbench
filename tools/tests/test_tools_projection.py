"""Registry-level projection invariants over the product systems."""

import sqlite3
from pathlib import Path

from projection_fixtures import coherent_events

from workbench.tools import REGISTRY, check_coherence, project_all

DBS = ["clio.db", "gmail.db", "imanage.db", "slack.db"]


def project_fixture(tmp_path: Path) -> Path:
    out = tmp_path / "state"
    project_all(coherent_events(), out)
    return out


def test_all_four_systems_project(tmp_path: Path) -> None:
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
