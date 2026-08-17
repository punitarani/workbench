"""A rule and the regex behind it are two artefacts; only one is the task.

Twice in one session the pattern was stricter than the prose it claimed to
implement, and both times the model was marked wrong for reading English
correctly:

* the approval register admitted `sign-off` and `sign off`, and the pattern
  `\\bsign[- ]off\\b` dropped `sign-offs` — 13 rows, twice, identically;
* the commitment register admitted `by <Month> <day>`, and the pattern
  `\\bby (month) (\\d{1,2})\\b` dropped `by April 15th` — 17 of the 42 misses
  that had been certified as model failures.

Neither was catchable by anything else here. The oracle-independence check
shares these patterns deliberately, as the task's specification, so it
agrees with them by construction; and every miss was "verified" by
re-running the same regex over the message it came from.

So this asserts the other direction: phrasings a reader of the instruction
would call an instance of the form must actually match. It needs no world
and no rollout.
"""

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "datasets" / "ashgrove"))

from adjudicate import NET  # noqa: E402
from verify_oracle import COMMITMENT_PATTERNS  # noqa: E402

BY_FORM = dict(COMMITMENT_PATTERNS)

ACCEPTED = [
    "please send it by March 14",
    "please send it by March 14th",
    "audited statements by April 15th",
    "by December 1st at the latest",
    "by August 22nd",
    "by October 3rd",
    "by Monday",
    "by this Tuesday",
    "by next Friday",
    "BY WEDNESDAY",
    "by the end of the week",
    "by the end of this week",
    "by the end of next week",
    "by the end of the month",
    "EOD",
    "eod today",
    "COB Friday",
    "end of day",
    "close of business",
    "within 5 days",
    "within five days",
    "within 3 business days",
    "within two business days",
    "within a day",
    "by tomorrow",
]


def _matches(kind: str, text: str) -> bool:
    return re.search(BY_FORM[kind], text, re.IGNORECASE) is not None


class TestTheCommitmentFormsAcceptTheirOwnPhrasings:
    @pytest.mark.parametrize(
        "text",
        [
            "please send it by March 14",
            "please send it by March 14th",      # the ordinal that cost 17 rows
            "audited statements by April 15th",  # verbatim from the corpus
            "by December 1st at the latest",
            "by August 22nd",
            "by October 3rd",
        ],
    )
    def test_a_calendar_date_in_any_ordinal(self, text: str) -> None:
        assert _matches("date", text), text

    @pytest.mark.parametrize(
        "text",
        ["by Monday", "by this Tuesday", "by next Friday", "BY WEDNESDAY"],
    )
    def test_a_weekday_with_or_without_a_qualifier(self, text: str) -> None:
        assert _matches("weekday", text), text

    @pytest.mark.parametrize(
        "text",
        [
            "by the end of the week",
            "by the end of this week",
            "by the end of next week",
        ],
    )
    def test_every_qualifier_the_table_names(self, text: str) -> None:
        assert _matches("week", text), text

    @pytest.mark.parametrize(
        "text", ["EOD", "eod today", "COB Friday", "end of day", "close of business"]
    )
    def test_the_same_day_forms(self, text: str) -> None:
        assert _matches("day", text), text

    @pytest.mark.parametrize(
        "text",
        [
            "within 5 days",
            "within five days",
            "within 3 business days",
            "within two business days",
            "within a day",
        ],
    )
    def test_counted_days_written_either_way(self, text: str) -> None:
        assert _matches("within", text), text


class TestTheFormsStillRefuseWhatTheInstructionExcludes:
    """The gate must not be widened into admitting everything.

    These are the phrasings the instruction rules out in as many words, and
    they are where the task's difficulty lives — 25 of the commitment
    register's misses are exactly these, and they are genuine model errors.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "wrap end of week",          # EOW: no "by the end of"
            "queues early next week",
            "Wednesday 14:30 works",     # a meeting time, not "by Wednesday"
            "sometime in March",
            "in the next few days",
        ],
    )
    def test_prose_the_rule_excludes(self, text: str) -> None:
        assert not any(_matches(kind, text) for kind in BY_FORM), text


class TestTheAdjudicatorsNetIsWiderThanTheRule:
    """The net exists to catch what the pattern drops, so it must contain it.

    A verdict of "the model invented this" is only worth anything if the
    check behind it could have said otherwise. The net is allowed to
    over-report as much as it likes — `sometime in March` fires it and is
    not a commitment — but a phrasing the rule admits must never slip
    past, or the adjudicator inherits the blind spot it was built to see
    around.
    """

    @pytest.mark.parametrize("text", ACCEPTED)
    def test_every_accepted_phrasing_also_trips_the_net(self, text: str) -> None:
        assert NET.search(text), text

    def test_the_net_is_wider_and_not_merely_equal(self) -> None:
        # If these stopped over-reporting the net would have narrowed to
        # the rule, and it would stop being a second opinion.
        loose = ["sometime in March", "early next week", "wrap end of week", "asap"]
        for text in loose:
            assert NET.search(text), text
            assert not any(_matches(kind, text) for kind in BY_FORM), text

    def test_it_holds_over_the_corpus_and_not_only_over_examples(self) -> None:
        """Every body the rule fires on, the net fires on too."""

        import sqlite3

        bundle = REPO / "out" / "ashgrove" / "bundle" / "state"
        if not (bundle / "gmail.db").is_file():
            pytest.skip("no materialized bundle here")
        checked = 0
        for name in ("gmail.db", "slack.db"):
            db = sqlite3.connect(f"file:{bundle / name}?mode=ro", uri=True)
            for (body,) in db.execute("SELECT body FROM messages"):
                if any(_matches(kind, body) for kind in BY_FORM):
                    assert NET.search(body), body[:200]
                    checked += 1
        assert checked > 100, f"only {checked} bodies exercised the rule"
