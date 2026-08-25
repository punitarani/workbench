"""Find alternatives in a rule's patterns that can never fire.

    uv run python scripts/dead_conditions.py --dataset merrick

**Why this exists.** `_NEG` listed `n't` for months and matched no
contraction anybody has ever typed: written `\\bn't\\b`, it needs a word
boundary before the `n`, and in "doesn't" there is none. The brief promised
the condition and the rule could never apply it. Four rows were dates the
speaker was ruling OUT, and it took an outside reader, asked about an
unrelated row, to notice.

Nothing about a dead alternative is visible in review. It reads correctly,
it is spelled correctly, the tests pass, and the two independent
derivations agreed with each other because they shared the assumption
rather than the code.

**So it is found by mutation, not by reading.** Delete one alternative
from a pattern, run the rule over the whole corpus again, and count. If
the number of matches does not move, that alternative decided nothing --
either it is unreachable, or the corpus never exercises it. Both are worth
knowing: the first is a defect, the second is a rule condition the task
cannot be grading, and a reader of the brief cannot tell them apart.
"""

import argparse
import ast
import importlib.util
import re
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Where a dataset's prose lives. A pattern is dead against A CORPUS, never
# in the abstract, so the corpus is named in the report.
CORPORA: tuple[tuple[str, str, str, str], ...] = (
    (
        "meetings",
        "live-commitment-register",
        "meetings.db",
        "SELECT text FROM utterances",
    ),
    ("mail", "mail-promise-register", "gmail.db", "SELECT body FROM messages"),
)

# Alternations inside a non-capturing group: the shape every rule constant
# here uses. Nested groups are left alone rather than guessed at.
_GROUP = re.compile(r"\(\?:([^()]*)\)")


def alternatives(pattern: str) -> list[tuple[str, str]]:
    """Each removable alternative, with the pattern that drops it."""

    out: list[tuple[str, str]] = []
    for group in _GROUP.finditer(pattern):
        parts = group.group(1).split("|")
        if len(parts) < 2:
            continue
        for index, part in enumerate(parts):
            if not part:
                continue
            kept = "|".join(parts[:index] + parts[index + 1 :])
            without = pattern[: group.start(1)] + kept + pattern[group.end(1) :]
            out.append((part, without))
    return out


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def constants(path: Path) -> list[str]:
    """Module-level names bound to a `re.compile(...)`."""

    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Assign):
            continue
        call = node.value
        if not (
            isinstance(call, ast.Call) and getattr(call.func, "attr", "") == "compile"
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                found.append(target.id)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--module", default="promise_rule.py")
    args = parser.parse_args(argv)

    path = REPO / "datasets" / args.dataset / args.module
    module = load(path)

    texts: list[str] = []
    for _label, task, database, query in CORPORA:
        state = (
            REPO
            / "datasets"
            / args.dataset
            / "tasks"
            / task
            / "environment"
            / ".workbench"
            / "state"
            / database
        )
        if not state.is_file():
            continue
        connection = sqlite3.connect(f"file:{state}?mode=ro", uri=True)
        texts += [row[0] or "" for row in connection.execute(query)]
    if not texts:
        raise SystemExit("no corpus found; build the tasks first")
    print(f"  {len(texts)} items of prose\n")

    # The verdict is the RULE's output, not the pattern's own match count.
    # Counting matches was the first version of this and it failed in the
    # way the whole file is about: `_ALTERNATIVE_AFTER` is anchored with
    # `^` and applied to a substring, so scanning whole turns with it finds
    # nothing whatever you delete, and all sixteen of its alternatives
    # reported dead. A test whose result cannot depend on what it is
    # testing returns the same answer for healthy code.
    def verdict() -> tuple[int, tuple]:
        found = tuple(module.commitment_in(text) for text in texts)
        return sum(1 for token in found if token), found

    base_count, base_found = verdict()
    print(f"  the rule admits {base_count} commitments across that prose\n")

    dead: list[str] = []
    for name in constants(path):
        pattern = getattr(module, name, None)
        if not isinstance(pattern, re.Pattern):
            continue
        for alternative, without in alternatives(pattern.pattern):
            try:
                trimmed = re.compile(without, pattern.flags)
            except re.error:
                continue
            setattr(module, name, trimmed)
            try:
                _after_count, after_found = verdict()
            finally:
                setattr(module, name, pattern)
            if after_found == base_found:
                dead.append(f"{name}: {alternative!r}")
                print(
                    f"  DEAD  {name:20s} {alternative!r:24s} the rule's verdict "
                    f"on all {len(texts)} items is unchanged"
                )
    if not dead:
        print("  every alternative in every pattern decides at least one match")
    else:
        print(
            f"\n  {len(dead)} alternative(s) decide nothing. Unreachable is a defect;\n"
            "  merely unexercised is a rule condition the task cannot be grading,\n"
            "  and the brief promises both the same way."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
