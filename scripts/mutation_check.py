"""Break the code on purpose and confirm the tests notice.

    ./.venv/bin/python scripts/mutation_check.py \
        --source datasets/merrick/build_tasks.py \
        --tests tests/datasets/test_an_empty_oracle_is_refused.py \
        --function _refuse_empty_answer \
        --mutation 'if not rows[0]:' 'if False:' \
        --mutation 'if len(rows) != 1:' 'if False:'

Exits non-zero if any mutation survives, if any anchor is missing, or if
the source does not come back byte-identical. That is the point: a sweep
whose result is a printed table is one a caller can commit alongside
without reading, and this file exists because that happened.

**Three ways a hand-written sweep lies, all met in one day:**

*It dies with the source mutated.* A sweep killed by a timeout mid-run left
`DUMP_CEILING = 0.1` in a file, and the next sweep read that as its
baseline — so its "original" was already broken and its first assertion
failed for a reason unrelated to the code. Restored in `finally`, and the
restore is verified by digest before this exits.

*It mutates the wrong function.* Bare substrings with `replace(..., 1)` hit
the first match in the file, and shared idioms (`result.verdict == "PASS"`,
`min / 10`) usually appear first in a neighbouring function. Three
"survivors" in one sweep were mutations of code the tests never claimed to
cover. `--function` slices the target before mutating inside it.

*It stops early and the caller does not notice.* An anchor that no longer
matches — because a formatter rewrapped the line — raised on mutation three
of four, and the `git commit` chained after it ran anyway, with a message
already claiming four. A missing anchor is now a non-zero exit.

A surviving mutation is not always a bug in the tests: two conditions that
exclude exactly the same inputs are equivalent mutants, and the honest
response is to say so rather than to invent a fixture for a case the system
cannot produce.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


def _slice(text: str, function: str | None) -> tuple[int, int]:
    """The span to mutate inside: one function, or the whole file."""

    if function is None:
        return 0, len(text)
    marker = f"def {function}"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"no `{marker}` in the source")
    # The EARLIEST following top-level definition, not the first keyword
    # that happens to match: returning on `\ndef ` while a `\nclass ` sits
    # closer would hand back a slice covering both, and a mutation aimed at
    # one function would silently land in the other -- which is the whole
    # failure `--function` exists to prevent.
    after = start + len(marker)
    ends = [
        position
        for position in (
            text.find(keyword, after) for keyword in ("\ndef ", "\nclass ", "\n@")
        )
        if position > 0
    ]
    return start, min(ends) if ends else len(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--tests",
        required=True,
        nargs="+",
        help="one or more paths pytest should collect",
    )
    parser.add_argument("--function", default=None)
    parser.add_argument(
        "--mutation",
        nargs=2,
        action="append",
        metavar=("FROM", "TO"),
        required=True,
        help="a literal in the source, and what to replace it with",
    )
    parser.add_argument("--python", default="./.venv/bin/python")
    args = parser.parse_args()

    original = args.source.read_text()
    digest = hashlib.sha256(original.encode()).hexdigest()
    start, end = _slice(original, args.function)
    block = original[start:end]

    missing = [pair for pair in args.mutation if pair[0] not in block]
    survived: list[str] = []
    try:
        for before, after in args.mutation:
            if [before, after] in [list(p) for p in missing]:
                print(f"MISSING  {before[:56]}")
                continue
            mutated = block.replace(before, after, 1)
            args.source.write_text(original[:start] + mutated + original[end:])
            result = subprocess.run(
                [args.python, "-m", "pytest", *args.tests],
                capture_output=True,
                text=True,
            )
            tail = (result.stdout + result.stderr).strip().splitlines()
            note = tail[-1][:38] if tail else ""
            if result.returncode:
                print(f"CAUGHT   {before[:52]:<54}{note}")
            else:
                survived.append(before)
                print(f"SURVIVED {before[:52]:<54}{note}")
    finally:
        # No `return` here: one inside a `finally` swallows whatever
        # exception was on its way out, and this block runs on the paths
        # where something has already gone wrong.
        args.source.write_text(original)
        intact = hashlib.sha256(args.source.read_text().encode()).hexdigest() == digest
        print("source restored and verified" if intact else "SOURCE NOT RESTORED")

    if not intact:  # pragma: no cover - a filesystem failure
        print("the source did not come back — restore it by hand", file=sys.stderr)
        return 2

    if missing:
        print(f"\n{len(missing)} anchor(s) not found in the target", file=sys.stderr)
    if survived:
        print(f"\n{len(survived)} mutation(s) survived", file=sys.stderr)
    return 1 if (missing or survived) else 0


if __name__ == "__main__":
    raise SystemExit(main())
