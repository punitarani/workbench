"""Judge an oracle's rows against the source, independently of the rule.

    uv run python scripts/adjudicate.py --dataset merrick \
        --task live-commitment-register --rows disputed.json --out verdicts.json

**The problem this exists for.** A semantic rule has a long tail. The
attachment rule behind `live-commitment-register` was corrected twice --
eleven of twenty rows, then three of sixteen -- and a third sweep still
found rows every trial of every tier declined. Each round the extractor was
a slightly better approximation of a rule the brief states in English, and
each round the tail moved rather than ended.

Patching the extractor again is the wrong move, for a reason worth stating:
**the extractor is the thing under test.** A key derived from it and checked
by a second derivation of it is a key that agrees with itself. What decides
a disputed row is the source text, read by something that has not seen the
pattern.

**So the judge is an agent, and it never sees the rule's implementation.**
It gets the brief's own words for the rule, the raw passage with no pattern
applied, and nothing else. It answers: does this passage admit a row, and
what is the value. Several judges run per row and the verdict is the
majority; a row they split on is not a row anybody should be graded on.

**The evidence has to cover what decides the row, not what produced it.**
A judge shown the passage the key cites can only confirm or deny THAT
passage, and a row can be wrong for a reason no part of it contains. This
was not hypothetical: a row of `live-commitment-register` was adjudicated
here 3-0 ADMIT, the judges quoted the words that carried the commitment,
and they were right about every one of them. The row was wrong anyway --
the same person committed again eleven days later, the rule had failed to
admit that turn, and supersession made the cited passage stale. Nothing
inside it could have said so.

So when the trials answer a key at a DIFFERENT value, that value is the
other half of the evidence, and an item may carry an `alternate` -- the
competing value and the raw passage behind it. The judges then see both
and decide which one the rule leaves standing. `diagnose.py` names these
rows as CONTESTED and `certify.py` refuses to let one be waived on a
verdict that never saw the rival.

**What to do with the verdicts is a build decision, not a grading one.**
A row the judges refuse comes out of the key. A row they split on comes out
too -- an item whose own readers disagree cannot tell a good answer from a
bad one, and leaving it in makes the score a coin flip on that row. This
runs at BUILD time; nothing here is in the grading path, and no agent
judgement ever reaches a trial's score.
"""

import argparse
import json
import subprocess
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Odd, so a majority always exists, and more than one so a single confident
# misreading cannot carry a row on its own.
JUDGES = 3

PROMPT = """\
You are adjudicating one row of an answer key for a reading task, against \
the source it came from.

THE RULE, exactly as the task's own brief states it to the agent being \
tested:
---
{rule}
---

THE PASSAGE. This is the raw source with no pattern applied to it. It is \
everything the speaker said in this context; the row under test claims one \
part of it carries a commitment.
---
{passage}
---

{also}THE ROW the answer key holds:
{row}

Decide, from the passage{passages} and the rule alone:

1. Does the passage admit a row at all under that rule?
2. If it does, is the value the key holds the right one?

You have not been shown the code that produced this row, and you should not \
try to guess it. Read the passage.

Answer with a single JSON object and nothing else:
{{"admits": true|false, "value_correct": true|false|null, \
"reason": "<one sentence, quoting the words that decide it>"}}
"""

# Shown only when the trials answered this key at a different value. The
# judge is told what that value is and given its source, because the rule
# that decides between two commitments cannot be applied to one of them.
ALTERNATE = """\
A SECOND PASSAGE, on the same key. Trials of this task answered {value} \
here instead of what the key holds. This is the raw source behind that \
answer, from the same person and the same series:
---
{passage}
---
Read both. If each carries a commitment, the rule's own section on which \
one is live decides which value belongs in the key.

"""


def pinned_sections(task_dir: Path) -> list[str]:
    """Every brief section the task's own verifier pins as a rule.

    Derived, never hand-kept. The first version of this file took ONE
    section name as a default, and the cost arrived immediately: asked to
    judge a row whose value depends on `## Turning what was said into a
    date`, the judges never saw that section, resolved `tomorrow` to the
    calendar day rather than the next working day, and reported a correct
    key row as a wrong value. A judge deciding a value needs every section
    the value rests on, and the verifier's own `PINNED` table is the list
    of what the task treats as a rule.
    """

    verifier = task_dir / "checks" / "verify.py"
    if not verifier.is_file():
        return []
    import ast

    for node in ast.walk(ast.parse(verifier.read_text())):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        targets = (
            [node.target] if isinstance(node, ast.AnnAssign) else list(node.targets)
        )
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "PINNED":
                try:
                    return list(ast.literal_eval(node.value))
                except ValueError:
                    return []
    return []


