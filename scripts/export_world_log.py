"""Write ``world.jsonl`` and ``manifest.json`` from a run store.

    uv run python scripts/export_world_log.py --out out/merrick/epoch-v3

The world log is the canonical artefact: every downstream step — the
materializer, the validator, the coherence gate, the fidelity bands, every
task's reference solver — reads ``world.jsonl`` and none of them reads
``run.db``. And ``export_jsonl`` had exactly one caller, in
``simulation.run._finish``, which runs only when a recording *completes*.

A six-month recording takes about a day. Interrupt it at hour twenty-three
— a signal, a laptop lid, an OOM — and every event is safely in the store
and *not one downstream tool can read any of them*. The Merrick v2
recording was stopped at day 40 of 130 and left exactly that: an 18MB
``run.db`` holding 13,463 events, and no world log at all.

Nothing was lost, but nothing was reachable either, which is this tree's
most familiar failure shape wearing operational clothes: a capability that
is correct, has one caller, and the caller is on the happy path.

Safe to run against a live recording. SQLite is in WAL mode, so this reads
a consistent snapshot while the writer continues; the export is simply
truncated at whatever was committed when it started. Re-run it when the
recording finishes to get the whole thing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.store import SqliteRunStore, export_jsonl  # noqa: E402
from core.worldlog.manifest import RunManifest, write_manifest  # noqa: E402


def export(out_dir: Path, *, force: bool = False) -> int:
    store_path = out_dir / "run.db"
    if not store_path.is_file():
        raise SystemExit(f"no run store at {store_path}")
    log_path = out_dir / "world.jsonl"
    if log_path.exists() and not force:
        raise SystemExit(
            f"{log_path} already exists; pass --force to overwrite it. "
            "Overwriting a completed export with a partial one is the "
            "mistake this guard exists to prevent."
        )

    store = SqliteRunStore.open(store_path)
    try:
        # The manifest's identity comes from the store, and if the store
        # does not have it this refuses rather than inventing it.
        #
        # The first version defaulted `workplace_id` to the directory name
        # and `seed_root` to 0. That turns "this store is not a recording"
        # into a manifest reading `workplace epoch, seed 0`, which is a
        # confident, wrong, authoritative-looking answer — the exact
        # failure mode the docstring below the fold warns about. A missing
        # identity is an absence, and absences get refused.
        workplace_id = store.get_meta("workplace_id")
        raw_seed = store.get_meta("seed_root")
        config_hash = store.get_meta("config_hash") or ""
        fingerprint = store.get_meta("engine_fingerprint")
        if not workplace_id or raw_seed is None:
            raise SystemExit(
                f"{store_path} carries no run identity (workplace_id="
                f"{workplace_id!r}, seed_root={raw_seed!r}); it is not a "
                "recording this can label, and a manifest guessed from the "
                "directory name would look authoritative and be wrong"
            )
        seed_root = int(raw_seed)
        export_jsonl(store, log_path)
    finally:
        store.close()

    manifest = RunManifest.for_log(
        log_path,
        run_id=f"run-{workplace_id}-{seed_root}",
        seed_root=seed_root,
        workplace_id=workplace_id,
        config_hash=config_hash,
    )
    write_manifest(manifest, out_dir / "manifest.json")
    print(f"wrote {log_path} — {manifest.event_count} events")
    print(f"      {out_dir / 'manifest.json'}")
    print(f"  workplace {workplace_id}  seed {seed_root}")
    print(f"  config_hash        {config_hash[:16]}")
    print(f"  engine_fingerprint {(fingerprint or '(not recorded)')[:16]}")
    print(f"  world_sha256       {manifest.world_sha256[:16]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="the run directory")
    parser.add_argument("--force", action="store_true", help="overwrite an existing world.jsonl")
    args = parser.parse_args(argv)
    return export(args.out, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
