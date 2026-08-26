"""Record a short world whose people DELEGATE, and see whether they do.

    OPENROUTER_API_KEY=... uv run python datasets/merrick/probe_delegation.py \
        --days 10 --out out/probe-delegation

**The one arrow in the pipeline with no experiment behind it.** Everything
downstream of a recording has been measured: which surfaces can host a
task, which rules land in band, which keys are gradable. The claim upstream
of all of it — that a world can be *specified* to carry a task family — has
only correlational support:

    merrick   21 personas mentioning deadlines 8 times
              -> 537 dated owner-mails, 175 admitted promises
    calder    17 personas mentioning them 0 times
              -> 82 owner-mails, ZERO carrying any deadline form

Correlation across two worlds built months apart by different hands is not
nothing, but it is not the experiment either. This is the experiment: take
merrick's cast, change **one thing** about it, record, and count.

**The one thing.** Every recorded world is short of third-person
assignment — one person saying another will do something by a date. Across
four worlds the anchored form appears 1, 8, 14 and 0 times. That absence is
what blocks a second task family: the anchor produces clean extractions
wherever it occurs, there is simply never enough of it.

So the personas here gain a delegation register and nothing else. Same
firm, same matters, same cues, same seed. If assignment appears in the
recording, a world spec is a lever on what tasks are possible. If it does
not, the lever is somewhere else and the pipeline's upstream arrow is
wrong — which is worth knowing at the price of ten days rather than after
a task is designed around it.

Ten days, not a hundred and thirty: the question is whether the *form*
appears at all, and its rate per day is measurable from a short run. This
never writes to `out/merrick`, and nothing it records is shipped.

**Result: the lever works.** Against merrick's own matched first ten days,
which hold ZERO anchored assignments in 178 meeting turns and 83 mails,
this recording holds 4 in 191 turns and 2 in 116 mails -- ten times the
full-corpus baseline rate in meetings (p = 0.0008) and twenty-four times
in mail (p = 0.003). One sentence per persona, same cast, same seed.

**And the rule it enables is not free.** The recording is a dev set for
the family, and reading it says what the family will cost. Fifteen clauses
carry a named colleague, a verb, and a deadline:

    has    8    "Ingrid has lender consent due Wednesday close of business"
    is     4    "Adaora is still on for Thursday"
    will   2    "Quentin will have a name to circulate by tomorrow AM"
    owes   1    "Adaora owes Dov a name and one-line scope by tomorrow morning"

The unambiguous form -- a name, a future auxiliary, an attached date -- is
`will`, and at 2 in ten days it is too rare to key a register on. The
volume is `has`, and `has` is two different sentences:

    "Ingrid has lender consent due Wednesday"      an obligation
    "I'll update that line once Mira has a name"   the SPEAKER's promise

So the family is buildable and it inherits the long tail that took the
first-person rule five versions and four defects. What it does not have to
re-derive is the machinery: clause split, attachment, negation,
alternatives and the deadline table are all about English rather than
about who is speaking, and only the subject changes.

**The 45-day recording, and what it costs.** 19,340 steps, 1,318 turns and
mails. Applying the graded machinery with the subject swapped:

    a colleague + an obligation verb + a day in ONE clause    43 turns
    ...that the graded machinery admits                       15 turns  (35%)

Fifteen in forty-five days, and reading them is the point. Some are exactly
the form the family needs -- "Rosalie owes me the draft by midday
tomorrow", "Samir has Sub-Fund I cert by EOD Thursday". At least two are
plainly wrong: "so Fionnuala has them ahead of 9:30 tomorrow" is the
SPEAKER's promise with a colleague in a purpose clause, and "you cannot
represent a date to Frost tomorrow" assigns nothing to Ulrich. Several more
are reports of what somebody is doing rather than obligations they owe.

**This refines the probe's own result rather than contradicting it.** The
spec change reliably creates the FORM -- ten and twenty-four times the
baseline rate, p = 0.0008 and 0.003, against a matched control of zero. It
does not, on its own, create enough of the GRADABLE subset to key a
register on: a register wants fourteen-plus rows with supersession, and
this yields fifteen raw candidates of which maybe two-thirds survive
reading.

Creating a form and creating a gradable form are different requirements,
and the probe measured the first. The cost of the second is now known
rather than guessed: roughly three times this recording -- 130-odd days,
about twenty hours -- plus a rule-correction cycle of the size the
first-person rule took, which was fourteen defects found over one day.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from core.seed import Seed  # noqa: E402
from simulation.engine.engine import StopCondition  # noqa: E402
from simulation.workplace.compile import compile_workplace  # noqa: E402
from workplaces.merrick.epoch import epoch_director, epoch_spec  # noqa: E402

# What the cast gains, and the whole of the change. Written as a register
# rather than an instruction to use particular words: naming the words
# would put them in the corpus by fiat, and the question is whether the
# form arises from how people are told to behave.
DELEGATION = (
    " When work belongs to somebody else, say so by name and say when they "
    "will have it done — you track other people's commitments as carefully "
    "as your own, and you restate them out loud so the room has them."
)


def delegating_spec(days: int):
    """Merrick's own spec, with a delegation register added to each persona."""

    spec = epoch_spec(days=days)
    people = []
    for person in spec.people:
        persona = person.persona
        if persona is None:
            people.append(person)
            continue
        style = persona.channel_style
        # Appended, never replaced: replacing the register would change the
        # firm's whole voice and the recording would differ for reasons
        # that have nothing to do with delegation.
        changed = style.model_copy(
            update={"email_register": style.email_register + DELEGATION}
        )
        people.append(
            person.model_copy(
                update={
                    "persona": persona.model_copy(update={"channel_style": changed})
                }
            )
        )
    return spec.model_copy(update={"people": tuple(people)})


