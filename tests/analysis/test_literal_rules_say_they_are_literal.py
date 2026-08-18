"""A rule that matches words in prose must say it ignores what they mean.

Five tasks in this suite grade "does this body contain one of these
forms". Each began with a title and a preamble describing a *concept* —
a register of promises, work reported complete, who approved what — and
an operational test that is pure string matching. When those disagree,
a careful reader trusts the concept, and the grader trusts the string.

Every time, the model that read for meaning lost points to an oracle
that read for text:

* `commitment-register` — "every deadline the firm has promised" against
  seven token forms;
* `commitment-follow-through` — the same rule, the same gap;
* `open-items-triage` — "that message asks for something" against twelve
  phrases, where *"what we need to deliver"* contains `we need`;
* `completion-claims` — "work reported complete" against the word
  `complete`, where *"that gives you the complete picture"* counts;
* `approval-register` — "who approved what" against six words, where
  *"sign-off protocol once testing wraps"* counts.

The fifth was found by audit rather than by a rollout, which is the only
reason it never cost a measurement: it had been scoring 0.997 because
gpt-5.6-sol happened to apply the rule literally.

So: any task whose rule matches words inside a message body must say, in
its own instruction, that the test is textual. The sentence is cheap and
the alternative is grading whether a model filters on meaning — which is
a skill nobody should be trained out of.
"""

import re
from pathlib import Path

import pytest

TASKS = Path(__file__).resolve().parents[2] / "datasets" / "ashgrove" / "tasks"

# Tasks matching forms against free prose. `workpaper-open-items` is
# deliberately absent: its rule compares a spreadsheet's Status *cell*
# against five exact strings, and a cell has no sentence to misread.
PROSE_MATCHERS = (
    "approval-register",
    "commitment-follow-through",
    "commitment-register",
    "completion-claims",
    "open-items-triage",
    "opening-days-commitment-register",
    "opening-days-completion-claims",
    "opening-week-follow-through",
)

_SAYS_SO = re.compile(r"textual,? not editorial", re.IGNORECASE)


@pytest.mark.parametrize("task", PROSE_MATCHERS)
def test_it_says_the_test_is_textual(task: str) -> None:
    instruction = (TASKS / task / "instruction.md").read_text()
    assert _SAYS_SO.search(instruction), (
        f"{task} matches forms in prose but never says the test is textual "
        "rather than editorial. Its own framing describes a concept, so a "
        "reader who filters on meaning is penalised for the more careful "
        "reading — which has happened on four of these tasks already."
    )


def test_the_list_covers_every_prose_matcher() -> None:
    """Guard the guard: a new prose task must be added here, not forgotten."""

    named = set(PROSE_MATCHERS) | {"workpaper-open-items"}
    for task in sorted(p.name for p in TASKS.iterdir() if p.is_dir()):
        solver = TASKS / task / "solution" / "solve.py"
        if not solver.is_file():
            continue
        source = solver.read_text()
        # A task greps message bodies if its solver matches against `body`.
        if re.search(r"re\.(search|finditer)\([^)]*body", source) or (
            "_form(body)" in source
        ):
            assert task in named, (
                f"{task} matches forms against message bodies but is not in "
                "PROSE_MATCHERS. Add it, and give it the textual-test clause."
            )
