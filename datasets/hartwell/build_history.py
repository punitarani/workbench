"""Build the Hartwell & Marsh pilot history: genesis plus the first five
procedural workdays, fully offline and deterministic.

    uv run python datasets/hartwell/build_history.py [--out out/hartwell]
        [--seed 42] [--check]

Writes ``world.jsonl``, validates it, projects it into
``pilot-workspace/`` (seat unset), and prints per-day event counts.
``--check`` instead builds the log twice into temporary directories and
fails unless the bytes are identical.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events
from workbench.environment import materialize
from workbench.simulation.chronicle.builder import Chronicle
from workbench.simulation.chronicle.minter import minter_from_events
from workbench.simulation.chronicle.procedural import procedural_day
from workbench.workplaces.hartwell import WINDOW, build_genesis, procedural_cast

PILOT_WORKDAYS = 5


def build_world(out_dir: Path, seed: Seed) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "world.jsonl"
    if log_path.exists():
        log_path.unlink()

    genesis = build_genesis(seed)
    chronicle = Chronicle(log_path, window=WINDOW)
    chronicle.write_genesis(genesis.events)

    minter = minter_from_events(genesis.events)
    cast = procedural_cast(genesis)
    for day_index in WINDOW.workdays()[:PILOT_WORKDAYS]:
        drafts = procedural_day(
            seed=seed,
            window=WINDOW,
            day_index=day_index,
            cast=cast,
            minter=minter,
        )
        chronicle.add_procedural_day(day_index, drafts)
    chronicle.finish()
    return log_path


def print_summary(log_path: Path) -> None:
    events = read_events(log_path)
    order = ["genesis"]
    counts: dict[str, Counter[str]] = {"genesis": Counter()}
    day = "genesis"
    for event in events:
        if event.tag == "sim.day.started":
            day = event.payload.day
            order.append(day)
            counts[day] = Counter()
        counts[day][event.tag] += 1
    for day in order:
        total = sum(counts[day].values())
        print(f"{day}: {total} events")
        for tag, count in sorted(counts[day].items()):
            print(f"  {tag}: {count}")


def run_check(seed: Seed) -> int:
    def build_bytes() -> bytes:
        with TemporaryDirectory(prefix="hartwell-check-") as tmp:
            return build_world(Path(tmp), seed).read_bytes()

    first, second = build_bytes(), build_bytes()
    if first != second:
        print("determinism check FAILED: two builds differ", file=sys.stderr)
        return 1
    print(f"determinism check passed: {len(first)} identical bytes")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("out/hartwell"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--check",
        action="store_true",
        help="build twice into temp dirs and compare bytes",
    )
    args = parser.parse_args(argv)
    seed = Seed(root=args.seed)

    if args.check:
        return run_check(seed)

    log_path = build_world(args.out, seed)
    workspace = materialize(log_path, args.out / "pilot-workspace")
    print_summary(log_path)
    print(f"{workspace.event_count} events -> {workspace.workspace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
