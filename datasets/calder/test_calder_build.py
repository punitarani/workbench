"""Pilot-scale gates for the Calder build driver: a short build
validates, materializes, and reproduces byte for byte."""

import importlib.util
from pathlib import Path

from core.seed import Seed
from core.worldlog import read_events, validate_events
from environment import materialize

_SPEC = importlib.util.spec_from_file_location(
    "calder_build_history", Path(__file__).parent / "build_history.py"
)
build_history = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_history)


def test_pilot_build_validates_and_materializes(tmp_path: Path) -> None:
    log_path = build_history.build_world(tmp_path, Seed(root=42), day_count=8)
    events = read_events(log_path)
    report = validate_events(events)
    assert report.ok, report.findings[:5]
    assert len(events) > 500, "eight January days carry close-cycle traffic"

    bundle = materialize(log_path, tmp_path / "bundle")
    assert bundle.event_count == len(events)
    assert bundle.document_files >= 8, "seed documents materialized"


def test_pilot_build_is_deterministic(tmp_path: Path) -> None:
    first = build_history.build_world(
        tmp_path / "one", Seed(root=42), day_count=6
    ).read_bytes()
    second = build_history.build_world(
        tmp_path / "two", Seed(root=42), day_count=6
    ).read_bytes()
    assert first == second


def test_different_seed_diverges(tmp_path: Path) -> None:
    first = build_history.build_world(
        tmp_path / "one", Seed(root=42), day_count=3
    ).read_bytes()
    second = build_history.build_world(
        tmp_path / "two", Seed(root=43), day_count=3
    ).read_bytes()
    assert first != second
