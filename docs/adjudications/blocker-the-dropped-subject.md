# Seven rows the gate refused, and the seven defects behind them

`certify` refused `delegation/blocker-register` on five rows that every
trial of every tier declined, and `merrick/blocker-register` on two more
after the first five were fixed. All seven were the key. None was a model
failure.

That is worth stating before the details, because it inverts the instinct:
with the heaviest criterion between 0.4 and 0.85, a row that **nine
independent trials** decline is evidence about the row, not about the
readers. Four of five unanimous disagreements in this tree have been the
key, and this round it was seven of seven.

## The defects

| what the key held | what the passage says | class |
|---|---|---|
| a row from *"so nothing sits **waiting on me**"* | the speaker is what everyone else waits FOR | object, not subject |
| a row from *"I **was** waiting on Klara's comparison"* | the same turn says *"I can confirm staffing today"* | a wait already over |
| no row for *"**Still waiting on Clement.**"* | the subject is dropped, as this firm usually drops it | 34 turns |
| a chain starting six days late | *"**Separately,** still waiting on a name from Elena"* | dropped behind an adverb |
| a chain starting six weeks late | *"sent…, cc'd her and adaora, **waiting on** her numbers"* | dropped across a comma |
| a chain ending four days late | *"the question is … not closed **-** still waiting on written confirmation"* | the subject carried across the dash |
| a count one too high | *"Sandhurst is the one with a live gap: still waiting on officer names"* | the same |

## The two that are worth reading twice

**The subject left out** was the largest and the least visible. The rule
required an explicit `I`, and this firm says *"Still waiting on Clement."*
far more often than *"I am waiting on Clement."* — 34 turns across two
corpora. Measured at the ROW level, which is what is graded, admitting them
left the row SET unchanged (20 → 22 and 16 → 17): what changed was the ends
and the counts of rows that already existed.

**The subject carried across the dash** is the one where the author of the
rule was wrong and the models were right. The row read:

> the Series C disclosure schedule characterization question is partially
> narrowed but not closed **-** still waiting on written confirmation from
> Ulrich-Bergmann's side

Five trials of three tiers put that person's chain ending four days
earlier. The evidence was printed and read, and the verdict was *the key is
right, the models missed a late turn* — a waiver was one command away. The
judge panel, shown the brief and the raw passage and never the code,
returned the opposite: the clause splitter breaks on `" - "` and severs
*still waiting* from its subject. **The question is waiting.**

The tell had been there and was explained away: five independent trials
agreeing on the same different value is not five models making the same
mistake. It is the signal that points at the key.

## What it cost, and what it bought

Nothing was waived here. Every one of the seven was fixed in the rule and
in its independently written checker, the brief now states all of them, and
each task's verifier insists the brief still does — a rule the grader
enforces and the brief withholds is a rule the agent is graded on without
being told.

Every tier scored **higher** afterwards, because the key now agrees with
what the models were already reading:

| | opus | glm | kimi |
|---|---|---|---|
| `delegation/blocker-register` | 0.608 → 0.762 | 0.523 → 0.689 | 0.295 → 0.389 |
| `merrick/blocker-register` | 0.515 → 0.566 | 0.325 → 0.499 | 0.419 → 0.428 |

Both derivations agree on all 4,998 turns of both corpora, and they
disagreed by exactly the disputed turns until each fix reached both.
