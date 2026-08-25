# Building tasks that measure a frontier model

A pipeline, and the measurements that shaped it. Every stage here replaced
something that was being done by hand, and every one of them caught a real
defect on its first run — including one that overturned a judgement I had
made myself, and one that refused a task I had already called finished.

The problem it solves is narrow and expensive: **a task can be correct,
verified, reproducible, and measure nothing.** Five registers were built
over one corpus before that was clear. Four score 1.000 for the strongest
tier. Finding out cost four sweeps of nine trials each.

---

## The two laws

Everything below follows from two findings, both measured rather than
reasoned.

### 1. A rule a model can turn into a program scores 1.000

Corpus size does not change it. The ceiling tasks read 195, 280, 530 and
623 items; the one that measures reads 623. Arithmetic does not change it:
a ceiling task resolves three-working-day deadlines with weekend skipping.
On one, the transcript shows the model made 16 tool calls, 34 shell
commands, compiled four regexes and was finished.

### 2. What resists is a **derived grouping key**, and it needs an anchor

The same five-condition attachment rule scores **1.000 on mail** and
**0.766 on meeting transcripts**. The rule is identical; the key is not.

    mail      owner   <- `sender`, a column. Group, take the max, done.
    meetings  owner   <- a column
              meeting <- DERIVED: a title appearing on 3+ days is a
                         standing series. 8 of 52 titles; 44 one-offs make
                         no rows at all.

Row-F1 is sensitive to the row SET. An error in a derived key merges or
drops a *group*, which costs rows. An error in a value costs a field.

**But derivability and gradability pull against each other.** The obvious
next move — derive the owner too, so the register reports what the room
says each *person* owes — surveyed better than the working task on every
number (rows per owner 2.45 against 1.17, repeat 71%) and is ungradable.
255 of its 302 candidates are cases where the named person is a recipient,
an addressee, or the object of a verb:

    "...have a date to Thandiwe by tomorrow"      Thandiwe RECEIVES it
    "Dov, do you want that before Friday?"        a question; Friday
                                                  belongs to a closing

Restrict to an unambiguous anchor — a named person as the subject of a
future verb — and the whole corpus holds **one** instance. People speak in
the first person about their own work.

So: `I'll` is why the commitment rule is gradable. **A key component the
model cannot reliably derive is one the oracle cannot reliably derive
either, and the oracle has to be right.** A derivation with an anchor is
difficulty. A derivation without one is a coin flip that takes three sweeps
to recognise.

---

## The stages

```
WORLD SPEC → RECORD → SURVEY → BUILD → SCREEN → DIAGNOSE → ADJUDICATE → CERTIFY
                         ^                          |
                         +--------- redesign -------+
```

### WORLD SPEC — the corpus is part of the task

A family cannot be ported into a world that was not generated to carry it.
Measured across four recorded worlds, mails carrying `I'll`/`I will`, and
how many of those carry any deadline form:

    merrick   537 owner-mails   179 weekday, 115 this week, 87 tomorrow
    ashgrove  150 owner-mails    85 weekday,  34 EOD
    hartwell  135 owner-mails     3 tomorrow, 2 EOD     <- promises, no dates
    calder     82 owner-mails     0                     <- none at all

Under the real rule hartwell and calder yield **zero** items. That is not a
rule gap to patch; those firms' people do not write dates.

This is steerable. A persona carries `personality`, `role_description` and
`channel_style` (email register, chat register, quirks) as free text into
its prompt, so "people here delegate explicitly, naming who owes what by
when" is a thing a world can be *specified* to produce. The survey below is
how you find out whether it did.

### SURVEY — `scripts/survey_surfaces.py`

Prints, per surface and candidate grouping, the four numbers that decide
whether a task built on it can land in band: whether the grouping is
derived or a column, how much it discards, rows per owner, and the repeat
rate supersession needs.

**Run it with `--rule`, never the regex default.** The proxy reported
merrick's mail-by-subject at 39% repeat, a surface worth building on; under
the real attachment rule the same grouping is 0%. 537 messages carry an
`I'll` somewhere and 61 carry a promise the rule admits. A proxy flatters
every surface where the graded rule is stricter than it, which is all of
them.