def section(brief: str, heading: str) -> str:
    if heading not in brief:
        raise SystemExit(
            f"the brief has no section {heading!r}. The judge must be given the "
            "rule the agent is given, not a paraphrase."
        )
    start = brief.index(heading)
    end = brief.find("\n## ", start + 1)
    return brief[start : end if end > 0 else len(brief)]


def judge(
    rule: str, passage: str, row: str, model: str, alternate: dict | None = None
) -> dict | None:
    """One judgement, from a fresh reader with no state."""

    also = (
        ALTERNATE.format(value=alternate["value"], passage=alternate["passage"].strip())
        if alternate
        else ""
    )
    prompt = PROMPT.format(
        rule=rule.strip(),
        passage=passage.strip(),
        row=row,
        also=also,
        passages=", the second passage" if alternate else "",
    )
    try:
        done = subprocess.run(
            ["claude", "-p", prompt, "--model", model],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    text = (done.stdout or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {"error": "no JSON in the reply", "raw": text[:200]}
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return {"error": "unparseable JSON", "raw": text[start : end + 1][:200]}


def verdict(votes: list[dict]) -> dict:
    """Majority, and an explicit `split` when the readers do not agree.

    A split is not a tie to be broken. It is the finding: a row its own
    readers cannot agree on is one no answer can be scored against.
    """

    good = [v for v in votes if "error" not in v]
    if len(good) < 2:
        return {"verdict": "unjudged", "votes": votes}
    admits = [bool(v.get("admits")) for v in good]
    yes = sum(admits)
    if yes and yes != len(admits):
        return {"verdict": "split", "admits_yes": yes, "of": len(admits), "votes": good}
    if not yes:
        return {"verdict": "refuse", "votes": good}
    correct = [
        v.get("value_correct") for v in good if v.get("value_correct") is not None
    ]
    if correct and not all(correct):
        return {"verdict": "wrong-value", "votes": good}
    return {"verdict": "admit", "votes": good}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--rows",
        required=True,
        type=Path,
        help='JSON list of {"row": <label>, "passage": <raw source>}',
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--rule-section",
        action="append",
        default=[],
        help="override the sections; by default every section the task's own "
        "verifier pins as a rule is used",
    )
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--judges", type=int, default=JUDGES)
    args = parser.parse_args(argv)

    task_dir = REPO / "datasets" / args.dataset / "tasks" / args.task
    brief = (task_dir / "instruction.md").read_text(encoding="utf-8")
    sections = args.rule_section or pinned_sections(task_dir)
    if not sections:
        raise SystemExit(
            f"{args.task}: no rule sections found. The judge decides a value, "
            "so it needs every section the value depends on."
        )
    rule = "\n\n".join(section(brief, heading) for heading in sections)
    print(f"  rule sections given to the judges: {sections}")

    items = json.loads(args.rows.read_text())
    print(f"  adjudicating {len(items)} row(s), {args.judges} judges each\n")
    results = []
    for item in items:
        votes = [
            judge(
                rule,
                item["passage"],
                item["row"],
                args.model,
                item.get("alternate"),
            )
            for _ in range(args.judges)
        ]
        outcome = verdict(votes)
        results.append({"row": item["row"], **outcome})
        reasons = [
            v.get("reason", "") for v in outcome.get("votes", []) if isinstance(v, dict)
        ]
        print(f"  {outcome['verdict'].upper():12s} {item['row']}")
        for reason in reasons[:1]:
            print(
                textwrap.fill(
                    reason, 92, initial_indent="      ", subsequent_indent="      "
                )
            )
        print()

    if args.out:
        args.out.write_text(json.dumps(results, indent=2) + "\n")
        print(f"  wrote {args.out}")
    counts: dict[str, int] = {}
    for item in results:
        counts[item["verdict"]] = counts.get(item["verdict"], 0) + 1
    print(f"\n  {counts}")
    print(
        "\n  `refuse` and `wrong-value` are rows to take out of the key or "
        "re-derive.\n  `split` is a row to take out whatever its value: its own "
        "readers disagree,\n  so no answer can be scored against it."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
