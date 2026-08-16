"""Why did a rollout lose points, and was the loss the model's fault?

Run after a Harbor job. For every criterion that scored below one, this
prints what the oracle wanted, what the agent submitted, and — the part
that matters — whether the difference can be explained by something other
than the model getting it wrong.

The standing question for this dataset is not "what did it score" but
"does the score measure the model". Six times in a row the answer was no:
a `tkt-` id the tools never served, a client/internal split decided by a
string prefix, a peer reviewer filed as a client, a schema field set the
grader kept a stale copy of, a row field nothing graded, a subject line
the instruction never disambiguated. Each looked like a capable model
failing until someone read the transcript.

    uv run python scripts/failure_analysis.py jobs/<job-name> [task-dir]
"""

import json
import re
import sys
from pathlib import Path


def _latest(job: Path, *parts: str) -> Path | None:
    hits = sorted(job.glob(str(Path(*parts))), key=lambda p: p.stat().st_mtime)
    return hits[-1] if hits else None


def _submitted(job: Path, field: str) -> dict | None:
    """The agent's own deliverable, recovered from its transcript.

    Harbor does not keep the workspace, so the file itself is gone; the
    agent almost always prints or verifies it, and that is enough.
    """

    log = _latest(job, "*", "agent", "codex.txt")
    if log is None:
        return None
    raw = log.read_text(errors="replace")
    # Codex logs carry JSON inside JSON inside a shell string, so the same
    # object appears at one, two, or three levels of escaping. Try each.
    best: dict | None = None
    for text in (
        raw,
        raw.replace('\\"', '"').replace("\\n", "\n"),
        raw.replace('\\\\\\"', '"').replace('\\"', '"').replace("\\n", "\n"),
    ):
        for match in re.finditer(re.escape(f'"{field}"') + r"\s*:", text):
            start = text.rfind("{", 0, match.start())
            if start < 0:
                continue
            depth, end = 0, None
            for index in range(start, min(len(text), start + 200_000)):
                if text[index] == "{":
                    depth += 1
                elif text[index] == "}":
                    depth -= 1
                    if depth == 0:
                        end = index + 1
                        break
            if end is None:
                continue
            try:
                candidate = json.loads(text[start:end])
            except ValueError:
                continue
            if isinstance(candidate, dict) and field in candidate:
                best = candidate
        if best is not None:
            return best
    return best


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    job = Path(sys.argv[1])
    details = _latest(job, "*", "verifier", "reward-details.json")
    if details is None:
        print(f"no reward-details under {job}")
        return 1
    scored = json.loads(details.read_text())

    task = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    oracle = (
        json.loads((task / "tests/oracle.json").read_text())
        if task and (task / "tests/oracle.json").is_file()
        else {}
    )
    field = "".join(
        line.split("=")[1].strip().strip('"')
        for line in ((task / "task.toml").read_text().splitlines() if task else [])
        if line.startswith("primary_field")
    )
    got = _submitted(job, next(iter(oracle), "")) if oracle else None

    print(f"=== {job.name}")
    losses = []
    for dimension in ("answer", "process"):
        block = scored.get(dimension) or {}
        print(f"  [{dimension}] {block.get('score', 0):.3f}")
        for criterion in block.get("criteria", ()):
            mark = "  " if criterion["value"] >= 1 else "<-"
            print(
                f"    {mark} {criterion['name']:28} {criterion['value']:.3f} "
                f"w={criterion['weight']}"
            )
            if criterion["value"] < 1:
                losses.append(criterion["name"])

    if not losses:
        print("\n  nothing lost — no analysis to do")
        return 0

    print(f"\n=== what was lost, and why ({len(losses)} criteria)")
    if got is None:
        print("  the agent's deliverable could not be recovered from the")
        print("  transcript; read the codex log by hand before concluding")
        print("  anything about the model.")
        return 0

    for key, want in oracle.items():
        if isinstance(want, list):
            continue
        mine = got.get(key)
        if mine != want:
            print(f"  {key}: oracle {want!r} vs submitted {mine!r}")

    # The row table, not merely the first list: an oracle often carries a
    # plain list of ids as well.
    rows_key = next(
        (
            k
            for k, v in oracle.items()
            if isinstance(v, list) and v and isinstance(v[0], dict)
        ),
        None,
    )
    for key, want in oracle.items():
        if (
            isinstance(want, list)
            and key != rows_key
            and not (want and isinstance(want[0], dict))
        ):
            mine = got.get(key)
            if not isinstance(mine, list):
                print(f"  {key}: oracle {len(want)} ids vs submitted {mine!r}")
            elif set(map(str, mine)) != set(map(str, want)):
                missing = sorted(set(map(str, want)) - set(map(str, mine)))
                extra = sorted(set(map(str, mine)) - set(map(str, want)))
                print(f"  {key}: missed {missing[:5]} | invented {extra[:5]}")
    if rows_key and isinstance(got.get(rows_key), list):
        want_rows = oracle[rows_key]
        got_rows = got[rows_key]
        keyfield = next(iter(want_rows[0])) if want_rows else None
        if keyfield:
            want_ids = {str(r.get(keyfield)) for r in want_rows}
            got_ids = {str(r.get(keyfield)) for r in got_rows if isinstance(r, dict)}
            missing, invented = want_ids - got_ids, got_ids - want_ids
            print(f"  {rows_key}: {len(want_rows)} expected, {len(got_rows)} submitted")
            if missing:
                print(f"    missed:   {sorted(missing)[:6]}")
            if invented:
                print(f"    invented: {sorted(invented)[:6]}")
            if invented and not missing:
                print(
                    "    NOTE: extra rows with none missing often means the "
                    "task's population rule is looser than the oracle's — "
                    "check the instruction before blaming the model."
                )
            if missing and not invented:
                print(
                    "    NOTE: missing rows with none invented often means a "
                    "filter the instruction states differently from the "
                    "oracle. Read both."
                )

    print(f"\n  deliverable field: {field or '(unknown)'}")
    print("  Every difference above is a defect until shown otherwise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
