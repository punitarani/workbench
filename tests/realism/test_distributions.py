"""Statistical assertions against a generated world.

These are not fixture tests. They run the committed bands (§4 of the v2
plan) against a real generated world and fail when its *shape* is wrong —
flat where nature is skewed, too concentrated, missing a tail, or
uncorrelated across surfaces that should move together.

Failures print the observed value, the band, and where the outlier is,
because "assert False" against a distribution teaches nobody anything.

By default these run against whichever world is present: the v2 mini
epoch when it exists, else the v1 epoch (which fails most bands — that
is the documented baseline, so the suite is marked xfail there rather
than pretending v1 passes).
"""

from collections import Counter
from pathlib import Path

import pytest

from analysis import stats
from analysis.fidelity import (
    BANDS_PATH,
    evaluate,
    load_bands,
    measure,
)

REPO = Path(__file__).resolve().parents[2]
V2_MINI = REPO / "out/calder/mini-v2/bundle/state"
V1_EPOCH = REPO / "out/calder/epoch-6mo/bundle/state"
V1_LOG = REPO / "out/calder/epoch-6mo/world.jsonl"


def _world() -> tuple[Path, Path | None, bool]:
    """(state dir, log, is_v2). v2 first; v1 is the acknowledged baseline."""

    if V2_MINI.exists():
        return V2_MINI, V2_MINI.parent.parent / "world.jsonl", True
    if V1_EPOCH.exists():
        return V1_EPOCH, V1_LOG, False
    pytest.skip("no generated world available; run an epoch first")


@pytest.fixture(scope="module")
def world():
    state, log, is_v2 = _world()
    return measure(state, log), is_v2


def _diagnose(metric: str, observed, band) -> str:
    return (
        f"\n  metric:   {metric}"
        f"\n  observed: {observed}"
        f"\n  band:     {band.rendered()}"
        f"\n  v1 was:   {band.v1}"
    )


class TestBands:
    """Every committed band, as its own assertion with a diagnostic."""

    def test_all_bands(self, world) -> None:
        measurements, is_v2 = world
        results = evaluate(measurements, load_bands(REPO / BANDS_PATH))
        failures = [r for r in results if r.verdict == "FAIL"]
        absent = [r for r in results if r.verdict == "ABSENT"]
        report = "\n".join(
            _diagnose(r.metric, r.observed, r.band) for r in failures[:15]
        )
        if not is_v2:
            pytest.xfail(
                f"v1 baseline: {len(failures)} bands fail, {len(absent)} absent "
                f"(the documented floor v2 moves)"
            )
        assert not failures, f"{len(failures)} bands out of range:{report}"


class TestAntiUniformity:
    """A metric that comes back flat fails even when its mean is right.

    This is the statistician's test: machine filler is uniform, human
    behaviour is not.
    """

    def test_reply_latency_is_not_flat(self, world) -> None:
        measurements, is_v2 = world
        uniform_p = measurements.get("email.reply_latency_uniform_p")
        if uniform_p is None:
            pytest.skip("no reply latencies in this world")
        if not is_v2:
            pytest.xfail("v1 latency is a 300s quantization artifact")
        assert uniform_p < 0.01, (
            f"reply latency cannot reject uniform (p={uniform_p:.4f}) — "
            "it is machine-shaped, not human-shaped"
        )

    def test_time_entry_durations_are_not_flat(self, world) -> None:
        measurements, is_v2 = world
        uniform_p = measurements.get("billing.duration_uniform_p")
        if uniform_p is None:
            pytest.skip("no time entries in this world")
        if not is_v2:
            pytest.xfail("v1 logs too little time to have a shape")
        assert uniform_p < 0.01, f"entry durations are flat (p={uniform_p:.4f})"

    def test_round_numbers_do_not_dominate(self, world) -> None:
        measurements, is_v2 = world
        share = measurements.get("billing.round_number_share")
        if share is None:
            pytest.skip("no time entries in this world")
        if not is_v2:
            pytest.xfail(f"v1 round-number share is {share:.2f}")
        assert share <= 0.55, (
            f"{share:.0%} of entries land on whole or half hours — people "
            "log 0.4 and 1.3, generators log 0.5 and 1.5"
        )