async def record(args: argparse.Namespace) -> int:
    import os

    from simulation.lm.budget import BudgetedLM
    from simulation.lm.cassette import CassetteStore, RecordingLM
    from simulation.lm.openrouter import OpenRouterLM
    from simulation.lm.retry import RetryLM
    from simulation.run import run_compiled

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("recording needs OPENROUTER_API_KEY")

    # Read from `run_epoch` rather than restated: the models and the
    # provider pin are what make a recording comparable to merrick's own,
    # and a second copy of them here would make this probe a different
    # experiment the day either moves.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from run_epoch import DEEP_MODEL, FAST_MODEL, PROVIDERS  # noqa: PLC0415

    seed = Seed(root=args.seed)
    spec = delegating_spec(args.days)
    compiled = compile_workplace(spec, seed)
    backend = OpenRouterLM(
        api_key=key,
        providers=PROVIDERS,
        providers_by_model={DEEP_MODEL: PROVIDERS},
        max_concurrency=args.concurrency,
    )
    inner = BudgetedLM(
        RecordingLM(RetryLM(backend), CassetteStore(args.out / "cassette")),
        max_calls=args.max_calls,
    )
    try:
        result = await run_compiled(
            compiled,
            seed=seed,
            out_dir=args.out,
            inner_lm=inner,
            model=FAST_MODEL,
            deep_model=DEEP_MODEL,
            director=epoch_director(seed),
            stop=StopCondition(end_time=compiled.end_time),
            checkpoint_every=100,
            window=args.window,
        )
    finally:
        await backend.close()
    print(f"  recorded: {result.steps} steps, reason={result.reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--out", type=Path, default=REPO / "out" / "probe-delegation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window", type=int, default=16)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--max-calls", type=int, default=20000)
    parser.add_argument(
        "--show-change",
        action="store_true",
        help="print one persona before and after, and record nothing",
    )
    args = parser.parse_args(argv)

    if args.show_change:
        before = epoch_spec(days=args.days).people[0]
        after = delegating_spec(args.days).people[0]
        print(f"  {before.name}\n")
        print(f"  before: {before.persona.channel_style.email_register}\n")
        print(f"  after : {after.persona.channel_style.email_register}")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    return asyncio.run(record(args))


if __name__ == "__main__":
    raise SystemExit(main())
