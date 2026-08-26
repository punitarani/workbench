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

    world     mails   `I'll`   +a deadline form   the rule admits
    hartwell   1220      135                  5                 0
    ashgrove    354      150                100                24
    merrick    1399      537                272                58
    calder     3048    1 479              1 158               392

**This table was wrong about calder for weeks, and the error ran the
argument backwards.** It recorded "82 owner-mails, zero carrying any
deadline form ... none at all", and calder is in fact the densest world of
the four: 1,479 mails carry a first-person promise and the rule admits 392
of them. Textbook ones -- *"I'll have the full workpaper breakdown with
line-item detail on your desk by Friday morning"*. Only hartwell yields
zero, and hartwell's figures were right all along.

What that costs is the cross-world correlation this section used to lean
on. calder's personas mention deadlines **zero** times and its corpus
carries 392 commitments; merrick's mention them eight times and it carries
58. The persona-mention count does not predict corpus density, and any
argument built on ranking four worlds by it is worth nothing.

What survives is the part that was always better evidence: the controlled
experiment below. One world, one sentence changed per persona, same seed,
measured before and after. A correlation across four worlds built months
apart by different hands could never have carried this claim, and it turns
out it could not even carry itself.

**This is steerable, and it has now been tested rather than inferred.**
The claim that a world can be *specified* to carry a task family was the
one arrow in this pipeline with no experiment behind it. Everything
downstream of a recording had been measured; the arrow into it had only
correlation across worlds built months apart by different hands.

`datasets/merrick/probe_delegation.py` is the experiment. Merrick's own
cast, own matters, own seed, and **one sentence added to each persona's
email register** — say by name what other people owe and when — then ten
days recorded and counted. The form under test is third-person assignment
with a date attached, which four recorded worlds had between them almost
never produced (1, 8, 14 and 0 instances), and whose absence is what
blocks a second task family.

    corpus                        items   anchored   per 100
    merrick meetings, all           2872          6      0.21
    merrick meetings, days 1-10      178          0      0.00   <- control
    PROBE meetings, days 1-10        191          4      2.09
    merrick mail, all               1399          1      0.07
    merrick mail, days 1-10           83          0      0.00   <- control
    PROBE mail, days 1-10            116          2      1.72

Ten times the baseline rate in meetings (p = 0.0008) and twenty-four times
in mail (p = 0.003), against the full-corpus rate; the matched ten-day
control produced **none at all**, on comparable volume. And the sentences
are the shape the register needs, not near-misses:

    "Adaora owes Dov a name and one-line scope on the biz dev ticket
     by tomorrow morning"
    "Oskar has the data-processing markup to me by end of day tomorrow"
    "Quentin will have a name and one-line scope to circulate by
     tomorrow AM"

So a world spec is a lever on what tasks are possible, and the honest
order of work is to change the spec and record before designing a family
around a form the corpus does not contain. The negative that motivated
this — no anchored assignment anywhere — was solid across four worlds and
was a fact about those worlds' personas, not about English.

One measurement error nearly buried it. The first pass scanned
`sim.meeting.turn` events, which carry a speaker and no text: the scan
returned zero for the probe's meetings and the reading was "mail moved,
meetings did not". The turns live on `meeting.transcript`. A scan over
empty strings cannot fail to find nothing, which is why the mean length
of what was scanned is now printed beside every count.

The chain from spec to prose is traceable end to end. A persona carries
`personality`, `role_description` and `channel_style` (email register,
chat register, quirks) as free text into its prompt. Counting date-ish
words in those specs against what the recording contains:

    merrick   21 personas, 8 mentions ("by when", "deadline", "Friday")
              -> 537 dated owner-mails, 175 admitted promises
    calder    17 personas, 0 mentions
              -> 1,479 owner-mails, 392 admitted commitments
                 (the spec asks for no dates and the firm writes them
                  anyway, which is why this pairing proves nothing)

And the individual specs are visible in the prose they produced:

    Dov Reinhardt   email_register: "Bulleted, deadline-first, asks for a
                    number not a narrative."
    Rosalie Duchamp email_register: "...tells you what she needs and by when."
    Thandiwe Mokoena role: "Owns the firm's docket: every court deadline,
                    every response date, every statutory clock."

The sharpest instance is a warning as much as a demonstration. Ingrid
Solheim's spec carries the quirk **"Says 'that is not a real deadline' when
it is not."** — and the sentence that broke this dataset's oracle, costing a
day of adjudication, is hers: *"closing tomorrow on an unconfirmed Closing
Date is not a real deadline"*. The rule matched `tomorrow` inside its own
denial.

So a world spec decides both what tasks are POSSIBLE and which defects the
extractor will meet. A persona written to say a thing is not a deadline
guarantees the negation cases exist; whether the rule survives them is a
separate question, and the one the rest of this pipeline answers. The
survey below is how you find out whether the property you asked for
arrived.

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

**And then do not trust them on their own.** A register keyed by (person,
matter) surveys better than the task that works — rows per owner 1.81
against 1.17, repeat 34%, 29 groups — and is ungradable. People name
matters "Sable Ridge" and "Kestrel"; the firm's matter list names them by
client and description; one turn about Sable Ridge keyed to a matter
called "Sandhurst 9:15 Status Call Recap" because `Status` was the only
word the list recognised. Just 1 commitment in 35 names a matter in the
same clause as the promise.

That is the anchor limit in a second family, and the survey cannot see it:
its four numbers describe the SHAPE of a row set, not whether the key can
be recovered. Print the derivation beside the source for twenty rows and
read them. The wrong ones are obvious in seconds and invisible in
aggregate.

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

## Correcting an oracle can move a task to ceiling

The most uncomfortable measurement here, and the one most worth keeping.

`live-commitment-register` measured **0.766 ×3** for the strongest tier.
Four defects were then found and fixed, each confirmed by readers who
never saw the implementation:

| defect | what it did |
|---|---|
| a day had to be the clause's last word | dropped `first thing tomorrow morning` |
| `or` between two times took the first | invented a date nobody picked |
| `\bn't\b` matched no contraction | kept four days being ruled OUT |
| a row cited a superseded turn | the wrong date for one owner |

On the corrected key the same tier measures **0.909**, and the shape of
that number matters more than the number: `live.f1` **1.000**,
`row_facts` **1.000**, fourteen rows of fourteen in every trial. The
residual is one integer, off by one — the count of what was discarded,
which never appears in the register itself.

**Every one of the four corrections moved the key toward what the model
had already produced.** That is the tell. The 0.766 was not measuring how
hard the reading is; a third of it was measuring how wrong the answer key
was, and reporting it as a property of the tier.

There is a mechanism behind this and it is not bad luck. **Each correction
is a sentence added to the brief, and each sentence removes a judgement
call.** The brief now states that a time of day may trail a day, that two
times joined by `or` settle nothing, that a contracted negation counts.
Every one of those is necessary — the alternative is an ungradable rule —
and together they turn a semantic task into a specification a model can
implement. That is the ceiling law arriving through the front door, driven
by the correctness loop itself.

Two things follow, and both are now enforced rather than remembered:

* `certify.py` checks the **heaviest criterion**, not the mean. A headline
  inside the band can be made entirely of bookkeeping: 45% of this task's
  weight is `live.f1`, and a tier scoring 1.000 on it is not being
  measured whatever the aggregate says.
* A task whose score *rises* with every oracle correction was reporting
  the author's errors. Keep the scores from every key version; the
  sequence 0.766 → 0.909 is the finding.

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
