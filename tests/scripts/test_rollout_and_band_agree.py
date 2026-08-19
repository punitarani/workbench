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
    aggregator looks for `<prefix>-k9`."""

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--tag-gpt", action="append", default=None)
    parser.add_argument("--tag-opus", action="append", default=None)
    parser.add_argument("--tag-glm", action="append", default=None)
    args = parser.parse_args([])
    searched = {
        "gpt-5.6-sol": args.tag_gpt or ["gpt-k9", "gpt-k3"],
        "opus-5": args.tag_opus or ["fair-k3"],
        "glm-5.2": args.tag_glm or ["glm-k9", "glm-fair"],
    }
    for model in band.MODELS:
        written = f"{band.TAG_PREFIX[model]}-k9"
        # opus is searched under a historical tag; the others must line up
        # with what a fresh k=9 sweep writes.
        if model == "opus-5":
            continue
        assert written in searched[model], (
            f"a k=9 sweep of {model} writes '{written}', which the "
            f"aggregator does not search: {searched[model]}"
        )


def test_a_missing_task_fails_loudly_rather_than_writing_a_job() -> None:
    import pytest

    with pytest.raises(SystemExit):
        rollout.job_config("merrick", "no-such-task", "opus-5", "t", 9, 50341, 3)
