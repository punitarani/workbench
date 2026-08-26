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


# ---------------------------------------------------------------------------
# Order.
#
# Twelve conditions now stand between a turn and a row, and it is worth being
# precise about which of them care about order, because the intuition is
# wrong in both directions.
#
# The REJECTIONS do not. Every one is a `continue` in the same loop, so
# `if A: continue; if B: continue` is `if B: continue; if A: continue` for
# every input there is. Reordering them cannot change an answer.
#
# The DEADLINE TABLE does, and heavily: first match wins, so a table that
# tries bare `EOD` before `EOD tomorrow` reads the compound as the day it
# was said. Measured on the corpus, moving the bare form to the front moves
# 20 verdicts. Nothing guarded that until these tests.


def test_no_bare_deadline_form_precedes_a_compound_built_on_it() -> None:
    """First match wins, so every compound has to be tried first.

    Written twice. The first version contained `assert at > bare_eod or
    True`, which cannot fail -- the exact species of check this file exists
    to catch, written while writing this file. The invariant is stated
    directly now: find the compounds by what their patterns contain, find
    the bare forms the same way, and assert every compound comes first.
    """

    table = _rule()._DEADLINE
    days = ("tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday")

    compounds, bare = [], []
    for index, (pattern, _token) in enumerate(table):
        source = pattern.pattern.casefold()
        has_eod = "eod" in source
        has_day = any(day in source for day in days)
        if has_eod and has_day:
            compounds.append((index, pattern.pattern))
        elif has_eod or has_day:
            bare.append((index, pattern.pattern))

    assert compounds, "no compound forms found — the check would pass vacuously"
    assert bare, "no bare forms found — the check would pass vacuously"

    latest_compound = max(index for index, _ in compounds)
    earliest_bare = min(index for index, _ in bare)
    assert latest_compound < earliest_bare, (
        f"a bare deadline form at index {earliest_bare} is tried before a "
        f"compound at index {latest_compound}. First match wins, so the "
        "compound can never match and every turn naming one resolves to the "
        "wrong day"
    )


def test_the_deadline_table_order_is_load_bearing() -> None:
    """If reordering changed nothing, the comment would be decoration.

    This asserts the hazard is real, so that a later reader tidying the
    table alphabetically finds out here rather than in a sweep.
    """

    module = _rule()
    said = "I'll confirm the filing position by EOD tomorrow."
    assert module.commitment_in(said) == "tomorrow"

    original = list(module._DEADLINE)
    bare = next(i for i, (_p, tok) in enumerate(original) if tok == "eod")
    module._DEADLINE = [original[bare]] + [
        row for i, row in enumerate(original) if i != bare
    ]
    try:
        assert module.commitment_in(said) == "eod", (
            "putting the bare end-of-day form first no longer changes this "
            "turn's answer, so either the table stopped mattering or this "
            "example stopped exercising it"
        )
    finally:
        module._DEADLINE = original


def test_a_binding_fallback_outranks_the_rules_it_has_to_outrank() -> None:
    """`at the latest` beats both the disjunction rule and the trigger rule.

    These three sentences each need two conditions to interact correctly,
    and each broke once while the other was being fixed.
    """

    rule = _rule()
    assert rule.commitment_in(
        "I'll send it to you today or tomorrow at the latest"
    ) == ("tomorrow")
    assert (
        rule.commitment_in(
            "I'll flag the room the moment I hear back or by end of week at the latest"
        )
        == "end of week"
    )
    # ...and without the binding phrase, both rules still bite.
    assert rule.commitment_in("I'll send it to you today or tomorrow") is None
    assert (
        rule.commitment_in(
            "I'll fold it into the checklist the moment it's initialed tomorrow"
        )
        is None
    )
