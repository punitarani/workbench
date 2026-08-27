"""A sixth cause of 0.000, and it is not a fact about the model.

`band` already keeps a did-not-finish out of the average. It knew five
reasons a trial can score zero without having been measured: a wrong
answer, a harness incompatibility, a rate limit, a clock, an abandoned
delegation. This is the sixth -- the provider returned text that is not
language:

    .I meetings. . -  |. meeting  .  |   -6.. Meeting  0:Let  It If

A glm trial ended after five steps that way, a decoding fault on a
quantized endpoint, and it would have been read as a model that cannot
read a transcript. It answers the same task at 0.5.

Asked BEFORE the deliverable check, for two reasons: a provider that
served gibberish explains a missing file rather than being explained by
it, and a garbage run that *did* write something would otherwise be
averaged in as a real answer.

Measured over every glm trial in this tree before shipping: 1 of 30 trips
this test, and it is the one that produced the line above. A test that
flagged more would be catching terse answers rather than broken ones.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


GARBAGE = ".I meetings. . -  |. meeting  .  |   -6.. Meeting  0:Let  It If        ..   -. 1. +  .   .   .    ."
REAL = (
    "I'll start by listing all meetings in the window, then identify which "
    "are standing meetings and read their transcripts."
)


def _trial(tmp_path: Path, message: str, *, source: str = "agent",
           deliverable: bool = False) -> Path:
    trial = tmp_path / "t"
    (trial / "agent").mkdir(parents=True)
    (trial / "verifier").mkdir(parents=True)
    (trial / "agent" / "trajectory.json").write_text(
        json.dumps({"steps": [{"source": source, "message": message}]})
    )
    if deliverable:
        (trial / "verifier" / "submitted-answer.json").write_text("{}")
        (trial / "verifier" / "reward.json").write_text(json.dumps({"reward": 0.0}))
    return trial


def test_gibberish_is_not_a_score(tmp_path):
    band = _load("band")
    assert band._served_garbage(_trial(tmp_path, GARBAGE)) is True


def test_a_real_answer_is_not_flagged(tmp_path):
    band = _load("band")
    assert band._served_garbage(_trial(tmp_path, REAL)) is False


def test_tool_output_is_not_the_agents_voice(tmp_path):
    """Tool results are tables and punctuation and would trip any such rule."""

    band = _load("band")
    assert band._served_garbage(_trial(tmp_path, GARBAGE, source="tool")) is False


def test_a_garbage_run_that_wrote_a_file_is_still_not_a_score(tmp_path):
    """The case the ordering exists for: gibberish that still produced JSON."""

    band = _load("band")
    trial = _trial(tmp_path, GARBAGE, deliverable=True)
    assert band._outcome(trial, "answer.json") == (None, "provider served garbage")


def test_a_short_agent_turn_is_never_garbage(tmp_path):
    """"ok" and "done" are terse, not broken."""

    band = _load("band")
    assert band._served_garbage(_trial(tmp_path, "ok, done.")) is False