Read the numbers this way: rows per owner at 1.00 means the row set is
"enumerate the people" and only the value is ever at stake; a repeat rate
near 0 means a register keyed there has nothing to supersede — and every
row will still look right.

### BUILD — `datasets/<world>/build_tasks.py`

Derives the oracle with the reference solver, re-derives it with an
independent verifier, checks every identifier is reachable through the
tools, and measures the no-comprehension floors.

The two derivations are single-sourced per *route*, not per task:
`promise_rule` walks characters, `promise_rule_check` walks words, and each
is vendored into every task that needs it the way `criteria_base` already
is. Independence has to be at the level of assumptions, not code — an
earlier pair shared nothing textual, encoded the same too-narrow negation
rule, agreed on all 2,872 utterances, and eleven of twenty rows were wrong.

### SCREEN — `scripts/screen.py`

Many tasks in ONE harbor job at k=1 against the strongest tier. The
gateway, image pull and agent install are per-job, so eight tasks cost
about what two cost in eight jobs. A 1.000 here is a design verdict, not a
score. It identified three ceiling tasks in 4 trials where the sweeps had
cost 36.

### DIAGNOSE — `scripts/diagnose.py`

Loss per criterion; rows every trial declined; rows the models produced
that the key has no row for — with the tell that a wrong date appears as
one miss *and* one invention of the same pair.

The signal it exists for: genuine model error is stochastic, so a row that
**every** trial of **every** tier declines is a claim about the key. On
first run against a task already certified in band it found only 5 of 14
rows produced by every trial, and one declined 9 of 9.

### ADJUDICATE — `scripts/adjudicate.py`

The stage that cannot be automated with more code, and the reason is the
point: **the extractor is the thing under test**, so a key derived from it
and checked by a second derivation of it agrees with itself.

So the judge is an agent that never sees the implementation — only the
brief's own words for the rule and the raw passage. Three judges per row; a
**split is a finding, not a tie to break**, because a row its own readers
disagree about cannot separate a good answer from a bad one.

Give it every rule section the value depends on. Given only the commitment
rule it resolved `tomorrow` said on a Friday to the Saturday and reported a
correct row as wrong; the sections now come from the verifier's own `PINNED`
table rather than a default.

It overturned a row I had adjudicated by hand and called sound, quoting the
brief's own counter-example back at me. It was right.

### CERTIFY — `scripts/certify.py`

Five things at once, each of which has been wrong on a task that looked
finished: built by two derivations; floors leaving room; the band on ≥3
tiers from ≥3 graded trials each; no row declined by every trial; and the
sweeps measured against the **current** key.

That last one refused this file's own first run. The task certified
cleanly on three sweeps — every tier in band — and all nine trials predated
the same day's oracle fix. Nothing errors when that happens: the scores are
real, the trials completed, the table prints, and every number in it was
earned against a different answer key. Only a timestamp catches it.

---

## What the loop costs, and what it saves

The register at the centre of this moved 0.508 → 0.789 → 0.838 → 0.766
across five oracle versions **without the model changing**. Every jump was
a correction. Reported at any point along the way, each would have been a
property of my extractor described as a property of opus-5.

The cheap path and the expensive path for the same finding:

| finding | cheap | expensive |
|---|---|---|
| a rule has no anchor | 20 min of corpus measurement | build + screen + a day of adjudication |
| a surface is at ceiling | 1 screening trial | a 9-trial sweep |
| a key row is wrong | 3 judges, minutes | three sweeps and a wrong conclusion |

---

## Status

One task certified-quality on the strongest tier (0.766 ×3 against the
current key), with the other two tiers owed before `certify` will pass it.
Four measured at ceiling and kept as evidence, because what they rule out
is worth more than the tasks would have been.

The constraint on scale is not throughput. It is that exactly one
(surface, rule) combination across four worlds has been shown to measure a
frontier model, and the survey now says why in numbers before a sweep is
spent rather than after four.
