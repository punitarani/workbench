"""The viability gate has to measure the corpus, not a constant about it.

`measure_transcripts.py` decides whether a transcript task is possible at
all. It shipped with two constants that had drifted from the world they
described, and because a gate is what people consult *instead of* looking,
neither drift produced a visible wrong answer -- both produced a confident
verdict.

* **A literal matter list.** Twenty client and matter names written by
  hand. By the time the v6 world was recorded, `Hartley` and `Nordholm`
  named no matter the firm had, and `Pryor` -- the third-busiest handle in
  the corpus, 102 turns -- was missing from it. Commitments about Pryor
  were invisible to the gate.
* **A weekday-only deadline regex.** Written when the task admitted
  weekdays only. The brief later widened to admit the relative forms
  *because the corpus writes seven times more of them* (`eod` 245 turns,
  `tomorrow` 201, every weekday combined 169), and the screen never
  followed. It reported the supersession rate of an eighth of the material
  as the corpus's, reading 29% where the admitted forms read 53%.

Each test below fails if either constant comes back.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from dataset_modules import dataset_module

screen = dataset_module("merrick", "measure_transcripts")


def _clio(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    connection = sqlite3.connect(tmp_path / "clio.db")
    connection.execute("CREATE TABLE matters (display_number TEXT, description TEXT)")
    connection.executemany("INSERT INTO matters VALUES (?, ?)", rows)
    connection.commit()
    connection.close()
    return tmp_path


# --------------------------------------------------------------- deadlines


@pytest.mark.parametrize(
    "text",
    [
        "I'll have it by EOD.",
        "I'll have it by COB.",
        "I'll get it out by close of business.",
        "I'll have it by end of day.",
        "I'll have it by the end of the day.",
    ],
)
def test_every_spelling_of_eod_is_one_token(text: str) -> None:
    """The firm's commonest deadline, in the spellings it actually uses.

    These are one deadline. A screen that treated them as distinct would
    count a speaker who said `EOD` once and `end of the day` next week as
    having changed their mind, inventing supersession out of spelling.
    """

    assert screen._deadline(text) == "eod"


def test_the_relative_forms_are_admitted_at_all() -> None:
    """The regression test for the defect this file is named after.

    A weekday-only screen returns `None` for all of these, and every
    downstream figure -- pairs, repeats, supersession share -- is then
    computed over the ~12% of turns that name a weekday.
    """

    assert screen._deadline("I'll have it by EOD") == "eod"
    assert screen._deadline("I'll send it tomorrow") == "tomorrow"
    assert screen._deadline("I'll close it out by end of week") == "end of week"


def test_weekdays_are_still_admitted() -> None:
    for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        assert screen._deadline(f"I'll have it by {day}.") == day.lower()


def test_a_turn_with_no_deadline_names_none() -> None:
    assert screen._deadline("I'll pick this up and let you know.") is None
    assert screen._deadline("") is None


def test_first_match_wins_within_one_turn() -> None:
    """One sentence, two phrasings, one deadline.

    Collecting both would make a single statement look like a speaker
    contradicting themselves -- and supersession is measured by comparing a
    speaker's first statement to their last, so a fake disagreement inside
    one turn becomes a fake revision.
    """

    assert screen._deadline("I'll have it EOD tomorrow at the latest") == "eod"


def test_the_admitted_set_spans_both_families() -> None:
    """Guard the guard.

    Every test above names its own forms, so a screen narrowed back to
    weekdays would fail them loudly -- but a screen narrowed to *relative
    forms only* would still pass most of the file. This asserts the shape
    of the set itself: both families present, and the relative forms first
    so `end of the day` is never claimed by a shorter pattern.
    """

    tokens = [token for _, token in screen.DEADLINE_FORMS]
    assert "eod" in tokens and "tomorrow" in tokens
    assert {"monday", "tuesday", "wednesday", "thursday", "friday"} <= set(tokens)
    assert tokens.index("eod") < tokens.index("monday")


# ----------------------------------------------------------------- matters


def test_handles_come_from_the_served_matter_list(tmp_path: Path) -> None:
    state = _clio(
        tmp_path, [("00005-VerityGrain", "Verity Grain - Ardmore elevator acquisition")]
    )
    handles, ambiguous, unreachable = screen._matter_handles(state)
    assert handles == {"ardmore": "00005-VerityGrain"}
    assert not ambiguous and not unreachable


def test_a_matter_the_firm_does_not_have_yields_no_handle(tmp_path: Path) -> None:
    """The `Hartley`/`Nordholm` regression.

    A literal list can name a matter the world never had; a list derived
    from the served matters structurally cannot. If `_matter_handles` ever
    grows a hardcoded fallback, this fails.
    """

    state = _clio(
        tmp_path, [("00005-VerityGrain", "Verity Grain - Ardmore elevator acquisition")]
    )
    handles, _, _ = screen._matter_handles(state)
    assert "hartley" not in handles
    assert "nordholm" not in handles
    assert set(handles) == {"ardmore"}


def test_a_handle_two_matters_claim_is_dropped_not_assigned(tmp_path: Path) -> None:
    """`Sandhurst` named four matters at once after two were minted mid-run.

    Assigning it to either would attach a speaker's commitment to a matter
    they did not name, and the row would be graded wrong for a reason no
    amount of reading could fix.
    """

    state = _clio(
        tmp_path,
        [
            ("00010-Northmoor", "Northmoor - Sandhurst platform acquisition"),
            ("00011-Northmoor", "Northmoor - Sandhurst add-on diligence"),
        ],
    )
    handles, ambiguous, _ = screen._matter_handles(state)
    assert handles == {}
    assert ambiguous == ["sandhurst"]


def test_a_status_sentence_yields_no_handle(tmp_path: Path) -> None:
    """Matters minted mid-run are described with a sentence, not a name.

    Every capitalised word in one looks like a proper noun, so a naive
    reading yields `Clearance`, `Confirmation` and `Pending` as matter
    handles -- words that match ordinary prose and would attach commitments
    to a matter nobody mentioned.
    """

    state = _clio(
        tmp_path,
        [
            (
                "00033-Ravndal",
                "Ravndal - Priyanka Sandhurst Clearance Confirmation Pending",
            )
        ],
    )
    handles, _, unreachable = screen._matter_handles(state)
    assert handles == {}
    assert unreachable == ["00033-Ravndal"]


def test_an_acronym_does_not_hide_a_real_handle(tmp_path: Path) -> None:
    """`Fairmont OEM licence` is two-thirds capitalised and is not a sentence.

    Counting ALL-CAPS as evidence of Title Case pushed this matter over the
    threshold and lost a handle the corpus actually says.
    """

    state = _clio(
        tmp_path, [("00018-Linden", "Linden Robotics - Fairmont OEM licence")]
    )
    handles, _, unreachable = screen._matter_handles(state)
    assert handles == {"fairmont": "00018-Linden"}
    assert not unreachable


def test_a_common_noun_description_is_reported_unreachable(tmp_path: Path) -> None:
    state = _clio(tmp_path, [("00025-Nwosu", "Firm - administration")])
    handles, _, unreachable = screen._matter_handles(state)
    assert handles == {}
    assert unreachable == ["00025-Nwosu"]


def test_an_empty_matter_list_refuses(tmp_path: Path) -> None:
    """Guard the guard.

    With no matters every figure downstream is zero, and a zero printed
    beside `ABSENT: nothing is ever superseded` reads as a fact about the
    corpus rather than a missing database.
    """

    with pytest.raises(SystemExit, match="serves no matters"):
        screen._matter_handles(_clio(tmp_path, []))


def test_a_missing_clio_refuses(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no clio.db"):
        screen._matter_handles(tmp_path)


# ------------------------------------------------------- the graded population


def test_the_owner_forms_are_the_ones_the_corpus_writes() -> None:
    """A screen that ignores who owns the work measures a superset.

    The third drift in this same file: `_supersession` grouped every turn
    that mentioned a matter and a date, including a chair recapping
    somebody else's commitment (`Reinhardt, $61,047.00 out by Thursday`).
    No task keyed to the speaker can grade those -- the person who owes it
    never said it -- so the screen promised twice the gradeable material
    the corpus holds. It now reports both populations, and this pins the
    narrower one to what the corpus actually writes: `I'll` at 501 turns
    and `I will` at 9, and nothing looser.

    `I have` is possession, `I'd` is conditional, and `I can` is as often
    `I can't`. Admitting any of them puts turns in the register that are
    not commitments at all.
    """

    assert screen._OWNER.search("I'll have it by EOD")
    assert screen._OWNER.search("I will have it by EOD")
    for not_a_commitment in (
        "I have the file open",
        "I'd want to see the schedule first",
        "I can't get to it this week",
        "Reinhardt, $61,047.00 out by Thursday",
    ):
        assert not screen._OWNER.search(not_a_commitment), not_a_commitment
