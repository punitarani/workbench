"""Cut an existing task from one recorded world into another.

    uv run python scripts/port_task.py --task live-commitment-register \
        --from merrick --to delegation

The two worlds here are the same fictional firm recorded twice, with one
change to the spec. They share all 31 people, every meeting title and both
rule modules, and the ONLY thing a task's brief says about its world is the
four generated literals -- the two boundary dates, the working-day count
and the meeting count. Everything else transfers unchanged.

So a family that works on one world is a task on the other for the cost of
recomputing four numbers, and doing that by hand is how a brief comes to
state one window while its solver reads another.

**What this does NOT decide** is whether the result is worth shipping. The
corpora differ in density -- one world was re-recorded precisely because
the assignment family needed 122 assignments where the other had 16 -- so
a family can transfer cleanly and still land at ceiling or at zero. Build
it, read the floors, re-measure the key against saved deliverables, and
believe the numbers rather than the port.

It refuses rather than guessing when:

  * the target already holds a task by that name;
  * anything outside the four literals differs between the briefs, which
    would mean the port is not the mechanical one this assumes;
  * the source names its own world anywhere in the code or the brief.
"""

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from window_variant import _facts, _stamp, _world  # noqa: E402

_PARTS = (
    ".gitignore",
    "instruction.md",
    "task.toml",
    "solution/solve.py",
    "checks/verify.py",
    "tests/criteria.py",
)


