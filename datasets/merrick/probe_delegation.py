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
