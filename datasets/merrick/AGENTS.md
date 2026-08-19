# merrick

Root rules in [`AGENTS.md`](../../AGENTS.md) apply, and the method in
[`docs/METHOD.md`](../../docs/METHOD.md) governs anything cut from this
world. Firm-specific:

## What this world is for

A law firm, recorded over six months, because two of its structures are
ones the accounting worlds in this tree do not have.

**Deadlines are set by somebody else.** A court moves a scheduling order
and the firm rearranges around it. "What the deadline is now" is
therefore a *recorded* fact with a history, not a value derived from a
rule — and a fact the world records explicitly is the only kind a task
may grade.

**Work product becomes final by leaving the firm.** A brief that is
filed, an agreement executed, an opinion issued. That is what makes the
document formats load-bearing rather than decorative, and it is why this
dataset's file-room gate requires issued PDFs and decks rather than
merely permitting them.

## Pipeline order

| step | command | what it must not skip |
|---|---|---|
| record | `run_epoch.py start --days 180 --mode record` | loud failure; every day checkpoints, so a kill resumes |
| build | `build_tasks.py` | coherence **before** materialization; wholesale rebuild; the file-room gate |
| measure | `scripts/band.py --dataset merrick` | never averages a DNF as a zero |

## Encoded invariants

* **The bundle is rebuilt wholesale.** `materialize` writes files and
  never removes them, so an incremental rebuild accumulates several
  worlds in one directory. Invisible until a task grades those files.
* **The file room is gated, not hoped for.** Format mix is an emergent
  property of a generated world: one recorded world produced no
  documents, decks or PDFs at all despite an authoring prompt that asked
  for the real form every time. `FILE_ROOM` fails a build that is mostly
  notes, that is missing a form this firm really produces, or that holds
  a single raw-text fallback — a file claiming a form it does not have.
* **Rates are cents per hour, and two people are not billed at all.**
  The docket clerk and the billing manager are staff. A firm-wide
  realization figure that silently includes them is a different number
  than the one the partners read, so any task touching utilisation must
  say which population it means.
* **Category is a field, not a prefix.** Opposing counsel, courts and
  vendors are not clients, and the directory records which is which. A
  report keyed on that field is only right if the field is.
* **Artifact conventions are per-persona and opt-in.** The shared
  authoring prompt describes form in the abstract; which artifact is a
  workbook and which is an issued PDF is a fact about a profession. The
  field renders nothing when unset, which is what keeps every other
  world's recorded cassettes byte-identical.

## Before cutting a task from this world

Read [`docs/METHOD.md`](../../docs/METHOD.md) §4 and the
`authoring-graded-tasks` skill. The two failures this tree pays for most
often, in order:

1. An instruction whose prose describes a concept and whose test is a
   string match. Say which kind of rule it is, in the instruction.
2. A rule whose vocabulary was guessed rather than counted. Count how
   this corpus actually writes the thing before fixing the wording — it
   costs one query, and getting it wrong once admitted 1 of 35 real
   instances and scored the other 34 as hallucinations.
