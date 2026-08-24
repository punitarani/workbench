<!--
STOP — DO NOT FILL THIS BRIEF. The premise does not hold on this world.

The three forms the table below admits match FOUR messages in the whole
67-day record, across 1,959 mail and chat bodies:

    within N days     1
    N days after      1
    due in N days     2

The best window yields 3 rows against a twelve-row floor. There is no
window of this record that carries a register.

A wider reading does not rescue it. Admitting `in N days` (3 messages) and
`N days from` (5) reaches about a dozen over six months — still under the
floor for any window, and only by admitting forms this brief does not.

**How this was nearly missed, twice over.** A first screen reported the
task viable on 195 interval-bearing messages. That pattern matched any
`N days` construction anywhere, and most of its hits were the docket
tracker's own "N days remaining" — not a court clock at all. The same audit
had already gone wrong in the other direction, reporting `one-sentence-two-
dates` as empty under a pattern narrower than the corpus's vocabulary. A
screen too broad ships a dead task; a screen too narrow retires a live one,
and the second failure looks like diligence.

Retire it, or re-found it on intervals this firm actually writes.

See docs/fidelity/task-viability.md.
-->

# The clock each deadline runs on

You are the **docket and calendar manager** at **Merrick Stanton LLP**, a
litigation and transactions firm. Deadlines reach this desk in prose long
before they reach the docket. A partner writes that a production is due
within ten days. An associate repeats a court's thirty-day clock in a chat
message. An opposing firm's letter is quoted back with its own interval
attached. None of it is on anybody's calendar until this desk works out
what date it actually lands on.

The partners want that register: every interval the firm's own traffic
names, and the date each one falls due when it is counted the firm's way.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage** and **calendar**. Mail and chat are the two this
register reads.

## The window

Report only intervals named in messages sent **on or before «MEASURE: the
window's last day, in exactly the shape "Friday 16 January 2026" — weekday,
day, month name, year — and nothing else, because that sentence is parsed
back out of this file rather than copied from the solver. Choose the
shortest window from 2026-01-05 that clears the twelve-row floor, with both
values of `rolled` present and rows written by more than one author: a
column carrying one value grades nothing, and a single author makes
`distinct_authors` and `busiest_author` free»**. A message sent after that
day makes no row here, however plainly it names a deadline.

`messages_read` counts the messages **inside the window** — the ones you
actually had to read. Nothing sent later is part of this question, and
there is no need to open it.

## What names an interval

Exactly these three forms, matched case-insensitively, anywhere in a
message body:

| form | what it looks like in the traffic |
|---|---|
| `within N days` | *"produce the privilege log within 10 days"* |
| `N days after` | *"objections are due 30 days after service"* |
| `due in N days` | *"the opposition brief is due in 14 days"* |

`N` is written either in **digits** or as one of these words, and no
others: «MEASURE: the spelled-out numbers that actually appear inside one
of the three forms in this corpus, with the value each stands for — count
them before fixing the list. A list that names a word the firm never
writes admits nothing; a list that misses one the firm writes often scores
every instance of it as a hallucination».

The register reads `day` and `days` alike: *within 1 day* carries the same
form as *within 10 days*.

Between the number and `days` the register accepts **nothing at all**,
**`business`**, or **`calendar`**. *Within 10 days*, *within 10 business
days* and *within 10 calendar days* are the same form carrying the same
number. Every count in this register is in **calendar days**: `business`
changes the wording and nothing else, and no interval here is ever counted
in working days.

**The test is textual, not editorial.** A message counts when one of the
three forms is in it, whatever the sentence is doing with it. *"We should
be able to turn this around within 5 days if the vendor cooperates"* is a
hedge, not a deadline; *"the standard clause gives them 30 days after
notice"* is a description of a contract nobody is working to. Both carry a
form and both make a row. Do not weigh up whether a deadline was really
being set — read the words, not the intent.

**A form counts wherever it appears, including inside a longer phrase.**
*"within 10 days of service"* contains `within 10 days`, and *"due in 14
days or sooner"* contains `due in 14 days`. The words that follow do not
remove the form that precedes them.

## What does not name an interval

Nothing else counts, and each of these is in the traffic:

- **Any other unit.** `within 2 weeks`, `within 3 months`, `30 days'
  notice` written without `after`. Only the three forms above, only in
  `days`. «MEASURE: how many in-window bodies carry a week-or-month
  interval and no admitted form».
- **`N days before`.** The clock runs forward here. A form that counts
  backward is not one of the three. «MEASURE: incidence of `N days
  before`».
- **`in N days` without `due`.** *"I'll have it in 10 days"* is not `due
  in 10 days`. «MEASURE: incidence of bare `in N days` — this is the
  densest near-miss if the firm writes it, and the one worth counting
  first».
- **The hyphenated or bare adjective.** *"a 30-day extension"*, *"the
  14 day window"* — neither is `30 days after` or `within 14 days`.
  «MEASURE: incidence of `N-day` and `N day` used as an adjective».
- **A number the register cannot read.** `within a couple of days`,
  `within the week`. If what stands where `N` goes is neither digits nor
  one of the words listed above, there is no form.
- **A date on its own.** A message that names a date and no interval makes
  no row. A date is what an interval counts **from**; it is never a row by
  itself. «MEASURE: how many in-window bodies carry a date form and no
  admitted interval form».

## What the interval counts from

Every interval needs something to count from. That is the **trigger**, and
it is found in the body of the same message — never in the subject, never
in an earlier message in the thread, never in the matter's file.

