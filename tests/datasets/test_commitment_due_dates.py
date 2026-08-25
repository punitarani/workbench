"""The date arithmetic of the live commitment register.

This is the part of the task that is a property of the English rather than
of the recording, so it is written and settled before the corpus lands.
Every convention asserted here is one the corpus exercises, with the count
that earned it its place in the brief.

The register grades the resolved date rather than the word, and that is the
whole mechanism: `EOD` said in two different meetings is the same word and
two different obligations. Measured across five windows, grading the token
hands a reader who guesses the commonest word 47-69% of the field for free;
grading the date hands them 16-23%, and roughly doubles the error rate of a
reader who takes each person's first statement (to 62-72%).
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

_TASK = (
    Path(__file__).resolve().parents[2]
    / "datasets/merrick/tasks/live-commitment-register"
)


def _solver():
    """Import the solver without a corpus.

    It reads `WORKBENCH_STATE` at import, and the window calls `measure()`,
    which raises. Both are deliberate — the file must fail loudly when run
    unmeasured — so the date logic was put above that line precisely so it
    could be imported and tested on its own.
    """

    import os

    # Set for the import and put back afterwards. `os.environ.setdefault`
    # here mutated the *session* environment permanently, and every
    # subprocess a later test started inherited it -- which is how
    # legal-nda's two tasks began failing: their `solve.sh` reads
    # `WORKBENCH_STATE` with a relative default, so an inherited absolute
    # path pointed it at another dataset's databases and it exited 1. The
    # tests passed alone and failed in the suite, and the traceback named
    # legal-nda.
    previous = os.environ.get("WORKBENCH_STATE")
    os.environ["WORKBENCH_STATE"] = str(_TASK)
    sys.path.insert(0, str(_TASK.parents[1]))
    spec = importlib.util.spec_from_file_location(
        "_lcr_solve", _TASK / "solution/solve.py"
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            os.environ.pop("WORKBENCH_STATE", None)
        else:
            os.environ["WORKBENCH_STATE"] = previous
    return module


solve = _solver()

MON, TUE, WED, THU, FRI = (dt.date(2026, 2, 16 + n) for n in range(5))


# ------------------------------------------------------------------ tokens


def test_eod_tomorrow_is_one_deadline_and_it_means_tomorrow() -> None:
    """The commonest two-form phrase in the corpus: 47 of 178 turns.

    A form table that tries `EOD` before the compound resolves a quarter of
    everything the task grades to the wrong day — and does it silently,
    because `eod` is a perfectly valid token that produces a perfectly
    plausible date.
    """

    assert solve.deadline_token("I'll confirm the date by EOD tomorrow") == "tomorrow"
    assert solve.deadline_token("I'll have it COB tomorrow") == "tomorrow"
    assert solve.deadline_token("I'll have it by end of day tomorrow") == "tomorrow"


def test_a_bare_eod_is_still_today() -> None:
    assert solve.deadline_token("I'll have it by EOD") == "eod"
    assert solve.deadline_token("I'll get it out by close of business") == "eod"


def test_one_turn_names_one_deadline() -> None:
    """40% of commitment turns name two forms.

    Collecting both would make a single sentence disagree with itself, and
    supersession is computed by comparing a speaker's first statement to
    their last — so a fake disagreement inside one turn becomes a fake
    revision.
    """

    assert solve.deadline_token("I'll have it Thursday, Friday at the latest") in {
        "thursday",
        "friday",
    }
    assert solve.deadline_token("I'll start tomorrow and finish by Thursday") in {
        "tomorrow",
        "thursday",
    }


def test_a_turn_with_no_deadline_names_none() -> None:
    assert solve.deadline_token("I'll pick this up and come back to you") is None
    assert solve.deadline_token("") is None


# ------------------------------------------------------------------- dates


def test_eod_is_the_day_it_was_said() -> None:
    assert solve.due_date(WED, "eod") == WED


def test_tomorrow_skips_the_weekend() -> None:
    """Said on a Friday, `tomorrow` means Monday — 3 turns in 56 days.

    The firm records no weekend days at all: 58 recorded days, every one
    Monday to Friday. A Saturday deadline would be a date on which nobody
    could deliver, so it is not one the register can report.
    """

    assert solve.due_date(THU, "tomorrow") == FRI
    assert solve.due_date(FRI, "tomorrow") == MON + dt.timedelta(days=7)


def test_end_of_week_is_that_weeks_friday() -> None:
    assert solve.due_date(MON, "end of week") == FRI
    assert solve.due_date(THU, "end of week") == FRI


def test_end_of_week_said_on_friday_is_that_same_friday() -> None:
    """Not a week later. Somebody saying "end of week" on Friday morning
    means today, and reading it as next Friday moves a live commitment a
    week into the future — the exact error the register exists to catch."""

    assert solve.due_date(FRI, "end of week") == FRI


def test_a_weekday_names_its_next_occurrence() -> None:
    assert solve.due_date(MON, "thursday") == THU
    assert solve.due_date(TUE, "friday") == FRI


def test_a_weekday_earlier_in_the_week_is_next_week() -> None:
    """26 turns in 56 days name a weekday already past.

    Said on Thursday, "Tuesday" cannot mean two days ago — a deadline in the
    past is not a deadline. It is next Tuesday.
    """

    assert solve.due_date(THU, "tuesday") == TUE + dt.timedelta(days=7)
    assert solve.due_date(FRI, "monday") == MON + dt.timedelta(days=7)


def test_a_weekday_said_on_that_same_weekday_is_next_week() -> None:
    """3 turns. Somebody saying "Thursday" in Thursday's docket call is
    talking about the next one, not the meeting they are sitting in."""

    assert solve.due_date(THU, "thursday") == THU + dt.timedelta(days=7)


@pytest.mark.parametrize("token", ["eod", "tomorrow", "end of week", *solve.WEEKDAYS])
def test_every_token_resolves_to_a_working_day(token: str) -> None:
    """Guard the guard.

    Each convention above is asserted on one or two dates. This asserts the
    property they all have to share, across every starting weekday: a
    register of what the firm owes cannot name a day the firm does not work.
    """

    for offset in range(5):
        said = MON + dt.timedelta(days=offset)
        assert solve.due_date(said, token).weekday() < 5, (token, said)


def test_the_resolved_date_is_never_before_the_day_it_was_said() -> None:
    for offset in range(5):
        said = MON + dt.timedelta(days=offset)
        for token in ("eod", "tomorrow", "end of week", *solve.WEEKDAYS):
            assert solve.due_date(said, token) >= said, (token, said)


# --------------------------------------------------------- punctuated forms


@pytest.mark.parametrize(
    ("text", "token"),
    [
        ("I'll have it by EOD-tomorrow", "tomorrow"),
        ("I'll have it by EOD tomorrow", "tomorrow"),
        ("I'll close it by end-of-week", "end of week"),
        ("I'll close it by end of week", "end of week"),
        ("I'll send it end-of-day", "eod"),
        ("I'll send it end of the day", "eod"),
    ],
)
def test_a_hyphen_is_a_gap_like_any_other(text: str, token: str) -> None:
    """The firm writes `EOD-tomorrow`, and a pattern anchored on `\\s+` is a
    day early.

    Found by the independence gate rather than by reading: the verifier
    tokenises the turn and splits on any non-word character, so it read
    these correctly while the solver's regex matched only the bare `EOD`
    inside `EOD-tomorrow` and resolved the deadline to the wrong day. The
    two derivations disagreed by one supersession on a 47-day window, which
    is a small number standing for a systematic error — `eod` is a valid
    token producing a plausible date, so nothing downstream would have
    looked wrong.
    """

    assert solve.deadline_token(text) == token


# ------------------------------------------------- the promise and the date


def test_the_promise_and_the_date_must_share_a_clause() -> None:
    """The defect three model families caught before this test did.

    The rule first asked whether a turn held an owner form *somewhere* and a
    deadline *somewhere*. That was narrowed to a sentence, and a sentence
    was still too big: eleven of the twenty rows the sentence rule produced
    paired a promise with a date from a neighbouring clause. opus-5, glm-5.2
    and kimi-k3 declined all eleven across nine trials, and reading the
    transcripts agreed with them.

    This test previously asserted the condition case fired, with a comment
    reasoning that "inside one sentence the reader cannot tell a condition
    from a deadline". The brief's own condition example *is* one sentence
    and the brief says it makes no row -- so the test was pinning the gap
    between the rule and the brief, in the brief's own words, as intent.
    """

    # The docket manager reciting somebody else's deadline, then promising
    # something undated. No row.
    assert (
        solve.commitment_in(
            "Position Statement review, owner Jamal, due EOD tomorrow. "
            "I'll circulate the updated Master Docket Report."
        )
        is None
    )
    # The brief's own "date as a condition" example, verbatim, in ONE
    # sentence: the date precedes the promise and conditions it.
    assert (
        solve.commitment_in(
            "If it's still open Wednesday EOD, flag me directly and I'll make the call."
        )
        is None
    )
    # A promise contingent on an external event, with the date elsewhere.
    assert (
        solve.commitment_in(
            "I'm holding EOD tomorrow as the checkpoint. "
            "The second I get a response from their counsel I'll log it."
        )
        is None
    )
    # One clause is not one sentence. The deadline belongs to the docketing
    # manager's confirmation; the promise after the dash carries none.
    assert (
        solve.commitment_in(
            "I've escalated the two applications and I'm expecting written "
            "confirmation by end of day - I'll flag that to Priyanka the "
            "moment it lands."
        )
        is None
    )
    # A conjunction does NOT end a clause: one subject, two verbs, one date.
    assert (
        solve.commitment_in("I'll have it edited and released by Wednesday.")
        == "wednesday"
    )
    # Attachment: a bare form mid-clause names a task, not a day.
    assert (
        solve.commitment_in("Quentin, I'll defer the EOD escalation ownership to you.")
        is None
    )
    # ...but a bare form that ENDS the clause is a deadline.
    assert (
        solve.commitment_in("I'll have the scope and timeline doc to Clement Thursday.")
        == "thursday"
    )
    # Negation between the promise and the day rules the day out, however
    # much verb phrase stands in between.
    assert (
        solve.commitment_in(
            "I'll cross-check same day and give you a firm due date the "
            "moment it lands, so let's not slip that to Monday."
        )
        is None
    )


def test_a_promise_and_its_own_date_is_a_row() -> None:
    assert (
        solve.commitment_in("I'll have the privilege log to the team by EOD tomorrow.")
        == "tomorrow"
    )


def test_a_semicolon_ends_a_sentence() -> None:
    """This firm hangs independent statements off one another with them, so
    a rule that ignores the semicolon pairs a promise with a stranger's
    date."""

    assert (
        solve.commitment_in(
            "Cecile's note is due Thursday; I'll hold off drafting until it lands."
        )
        is None
    )


def test_a_full_stop_inside_a_word_does_not_end_a_sentence() -> None:
    """`.xlsx` is not the end of a sentence.

    The independent verifier split on any terminal mark and broke this
    commitment in half, separating the promise from its date — which is how
    the two derivations came to disagree by exactly one row on a commitment
    both should have kept. A mark ends a sentence when whitespace follows
    it; decimals, file extensions and abbreviations end nothing.
    """

    assert (
        solve.commitment_in(
            "The privilege log is on track, I'll have the updated .xlsx "
            "to the team by EOD tomorrow, no deadline risk."
        )
        == "tomorrow"
    )


# ------------------------------------------------------ deadlines ruled out


def test_a_deadline_named_only_to_reject_it_makes_no_row() -> None:
    """ "not wednesday" is not a commitment to Wednesday.

    Three of 132 commitment sentences on the record do this, and all three
    are real: the speaker's actual deadline is unstated or unadmitted
    (`today`, `same day`), so the sentence should make no row at all.
    Matching the rejected form instead puts a commitment in the register
    that its owner explicitly disclaimed — and it cost a frontier model a
    row it had read correctly.
    """

    assert solve.commitment_in("I'll flag it same day, not wednesday morning.") is None
    assert solve.commitment_in("I'll get an answer today, not tomorrow.") is None
    assert (
        solve.commitment_in("I'll flag the second I hear back, urgent, not EOD.")
        is None
    )


def test_the_guard_is_tight_enough_not_to_eat_real_deadlines() -> None:
    """Guard the guard, and the looser rule was measured before being
    discarded.

    Scanning a 28-character window for any negation flags 8 of 132
    sentences and five are false. In the first case below the `not` belongs
    to the guess, not to the deadline. In the second the negation lands on a
    *later* form that first-match-wins never reaches — Wednesday is the
    commitment and Friday is the thing being avoided.
    """

    assert (
        solve.commitment_in("I'll have a real number, not a guess, by end of day.")
        == "eod"
    )
    assert (
        solve.commitment_in(
            "I'll have it back to Ulrich by Wednesday so it's not in Friday's crunch."
        )
        == "wednesday"
    )
    assert solve.commitment_in("I'll send it by tomorrow.") == "tomorrow"


def test_a_negation_reaches_across_its_connective() -> None:
    """`not by Friday` and `not until Friday` negate as plainly as
    `not Friday`; the connective does not shelter the form."""

    assert solve.commitment_in("I'll have it done, not by Friday.") is None
    assert solve.commitment_in("I'll start it, rather than Monday.") is None


def test_somebody_elses_clause_between_the_promise_and_the_day() -> None:
    """A new subject breaks the link; a conjunction on its own does not.

    Dropping this condition entirely left all 33 tests in this file green,
    so it was doing its work unwatched. The rows it removes are the ones
    where a date belongs to a second actor's action -- which is the single
    commonest way this register has been wrong.
    """

    # `so you can finalize ... before tomorrow` dates Mira's work.
    assert (
        solve.commitment_in(
            "I'll ping the moment I have it, Mira, so you can finalize the "
            "Officer's Certificate before tomorrow."
        )
        is None
    )
    # Same shape, subject `everyone`, and the verb CONTRACTED onto it. The
    # tokeniser splits `everyone's` into `everyone` and `s`, so a rule that
    # looks only for whole finite verbs cannot see this one -- and did not:
    # three model families declined this row nine times out of nine while
    # the register carried it.
    assert (
        solve.commitment_in(
            "I'll update the checklist entry and recirculate the final version "
            "to Mira and Quentin so everyone's working off the same document "
            "before it goes out tomorrow."
        )
        is None
    )
    # A conjunction with no new subject is still the speaker's own promise.
    assert (
        solve.commitment_in("I'll have it edited and released by Wednesday.")
        == "wednesday"
    )
    # ...and one where the second clause's subject IS the speaker.
    assert (
        solve.commitment_in(
            "I'll call Okafor myself today, not have an associate chase it, "
            "and I'll have a firm date before Friday."
        )
        == "friday"
    )
    # A possessive is not a contracted verb: `Thandiwe's sign-off` names a
    # thing, and reading its `s` as a finite verb put the two derivations
    # four turns apart.
    assert (
        solve.commitment_in(
            "I'll add a caveat to the Atwater slide flagging that the Section "
            "III timeline assumes Thandiwe's sign-off by Wednesday."
        )
        == "wednesday"
    )
