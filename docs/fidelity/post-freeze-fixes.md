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

## 3. Markdown is still an available format in a firm that should not write it

Three of 82 documents are markdown, filed as `.md`. The stated goal for this
environment was few or none, and the mix floor tolerates 15% so nothing
objects at 3.7%.

They are not markdown because a template chose it — each is a document whose
author picked `markdown` and gave a path with no suffix. As long as the
format is offered, some authors will take it.

For an institution that produces Word, Excel, PowerPoint and PDF, the format
should not be on the menu at all. That is a change to the intent schema in
`core` rather than to a prompt, which is why it waits: `core` is inside the
recorder's import closure.

## How to verify each fix afterwards

Re-record a short window and check:

1. `analysis.calendar_units.inspect(...)` reports zero suspects.
2. Slide decks appear for the presentation matters — the floor to argue about
   is a rate, not presence.
3. `analysis.artifact_mix.measure(...)` reports zero markdown.

None of these needs the full 130 days; a five-day run exercises all three.
