# Engine defects found during the recording, to fix after it lands

The simulation is frozen while a 130-workday world records: changing what
gets written mid-run makes the first half and the second half two different
worlds, and nothing reports it. Each of these was found with the recording
live, verified against the world, and left alone deliberately.

Ordered by what they cost.

## 1. A scheduled start is never checked against the run's clock

`src/simulation/gm/grounded.py`, `_ground_calendar` — the referee validates
only that the event ends after it starts:

```python
if intent.schedule.end <= intent.schedule.start:
    raise IntentRejection(...)
```

Nothing checks that `start` is seconds-from-epoch. An author writing a
wall-clock time (`31500` for 08:45) or an absolute Unix timestamp passes
straight through, because both are integers larger than the one before them.

**Measured: 64 of 787 starts, 8.1%** — 41 scheduled into the past, 23 beyond
any horizon the run could reach. Those events caused **96% of every
scheduling conflict in the world** and killed a task built on that signal.

**And the rate is rising, steeply.** The same measurement over time:

| recorded day | malformed starts | share |
|---|---|---|
| 22 | 64 of 787 | 8.1% |
| 35 | 127 of 850 | 14.9% |
| 109 | **464 of 1,187** | **39.1%** |

Nearly two calendar events in five. The malformed ones accumulate far faster
than the sound ones, so any single day's figure understates the finished
world badly — this note itself said "8% or 15%" while the true figure was
heading for forty.

**This is also the clearest argument for how the gate was re-aimed.** The
first version refused any world above a 2% raw rate. At 39% it would have
refused the build outright, with no remedy available: the writer is frozen,
the rate only grows, and the only move left would have been deleting a gate
under time pressure. The version that refuses on *survivors into the served
state* passes cleanly — the projection quarantines all 464 — while the rate
stays loud and recorded. A gate aimed at what reaches a score survives a
defect getting worse; a gate aimed at the generator does not.

The fix belongs beside the existing check and should reject rather than
repair, with the reason in the rejection so the persona can rewrite it:
compare `start` against the event's own recorded time, and against a
horizon. `core.simtime.misread_unit(start, recorded_at)` already states the
rule; the referee is the reader that is missing.

Downstream mitigation is in place — the calendar projection quarantines them
and the build refuses a world above 2% — so this is a fidelity fix, not a
correctness emergency.

## 2. Occasions to present almost never produce a deck

The workplace schedules two recurring external presentation slots, and
several matters say outright that a deck is the deliverable:

> *"...expects the deck rather than a memo."*
> *"...the deck is the deliverable, not a letter."*

**Measured over 25 workdays: 72 such occasions, 148 meetings convened, and
one slide deck** — 1 of 82 documents. Personas write a memo or a workbook
instead, including for the matters whose brief names a deck.

This is why `MixFloors.required_forms` was written as aspirational: no world
had ever emitted one. This world finally does, exactly once, which satisfies
a presence floor and does not make the file room look like a firm that
presents to clients.

The lever that failed is worth naming precisely: **scheduling an occasion
does not create a deliverable.** The occasion is in the calendar and the
expectation is in the matter description, and neither reaches the persona at
the moment it chooses a format. The fix is in the deliverable turn — when
the day's context includes a presentation the persona attends, `slides`
should be the offered default rather than one option among four.

## 3. The format guard's escape hatch accepts empty documents

Three of 84 documents have **no content at all**, registered under full
professional titles — a management-incentive-plan memo, an OEM licence
status, a counterclaim strategy. They materialize as empty `.md` files.

The markdown set and the empty set are the same three documents, 3 of 3, and
the mechanism explains why. `_reject_unless_parsable` in
`src/simulation/gm/grounded.py` validates a document's content against its
declared format:

```python
parser = _PARSERS.get(content_format)
if parser is None:
    return                      # markdown has no parser
```

Spreadsheets, formatted documents and decks must parse as structured JSON.
**Markdown has no parser, so it accepts anything, including nothing.** And
the rejection the guard raises for the others says:

> *"...send the structured JSON for that format, or declare markdown and
> write prose"*

So the guard's own error message routes a failing author into the single
format the guard does not check, and an author who could not produce
structured content is not well placed to produce prose either. The result is
a document that exists, is registered, has a title and an author and a
matter, and is empty.

Two things to fix, and the order matters:

**Require content.** Whatever the format, a document with empty content
should be rejected. This is the cheap half and it stops the bad artifact
reaching the file room.

**Stop advertising the unvalidated path.** The suggestion should be to
retry in the declared format, not to fall back to the one with no
validation. For an institution producing Word, Excel, PowerPoint and PDF,
markdown arguably should not be offered at all — but removing it while it is
the advertised escape hatch would turn these three documents into three
rejections, not three real documents, so the content check comes first.

Earlier notes here described this as "authors choosing markdown". That was
wrong: nobody chose it, they were sent there.

## 4. Every explicit date in a document body predates the world

341 ISO dates across document bodies, spread over 2018–2025, and **none in
2026** — the year the world runs in. 214 are in 2025 alone.

This does not reach the graded surfaces, which is why it is fourth rather
than first. Mail carries **zero** ISO dates across 481 messages, chat one
across 697, and the single date in a time-entry note is correctly 2026.
Messages express time the way people do — `EOD`, `by Friday`, `end of week`
— which is also why a task needing `<Month> <day>` dates in mail found none
and retired.

It is still a fidelity defect: an agent reading the firm's work product sees
a document dated 2025 filed against a 2026 matter. The document-writing turn
does not carry the world's current date into the content it asks for, while
the message-writing turn never needs one because it writes relatively.

## 5. Internal identifiers leak into work product

Thirteen of 79 materialized files carry database ids in their prose --
`tkt-000010`, `doc-000042` -- inside documents a client could be shown. The
firm's staff would write "the Northmoor closing checklist", not a row key.

It is cosmetic against the graded surfaces and it is not cosmetic to the
fiction. It also has a second cost worth noting: those ids are the internal
vocabulary, and a task keyed on something an agent can actually spell had to
be fixed for exactly this confusion — an oracle named `doc-000012`, which no
tool emits, while the tools serve `LEGAL!12.3`. Prose that shows the
internal form teaches an agent to use it.

The persona's authoring turn is given documents by reference and repeats the
reference. It should be given the name.

## How to verify each fix afterwards

Re-record a short window and check:

1. `analysis.calendar_units.inspect(...)` reports zero suspects.
2. Slide decks appear for the presentation matters — the floor to argue about
   is a rate, not presence.
3. No document has empty content, and `analysis.artifact_mix.measure(...)`
   reports zero markdown as a consequence rather than as a separate rule.
4. Dates written into document bodies fall inside the world's window.
5. No materialized file contains an internal id -- grep the workspace for
   the id prefixes.

None of these needs the full 130 days; a five-day run exercises all three.