def _install(staged: Path, target: Path) -> None:
    """Swap the staged port into place, having passed every check.

    Anything the target held that this script does not write -- a built
    oracle, its `oracle.world` stamp, the generated grading files -- is
    carried across rather than lost, because a port replaces the task's
    SOURCES and the build regenerates the rest.
    """

    if target.exists():
        for existing in target.rglob("*"):
            if not existing.is_file():
                continue
            relative = existing.relative_to(target)
            if not (staged / relative).exists():
                (staged / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(existing, staged / relative)
        shutil.rmtree(target)
    staged.rename(target)


def _last_day(state: Path) -> int:
    """The last day of the target world's recording, from the world."""

    connection = sqlite3.connect(f"file:{state / 'meetings.db'}?mode=ro", uri=True)
    latest = connection.execute("SELECT MAX(started) FROM meetings").fetchone()[0]
    connection.close()
    return int(latest) // 86_400


def _port(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--from", dest="source", required=True)
    parser.add_argument("--to", dest="target", required=True)
    parser.add_argument(
        "--force", action="store_true", help="replace an existing target task"
    )
    args = parser.parse_args(argv)

    source = REPO / "datasets" / args.source / "tasks" / args.task
    target = REPO / "datasets" / args.target / "tasks" / args.task
    if not source.is_dir():
        raise SystemExit(f"no such task: {source}")
    if target.exists() and not args.force:
        raise SystemExit(f"{target} already exists; pass --force to replace it")

    # Built beside the target and moved into place only once every check
    # has passed, because this script REFUSES in six places and a refusal
    # used to leave the target half-ported.
    #
    # That is not hypothetical and it was not cheap: adding the duration
    # check below, and testing it by porting a task that would trip it,
    # deleted a CERTIFIED task's oracle and overwrote its solver, brief,
    # criteria and grading files with the other world's. `git checkout`
    # brought it back because it was committed. Nothing in the script would
    # have.
    #
    # A tool whose failure path destroys what it was asked not to touch is
    # more dangerous than the mistake it exists to catch.
    finished = target.with_name(target.name + ".porting")
    if finished.exists():
        shutil.rmtree(finished)
    real_target, target = target, finished

    for part in _PARTS:
        if (source / part).is_file():
            (target / part).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source / part, target / part)

    # A task that names its own world does not port mechanically, and the
    # failure would be a brief describing one firm's record while served
    # from another's.
    # The hazard is a RUNTIME reference into the source world -- a path
    # under `datasets/<world>/` or `out/<world>/`, or an import of a module
    # that only exists there. A task served from one world while reading
    # another's files would grade against the wrong record and say nothing
    # about it.
    #
    # Searching for the bare world name instead finds only false alarms,
    # and that was the first version of this check: the firm in both worlds
    # is "Merrick Stanton LLP", so every brief names it; the shared
    # `.gitignore` names it in a note about an accidental commit; and the
    # solver names it a dozen times in comments recording which corpus a
    # lesson came from. Not one of those is a task saying something true of
    # one world and false of the other.
    _INTO_THE_SOURCE = re.compile(
        rf"(?:datasets|out|jobs)/{re.escape(args.source)}\b"
        rf"|\bfrom\s+{re.escape(args.source)}\b"
        rf"|\bimport\s+{re.escape(args.source)}\b"
    )
    # Python is read as a TREE, not as lines. Stripping `#` comments is not
    # enough -- the solver carries a «MEASURE:» note inside a docstring
    # naming `datasets/merrick/measure_transcripts.py`, which is a pointer
    # to a measurement script and not something this task runs. A
    # line-based check called that a runtime read.
    import ast

    def _docstrings(tree: ast.AST) -> set[int]:
        seen = set()
        for node in ast.walk(tree):
            if not isinstance(
                node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ):
                continue
            first = next(iter(getattr(node, "body", [])), None)
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                seen.add(id(first.value))
        return seen

    for part in ("solution/solve.py", "checks/verify.py", "tests/criteria.py"):
        p = target / part
        if not p.is_file():
            continue
        tree = ast.parse(p.read_text())
        docs = _docstrings(tree)
        for node in ast.walk(tree):
            named = None
            if isinstance(node, ast.Import):
                named = " ".join(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                named = node.module or ""
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
            ):
                named = node.value
            if named and (
                _INTO_THE_SOURCE.search(named) or named.strip() == args.source
            ):
                raise SystemExit(
                    f"{part}:{getattr(node, 'lineno', '?')} reads out of "
                    f"{args.source!r} at runtime: {named[:70]!r}. Port by hand"
                )

    # A duration claimed in PROSE. The script recomputes every number it
    # knows the name of -- window constants, the brief's four literals, the
    # verifier's dates -- and copies the manifest description verbatim,
    # because nothing derives a sentence.
    #
    # Three manifests reached this world describing "six months" of standing
    # meetings, which is the SOURCE world's recording. This one holds 135
    # days. Two were ported by hand before this script existed and one by
    # this script, and all three had correct constants throughout.
    #
    # So the durations are checked against the target world and the port
    # refuses rather than rewriting: "four and a half months" is a phrasing
    # decision, and a script that guesses at prose will get it wrong in a
    # way nobody re-reads.
    _MONTHS = {
        "two months": 2, "three months": 3, "four months": 4,
        "four and a half months": 4.5, "five months": 5, "six months": 6,
        "half a year": 6, "a year": 12,
    }
    target_state = _world(args.target)
    connection = sqlite3.connect(
        f"file:{target_state / 'meetings.db'}?mode=ro", uri=True
    )
    span = [s for (s,) in connection.execute("SELECT started FROM meetings")]
    connection.close()
    months = ((max(span) - min(span)) / 86_400 + 1) / 30.44
    described = (target / "task.toml").read_text()
    for phrase, claimed in _MONTHS.items():
        if phrase in described and abs(claimed - months) > 0.75:
            raise SystemExit(
                f"the manifest describes {phrase!r} and {args.target} records "
                f"{months:.1f} months. The window constants port and the prose "
                "does not; rewrite the description by hand, then re-run"
            )

    state = _world(args.target)
    last = _last_day(state)
    solver = target / "solution" / "solve.py"
    text = solver.read_text()

    # A third window form, and it ports differently from the other two.
    #
    # Most tasks here name a LAST DAY, which is a property of how long the
    # world was recorded and has to move. `mail-promise-register` names a
    # DURATION -- `WINDOW_DAYS = 61` from the epoch -- which is a property
    # of the task and does not. Nothing in the solver, the verifier or the
    # brief changes, and rewriting any of them would move a window the
    # task never asked to move.
    #
    # That is only true while the two worlds share an epoch, which they do
    # -- both open 2026-01-05T00:00:00-05:00 -- and which is checked here
    # rather than assumed. If they ever diverge, a duration window lands on
    # different calendar dates in each world and the brief's stated dates
    # become wrong silently, in a task whose whole content is dates.
    if re.search(r"^\s*WINDOW_DAYS\s*[:=]", text, re.M) and not re.search(
        r"^\s*WINDOW_LAST_DAY\s*=", text, re.M
    ):
        epochs = {}
        for world in (args.source, args.target):
            connection = sqlite3.connect(
                f"file:{_world(world) / 'meetings.db'}?mode=ro", uri=True
            )
            epochs[world] = dict(
                connection.execute("SELECT key, value FROM meta")
            )["epoch"]
            connection.close()
        if epochs[args.source] != epochs[args.target]:
            raise SystemExit(
                f"this task states its window as a DURATION, and the two "
                f"worlds open on different days ({epochs[args.source]} vs "
                f"{epochs[args.target]}). The same 61 days would be different "
                "calendar dates in each; port it by hand"
            )
        manifest = target / "task.toml"
        manifest.write_text(
            manifest.read_text().replace(
                f"workbench/{args.source}-{args.task}",
                f"workbench/{args.target}-{args.task}",
            )
        )
        _install(target, real_target)
        target = real_target
        print(f"  {target.relative_to(REPO)}")
        print(f"    window: a duration ({epochs[args.target][:10]} + N days),")
        print("    identical in both worlds; nothing rewritten but the task id")
        print("    now build it, read the floors, and re-measure the key")
        return 0

    opens = re.search(r"^\s*WINDOW_FIRST_DAY\s*=\s*(\d+)", text, re.M)
    facts = _facts(state, int(opens.group(1)) if opens else 0, last)
    text, moved = re.subn(
        r"^(\s*WINDOW_LAST_DAY\s*=\s*)\d+", rf"\g<1>{last}", text, flags=re.M
    )
    if not moved:
        raise SystemExit("the solver states no WINDOW_LAST_DAY to move")
    solver.write_text(text)

    checker = target / "checks" / "verify.py"
    text = checker.read_text()
    text, by_offset = re.subn(
        r"^(\s*_?WINDOW_LAST_DAY\s*=\s*)\d+", rf"\g<1>{last}", text, flags=re.M
    )
    text, by_date = re.subn(
        r'^(WINDOW_LAST_DATE\s*=\s*")\d{4}-\d{2}-\d{2}(")',
        rf'\g<1>{facts["last"].isoformat()}\g<2>',
        text,
        flags=re.M,
    )
    text = re.sub(
        r'^(WINDOW_FIRST_DATE\s*=\s*")\d{4}-\d{2}-\d{2}(")',
        rf'\g<1>{facts["first"].isoformat()}\g<2>',
        text,
        flags=re.M,
    )
    if not (by_offset or by_date):
        raise SystemExit(
            "the verifier states its window in neither form this knows; teach "
            "it the third rather than shipping two derivations that read "
            "different windows"
        )
    checker.write_text(text)

    brief = target / "instruction.md"
    text = brief.read_text()
    literals = re.findall(r"\*{4}([^*]+)\*{4}", text)
    if len(literals) < 4:
        raise SystemExit(f"expected 4 generated literals, found {len(literals)}")
    for old, new in zip(
        literals[:4],
        (
            _stamp(facts["first"]),
            _stamp(facts["last"]),
            str(facts["working_days"]),
            str(facts["meetings"]),
        ),
    ):
        text = text.replace(f"****{old}****", f"****{new}****", 1)

    # The sentence has to agree with the number this script just wrote.
    #
    # `_facts` counts every meeting in the window. The source world's brief
    # states its STANDING meetings there instead -- 520 where its window
    # holds 567 -- and its sentence ends "standing meetings" accordingly.
    # Porting copies the sentence and replaces the number, which produced a
    # brief reading "403 standing meetings" where 403 is the window total
    # and the standing count is 383.
    #
    # Wrong in the direction that matters, too: the standing count is what
    # the register asks the reader to report, so a brief stating it hands
    # over a graded scalar, and one stating the total does not.
    standing = "meetings, of which the standing ones are yours to identify."
    text = re.sub(r"\bstanding meetings\.", standing, text, count=1)
    brief.write_text(text)

    manifest = target / "task.toml"
    text = manifest.read_text().replace(
        f"workbench/{args.source}-{args.task}", f"workbench/{args.target}-{args.task}"
    )
    manifest.write_text(text)

    # Re-pin the digests, having first proved the section moved by the
    # LITERALS alone. Pasting a new digest in to silence the pin is what
    # the pin exists to catch, so this reconstructs the source section from
    # the ported one by putting the old numbers back, and refuses if the
    # two do not then match.
    sys.path.insert(0, str(REPO / "datasets" / args.target))
    from brief_pins import digest  # noqa: E402

    was_text = (source / "instruction.md").read_text()
    now_text = brief.read_text()
    checker_text = checker.read_text()
    for heading in re.findall(r'"(## [^"]+)": "[0-9a-f]{16}"', checker_text):

        def cut(whole: str) -> str:
            start = whole.index(heading)
            end = whole.find("\n## ", start + 1)
            return whole[start : end if end > 0 else len(whole)]

        was, now = cut(was_text), cut(now_text)
        undone = now
        for old, new in zip(
            (
                _stamp(facts["first"]),
                _stamp(facts["last"]),
                str(facts["working_days"]),
                str(facts["meetings"]),
            ),
            literals[:4],
        ):
            undone = undone.replace(f"****{old}****", f"****{new}****", 1)
        if undone != was:
            raise SystemExit(
                f"{heading} differs from the source by more than the four "
                "generated literals; read it and port by hand"
            )
        checker_text = re.sub(
            rf'("{re.escape(heading)}": ")[0-9a-f]{{16}}(")',
            rf"\g<1>{digest(now_text, heading)}\g<2>",
            checker_text,
        )
    checker.write_text(checker_text)

    _install(target, real_target)
    target = real_target
    print(f"  {target.relative_to(REPO)}")
    print(f"    window: day 0..{last}  ->  {facts['first']} .. {facts['last']}")
    print(f"    {facts['working_days']} working days, {facts['meetings']} meetings")
    print("    now build it, read the floors, and re-measure the key")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the port, and leave no staging directory behind either way.

    `_port` refuses in six places. Each refusal is correct and each one
    used to leave a `<task>.porting` directory sitting in the tasks folder,
    where `build_tasks` iterates every directory that does not start with
    an underscore -- so a refused port became a task the next build tried
    to build.
    """

    try:
        return _port(argv)
    finally:
        for staged in (REPO / "datasets").glob("*/tasks/*.porting"):
            shutil.rmtree(staged, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
