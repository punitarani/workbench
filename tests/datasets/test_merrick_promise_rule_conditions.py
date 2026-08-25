"""Conditions the brief promises, held to actually deciding something.

A rule condition can be present, correctly spelled, covered by passing
tests, and decide nothing. `_NEG` listed `n't` for months written
`\\bn't\\b`, which cannot match a contraction -- there is no word boundary
between `s` and `n` in "doesn't" -- and every one of its five alternatives
was then redundant with `_RULED_OUT`. The whole negation condition was
decorative while the brief stated it as a rule, and it cost four rows
whose dates the speaker was ruling OUT.

These tests are behavioural rather than structural: they name sentences
from the corpus and assert what the rule must say about them. A structural
test ("the pattern contains n't") passed the entire time.
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _rule():
    path = REPO / "datasets" / "merrick" / "promise_rule.py"
    spec = importlib.util.spec_from_file_location("_merrick_promise_rule", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Every one of these is a real turn or mail body from the recorded firm.
REFUSED = (
    "Good flag, Petra — yes, please get me the memo beforehand, and I'll make "
    "sure Clement doesn't see it or hear its substance on Thursday.",
    "I'll chase Roland again if I haven't heard by Friday.",
    "The enviro severity number is Saoirse's to give us, not mine, so I'll "
    "defer to Quentin on that piece, but from a documents standpoint 10.3 "
    "shouldn't be holding up Wednesday.",
)

ADMITTED = (
    # A comma ends a negation's reach, so this one keeps its deadline.
    ("I'll have a real number, not a guess, by end of day", "eod"),
    # A time of day may trail the day and it still ends the clause.
    ("I'll check with Noor first thing tomorrow morning", "tomorrow"),
    # `or` joining two things to be delivered leaves the deadline alone.
    ("I'll have my sign-off or a specific open item by Thursday", "thursday"),
)

UNPICKED = (
    "I'll get them to you today or tomorrow",
    "I'll get the joint call with Harriet locked for Wednesday or Thursday afternoon",
    "I'll hold the tracker update until then or first thing tomorrow",
)


@pytest.mark.parametrize("text", REFUSED)
def test_a_contracted_negation_refuses_the_day(text: str) -> None:
    assert _rule().commitment_in(text) is None


@pytest.mark.parametrize(("text", "token"), ADMITTED)
def test_the_rule_still_admits_what_it_should(text: str, token: str) -> None:
    assert _rule().commitment_in(text) == token


@pytest.mark.parametrize("text", UNPICKED)
def test_a_day_the_speaker_never_picked_makes_no_row(text: str) -> None:
    assert _rule().commitment_in(text) is None


def test_the_negation_condition_decides_something() -> None:
    """The condition must be load-bearing, not merely present.

    This is the test that would have caught the original defect. Remove
    the contracted form from `_NEG` and the rule's verdict on the corpus
    has to move; if it does not, the brief is promising a rule that
    changes no answer.
    """

    import re
    import sqlite3

    module = _rule()
    texts: list[str] = []
    for task, database, query in (
        ("live-commitment-register", "meetings.db", "SELECT text FROM utterances"),
        ("mail-promise-register", "gmail.db", "SELECT body FROM messages"),
    ):
        state = (
            REPO
            / "datasets"
            / "merrick"
            / "tasks"
            / task
            / "environment"
            / ".workbench"
            / "state"
            / database
        )
        if not state.is_file():
            pytest.skip(f"{task} is not staged")
        connection = sqlite3.connect(f"file:{state}?mode=ro", uri=True)
        texts += [row[0] or "" for row in connection.execute(query)]

    before = [module.commitment_in(text) for text in texts]
    module._NEG = re.compile(
        r"(?:\bnot\b|\bnever\b|\brather than\b|\binstead of\b)", re.IGNORECASE
    )
    after = [module.commitment_in(text) for text in texts]
    moved = sum(1 for a, b in zip(before, after, strict=True) if a != b)
    assert moved > 0, (
        "dropping the contracted negation changes no verdict anywhere in the "
        "corpus, so the condition the brief states is deciding nothing"
    )
