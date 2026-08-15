"""The fidelity harness: band semantics, rendering, and a live measurement."""

import json
import sqlite3
from pathlib import Path

import pytest

from workbench.analysis.fidelity import (
    BANDS_PATH,
    Band,
    Result,
    evaluate,
    load_bands,
    measure,
    render_markdown,
    summarize,
)

REPO = Path(__file__).resolve().parents[2]
V1_STATE = REPO / "out/calder/epoch-6mo/bundle/state"


class TestBands:
    def test_committed_bands_load_and_are_bounded(self) -> None:
        bands = load_bands(REPO / BANDS_PATH)
        assert len(bands) > 80
        for metric, band in bands.items():
            assert band.min is not None or band.max is not None, (
                f"{metric} states no bound, so nothing can fail it"
            )
            if band.min is not None and band.max is not None:
                assert band.min < band.max, f"{metric} has an inverted band"
            assert band.surface, f"{metric} has no surface"

    def test_band_ids_are_namespaced_by_surface(self) -> None:
        bands = load_bands(REPO / BANDS_PATH)
        for metric, band in bands.items():
            assert metric.split(".")[0] == band.surface

    def test_verdicts(self) -> None:
        band = Band(label="x", surface="s", min=1.0, max=2.0)
        assert band.verdict(1.5) == "PASS"
        assert band.verdict(0.9) == "FAIL"
        assert band.verdict(2.1) == "FAIL"
        assert band.verdict(None) == "ABSENT"
        assert band.verdict(1.0) == "PASS", "bounds are inclusive"
        assert band.verdict(2.0) == "PASS"

    def test_one_sided_bands(self) -> None:
        floor = Band(label="x", surface="s", min=5)
        ceiling = Band(label="x", surface="s", max=5)
        assert floor.verdict(99) == "PASS"
        assert floor.verdict(1) == "FAIL"
        assert ceiling.verdict(1) == "PASS"
        assert ceiling.verdict(99) == "FAIL"
        assert floor.rendered() == "≥ 5"
        assert ceiling.rendered() == "≤ 5"


class TestReport:
    def test_render_counts_and_groups(self) -> None:
        results = [
            Result("a.one", Band(label="One", surface="a", min=1), 5.0, "PASS"),
            Result("a.two", Band(label="Two", surface="a", max=1), 5.0, "FAIL"),
            Result("b.three", Band(label="Three", surface="b", min=1), None, "ABSENT"),
        ]
        report = render_markdown(results, title="T", context="C")
        assert "1 pass · 1 fail · 1 absent" in report
        assert "## a" in report and "## b" in report
        assert "❌ FAIL" in report and "⚪ ABSENT" in report
        assert summarize(results)["PASS"] == 1

    def test_absent_metrics_render_a_dash_not_a_zero(self) -> None:
        results = [
            Result("b.three", Band(label="Three", surface="b", min=1), None, "ABSENT")
        ]
        line = [
            row
            for row in render_markdown(results, title="T", context="").splitlines()
            if "Three" in row
        ][0]
        assert "| — |" in line


class TestMeasurement:
    def test_empty_state_measures_nothing_rather_than_crashing(
        self, tmp_path: Path
    ) -> None:
        assert measure(tmp_path) == {}

    def test_measures_a_synthetic_world(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        connection = sqlite3.connect(state / "gmail.db")
        connection.executescript(
            """
            CREATE TABLE meta (key TEXT, value TEXT);
            CREATE TABLE people (person_id TEXT, name TEXT, email_address TEXT,
                title TEXT, department TEXT, affiliation TEXT);
            CREATE TABLE messages (message_id TEXT, thread_id TEXT,
                in_reply_to TEXT, sender TEXT, subject TEXT, body TEXT,
                time INTEGER, snippet TEXT);
            CREATE TABLE recipients (message_id TEXT, person_id TEXT, kind TEXT);
            CREATE TABLE attachments (message_id TEXT, filename TEXT,
                media_type TEXT, document_id TEXT);
            INSERT INTO meta VALUES ('epoch', '2026-01-05T00:00:00-08:00');
            INSERT INTO people VALUES ('p1','A','a@x','T','D','internal');
            INSERT INTO people VALUES ('p2','B','b@x','T','D','internal');
            INSERT INTO people VALUES ('c1','C','c@y','T','D','external');
            INSERT INTO messages VALUES ('m1','t1',NULL,'p1','s','one two',100,'s');
            INSERT INTO messages VALUES ('m2','t1','m1','p2','s','three',3700,'s');
            INSERT INTO messages VALUES ('m3','t2',NULL,'p1','s','four',90000,'s');
            INSERT INTO recipients VALUES ('m1','p2','to');
            INSERT INTO recipients VALUES ('m2','p1','to');
            INSERT INTO recipients VALUES ('m3','c1','to');
            INSERT INTO attachments VALUES ('m3','a.pdf','application/pdf','doc-1');
            """
        )
        connection.commit()
        connection.close()

        measurements = measure(state)
        # Two internal-only messages of three; the external one carries the
        # only attachment.
        assert measurements["email.internal_share"] == pytest.approx(2 / 3)
        assert measurements["email.attachment_rate_external"] == pytest.approx(1.0)
        assert measurements["email.attachment_rate_internal"] == pytest.approx(0.0)
        assert measurements["email.single_recipient_share"] == pytest.approx(1.0)
        assert measurements["email.thread_depth_max"] == pytest.approx(2.0)
        # m2 replies to m1 one hour later.
        assert measurements["email.reply_latency_median_hours"] == pytest.approx(1.0)

    @pytest.mark.skipif(
        not V1_STATE.exists(), reason="v1 epoch bundle not built locally"
    )
    def test_v1_bundle_produces_a_full_report(self) -> None:
        bands = load_bands(REPO / BANDS_PATH)
        results = evaluate(measure(V1_STATE), bands)
        counts = summarize(results)
        assert len(results) == len(bands)
        # The floor v2 is moving: v1 cannot pass the economics bands.
        assert counts["FAIL"] > 0
        by_metric = {result.metric: result for result in results}
        assert by_metric["billing.total_hours_h1"].verdict == "FAIL"
        assert by_metric["email.distinct_body_share"].verdict == "PASS"


def test_bands_file_is_valid_json_with_a_note() -> None:
    raw = json.loads((REPO / BANDS_PATH).read_text())
    assert raw["version"] >= 1
    assert "scale factor" in raw["note"].lower()
    assert raw["alpha"] == 0.01
