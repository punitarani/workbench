"""Run a list of sweeps, four at a time, and stop when the list is done.

    uv run python scripts/sweep_queue.py --queue queue.txt

One line per sweep: `<dataset> <task> <model> <tag> [k]`.

**Four is a measured ceiling, not a guess.** Past it, Docker's default
address pool runs out and trials come back 0.000 in seconds -- a harness
failure indistinguishable downstream from a model that cannot do the task,
and one that has already been averaged into a published mean in this tree.
`docs/RUNNING-SWEEPS.md` carries the pool configuration and the symptoms.

This exists because the alternative is watching for a free slot by hand
and launching the next one, which is both slow and the sort of thing that
gets skipped at the end of a long session -- leaving three tiers measured
and one not, which reads as "not run" and blocks certification.

It refuses a tag with no model prefix for the same reason `rollout.py`
does: a job directory nothing reads is worse than a job that never ran,
because it looks like work.
"""

import argparse
import os
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CEILING = 4
PREFIX = {"gpt-5.6-sol": "gpt", "opus-5": "opus", "glm-5.2": "glm", "kimi-k3": "kimi"}


def _running() -> int:
    out = subprocess.run(
        ["ps", "-eo", "command"], capture_output=True, text=True
    ).stdout
    return sum(1 for line in out.splitlines() if "scripts/rollout.py" in line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--ceiling", type=int, default=CEILING)
    parser.add_argument("--poll", type=int, default=60)
    args = parser.parse_args(argv)

    jobs = []
    for line in args.queue.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 4:
            raise SystemExit(f"malformed queue line: {line!r}")
        dataset, task, model, tag = parts[:4]
        k = parts[4] if len(parts) > 4 else "3"
        if model not in PREFIX:
            raise SystemExit(f"unknown model {model!r}")
        if not tag.startswith(f"{PREFIX[model]}-"):
            raise SystemExit(
                f"tag {tag!r} does not open with {PREFIX[model]!r}; nothing "
                f"would read jobs/{dataset}-{task}-{tag}"
            )
        jobs.append((dataset, task, model, tag, k))

    # The key is checked ONCE, here, rather than discovered by eight
    # sweeps in a row. `rollout.py` refuses without it and says so
    # clearly, but a queue swallows that into a per-job log nobody reads
    # until the scores are missing -- and a queue whose whole point is to
    # run unattended is exactly where that costs the most. This runner
    # inherits the environment it was started in, and starting it without
    # sourcing .env is a mistake that has already been made once.
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit(
            "OPENROUTER_API_KEY is not set, so every queued sweep would fail "
            "identically. Start this with the environment loaded"
        )

    print(f"  {len(jobs)} sweep(s) queued, {args.ceiling} at a time")
    started = []
    for dataset, task, model, tag, k in jobs:
        while _running() >= args.ceiling:
            time.sleep(args.poll)
        log = REPO / "jobs" / f"{dataset}-{task}-{tag}.queue.log"
        handle = log.open("w")
        subprocess.Popen(
            [
                str(REPO / ".venv" / "bin" / "python"),
                str(REPO / "scripts" / "rollout.py"),
                "--dataset", dataset, "--task", task,
                "--model", model, "--k", k, "--tag", tag,
            ],
            stdout=handle,
            stderr=subprocess.STDOUT,
            cwd=str(REPO),
            env=dict(os.environ),
        )
        started.append(f"{dataset}/{task} {model} {tag}")
        print(f"  started {started[-1]}", flush=True)
        # Let the gateway bind its ephemeral port before the next one asks
        # for one; two starting together have raced here before.
        time.sleep(30)

    while _running():
        time.sleep(args.poll)
    print(f"  all {len(started)} sweep(s) finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