A **date form** is any of these, matched case-insensitively:

«MEASURE: the written date shapes this corpus actually uses, as a table of
form and example. Count them before fixing the list. The candidates worth
screening are `March 14`, `March 14th`, `14 March`, `March 14, 2026`,
`2026-03-14`, `3/14` and `3/14/2026`; the abbreviated month names (`Mar`,
`Sept`) are a separate count. A shape the firm never writes costs nothing
to leave out and admits nothing if left in; a shape it writes often and
the list omits turns every one of those messages into a wrong trigger.

Three things this table decides beyond its own contents, all of them in
the same edit:

- **Which number is the month**, for any all-numeric shape. `4/17` reads
  one way or the other and the brief has to say which; the sentence below
  about a form naming no real date is what disposes of `15/16`, and it
  only works once the reader knows the first number is the month.
- **Whether any two admitted shapes nest** — whether one is the opening of
  another, the way `March 14` opens `March 14, 2026`. If none do, the
  longest-at-the-same-start sentence below is a branch that can never be
  taken, and it should be cut here rather than left for a careful reader
  to puzzle over. Restore it with a nesting example if two shapes do nest.
- **How every worked example in the rest of this brief writes a date.**
  They are deliberately written without one right now. If a filled table
  admits, say, only `M/D`, an example written `14 March` teaches the
  reader the opposite of the rule it is illustrating.»

When a date form names no year, the year is **the year the message was
sent**. When it names no month — it is not a date form.

A form that names **no real date** — a day that month does not have, or a
month the calendar does not have — is not a date form either. Pass over it
and take the next one in the body; if there is no next one, the trigger is
the date the message was sent.

**The trigger is the first date form in the body**, reading left to right:
the one that *starts* earliest. Where two forms start at the same place —
where a shorter shape is the opening of a longer one — take the **longer**
one.

**When the body carries no date form at all, the trigger is the date the
message was sent.**

Two things this settles, both of which come up:

- **A trigger may be in the past.** A body that recites the date an order
  issued and then gives an interval counts from that date, even when the
  message was written a week later. The first date form is the trigger
  whether or not the resulting deadline has already gone by.
- **A trigger may have nothing to do with the interval.** A body that
  opens by referring back to the date of a call and then names an interval
  about something else counts from that date. The register does not ask
  which date the writer meant to count from; it takes the first one in the
  body.

## Counting

Count **calendar days forward** from the trigger. **The trigger day is day
zero**, so `within 10 days` counted from the 14th of a month falls due on
the **24th** of that month, not the 23rd. Weekends and holidays are
counted like any other day.

That date is **`raw_due_date`**.

Then, and only then, move a weekend landing:

- If `raw_due_date` is a **Saturday**, `due_date` is the **Monday two days
  later**.
- If `raw_due_date` is a **Sunday**, `due_date` is the **Monday one day
  later**.
- Otherwise `due_date` is the same date as `raw_due_date`.

`rolled` is **true** when `due_date` differs from `raw_due_date` and
**false** when it does not. **Only Saturday and Sunday move a date.** This
register keeps no holiday calendar: a deadline landing on New Year's Day
or on a court holiday stays there.

## One row per message and per interval

A message makes **one row for each distinct number of days its forms
name**. *"Within 10 days"* written twice is one row. *"Within 10 days"*
and *"due in 10 days"* in one body are one row — same number, same
trigger, same date. *"Within 10 days"* and *"30 days after service"* are
**two** rows, because 10 and 30 are different numbers.

## What to produce

One file in your workspace: **`court_clock.json`**, with exactly these
fields:

- `messages_read` — how many messages the window holds, mail and chat
  together. That is a count of what is there, not of what you got to:
  every message in the window has to be read, so the two are the same
  number.
- `deadlines_total` — how many rows are in `deadlines`.
- `distinct_authors` — how many different people wrote a message that made
  at least one row.
- `rolled_count` — how many rows have `rolled` true.
- `form_counts` — an object with **all three** form names as keys —
  `within N days`, `N days after`, `due in N days` — each mapped to how
  many rows it accounts for. **Include a key whose count is zero.** Where
  a row's number is named by more than one form in the same body, count
  the row under the **first of the three, in the order they are listed in
  the table above**.
- `busiest_author` — the person on the most rows. Break a tie
  alphabetically, earlier first.
- `deadlines` — one entry per row, sorted by `ref` ascending as text, and
  within one `ref` by `interval_days` ascending:
  - `ref` — how the message's own system names it. **Mail** uses an id
    like `msg-000104`. **Chat** has no such id on the wire: Slack
    addresses a message by its timestamp, a string like
    `1767661500.000003`. Use that string unchanged, every digit.
  - `author` — the full name of whoever wrote the message.
  - `sent_date` — the date it was written, `YYYY-MM-DD`.
  - `interval_days` — the number the form names, as an integer. A spelled
    number becomes its digits: *five* is `5`.
  - `raw_due_date` — the counted date before any weekend move,
    `YYYY-MM-DD`.
  - `due_date` — the date after the weekend move, `YYYY-MM-DD`.
  - `rolled` — `true` or `false`.

Chat identifies its authors by Slack user id. Resolve each through the
directory — `author` is a person's full name, never an id.

## A warning about completeness

Every figure here depends on having read the **body** of every message in
the window, mail and chat, and not its subject or its snippet: a form can
sit anywhere in a body, and the trigger is found by reading the body from
the beginning. The systems hand messages back a page at a time.