class TestConcentration:
    """Both extremes fail: everyone identical, and one entity owning all."""

    @pytest.mark.parametrize(
        ("metric", "low", "high"),
        [
            ("email.gini_by_person", 0.30, 0.55),
            ("slack.gini_by_channel", 0.35, 0.65),
            ("billing.hours_gini_by_matter", 0.45, 0.70),
        ],
    )
    def test_gini_sits_inside_its_band(
        self, world, metric: str, low: float, high: float
    ) -> None:
        measurements, is_v2 = world
        value = measurements.get(metric)
        if value is None:
            pytest.skip(f"{metric} is not measurable in this world")
        if not is_v2 and not low <= value <= high:
            pytest.xfail(f"v1 {metric} = {value:.2f}")
        assert low <= value <= high, (
            f"{metric} = {value:.3f}, outside {low}–{high}: "
            f"{'too even to be real' if value < low else 'one entity owns the surface'}"
        )

    def test_no_single_entity_dominates_a_surface(self, world) -> None:
        measurements, is_v2 = world
        caps = {
            "email.top1_share_by_person": 0.45,
            "slack.top_channel_share": 0.45,
            "cross.matter_note_top1_share": 0.45,
        }
        over = {
            metric: measurements[metric]
            for metric, cap in caps.items()
            if measurements.get(metric) is not None and measurements[metric] > cap
        }
        if over and not is_v2:
            pytest.xfail(f"v1 concentration: {over}")
        assert not over, f"one entity holds too much of a surface: {over}"


class TestCrossSurfaceCoupling:
    """Uncorrelated surfaces are the giveaway that each was generated alone."""

    @pytest.mark.parametrize(
        "metric", ["cross.person_volume_spearman", "cross.matter_volume_spearman"]
    )
    def test_volumes_move_together(self, world, metric: str) -> None:
        measurements, is_v2 = world
        value = measurements.get(metric)
        if value is None:
            pytest.skip(f"{metric} needs more than one surface")
        if not is_v2 and value < 0.45:
            pytest.xfail(f"v1 {metric} = {value:.2f}")
        assert value >= 0.45, (
            f"{metric} = {value:.2f}: a busy engagement should be busy "
            "everywhere — mail, chat, time, documents — and this world's "
            "surfaces do not move together"
        )


class TestPersonaVariance:
    def test_personas_do_not_all_write_the_same_length(self, world) -> None:
        measurements, is_v2 = world
        ratio = measurements.get("cross.persona_body_length_ratio")
        if ratio is None:
            pytest.skip("not enough mail per persona")
        if not is_v2 and ratio < 2.0:
            pytest.xfail(f"v1 verbosity spread = {ratio:.2f}")
        assert ratio >= 2.0, (
            f"the most and least verbose personas differ by only {ratio:.2f}x — "
            "style is supposed to be a measurable per-persona parameter"
        )


class TestSuiteIntegrity:
    """The suite has to be able to fail, or it is decoration."""

    def test_a_flat_sample_fails_the_uniformity_check(self) -> None:
        flat = [float(index) for index in range(200)]
        _, p = stats.ks_uniform(flat)
        assert p > 0.01, "an even ramp must not reject uniform"

    def test_a_skewed_sample_passes_it(self) -> None:
        skewed = [1.05**index for index in range(200)]
        _, p = stats.ks_uniform(skewed)
        assert p < 0.01, "an exponential ramp must reject uniform"

    def test_concentration_extremes_are_both_caught(self) -> None:
        assert stats.gini([5] * 10) < 0.30
        assert stats.gini([0] * 9 + [100]) > 0.70

    def test_counter_shapes_are_measurable(self) -> None:
        counts = Counter({"a": 50, "b": 30, "c": 20})
        assert 0 < stats.gini(list(counts.values())) < 1
        assert stats.top_share(list(counts.values())) == pytest.approx(0.5)
