"""The job the sweep writes must be the job the aggregator reads.

These two scripts meet only through a string: `<dataset>-<task>-<tag>`,
written by the rollout runner as a directory name and looked up by the
aggregator as a glob. When they disagree, nothing errors. The sweep runs,
the trials complete, the scores land on disk — and the report says "not
run", which is indistinguishable from never having measured at all.

That is a whole sweep's cost and an hour of confusion, so the tag
vocabulary lives in one table and this asserts both sides read it.
"""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


band = _load("band")
rollout = _load("rollout")


def test_every_measured_model_can_be_rolled_out() -> None:
    """A model the aggregator reports on but the runner cannot launch is a
    column that will always read '--'."""

    assert set(band.MODELS) <= set(rollout.MODELS), (
        f"aggregator reports on {sorted(set(band.MODELS) - set(rollout.MODELS))} "
        "which the rollout runner cannot launch"
    )


def test_every_model_has_a_tag_prefix_and_a_tier_entry() -> None:
    for model in band.MODELS:
        assert model in band.TAG_PREFIX, f"{model} has no tag prefix"
        assert model in rollout.TIERS, f"{model} has no driving agent"


def test_codex_gets_the_bare_alias_and_hermes_the_qualified_id() -> None:
    """The wire name differs by agent, and the wrong one returns
    "unsupported model" on the container's first turn — a non-zero exit
    and a 0.000 that is not a score.

    Codex strips a slashed id to its last segment before the request
    leaves the container, so `anthropic/claude-opus-5` arrives as
    `claude-opus-5`, which the gateway's alias table does not carry.
    """

    for alias, (agent, wire) in rollout.TIERS.items():
        if agent == rollout.CODEX:
            assert "/" not in wire, (
                f"{alias} is driven by codex, which strips everything before "
                f"the slash — {wire!r} would arrive as {wire.split('/')[-1]!r} "
                "and resolve to 'unsupported model'"
            )
            assert wire == alias, f"{alias} must go on the wire as its own alias"
        else:
            assert "/" in wire, (
                f"{alias} is driven by hermes, which does not rewrite the id, "
                "so it needs the provider-qualified form"
            )


def test_the_default_tag_is_one_the_aggregator_searches() -> None:
    """The specific silent failure: a job named `<model>-k9` when the
    aggregator looks for `<prefix>-k9`.

    Reads the aggregator's OWN table. This test used to keep a copy of it
    inline, which cannot fail for the right reason: a copy goes stale the
    moment a tier is added, and it did -- adding `kimi-k3` raised KeyError
    here while the aggregator itself was correct. A test that reimplements
    what it checks is checking its own arithmetic.
    """

    for model in band.MODELS:
        assert model in band.DEFAULT_TAGS, (
            f"{model} is in MODELS but has no default tag, so a sweep of it "
            "reports 'not run' however many trials are on disk"
        )
        written = f"{band.TAG_PREFIX[model]}-k9"
        searched = band.DEFAULT_TAGS[model]
        # A k=9 sweep writes `<prefix>-k9` unless `--tag` overrides it, so
        # that name has to be one the aggregator looks under. `opus-5` is
        # exempt only because its historical evidence lives under a tag
        # that predates the convention.
        if model == "opus-5":
            continue
        assert written in searched, (
            f"a k=9 sweep of {model} writes '{written}', which the "
            f"aggregator does not search: {searched}"
        )


def test_every_default_tag_names_a_model_the_runner_can_drive() -> None:
    """The other direction: a tag table naming a tier nothing can run."""

    import rollout

    for model in band.DEFAULT_TAGS:
        assert model in rollout.TIERS, (
            f"the aggregator searches for {model} scores, but the runner "
            "cannot produce them"
        )


def test_every_model_gets_a_column() -> None:
    """The report's row is derived from MODELS, not written out by hand.

    It used to name `cells[0]`, `cells[1]`, `cells[2]` -- three, when
    MODELS had grown to four. The fourth column was never printed and
    everything after it shifted left, so a model whose mean the aggregator
    had in hand read as `--` and the mean column read as the fourth
    model's score. The header was derived and the row was not, which is
    the only reason they could disagree.
    """

    import inspect

    # Comments stripped: the comment explaining this failure names the very
    # index it warns about, and a check that reads prose fails on its own
    # explanation.
    source = "\n".join(
        line.split("#", 1)[0] for line in inspect.getsource(band.main).splitlines()
    )
    assert "cells[0]" not in source, (
        "the row indexes cells by position again; it will silently drop "
        "every model past the last index the day MODELS grows"
    )
    # Header and row must share one width, or the columns drift apart
    # without either being wrong on its own.
    assert source.count("{_COLUMN}s") >= 2, "header and row no longer share _COLUMN"
