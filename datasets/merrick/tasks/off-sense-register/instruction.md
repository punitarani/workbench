# What the search term actually hits

You are the practice manager at **Merrick Stanton LLP**, a litigation and
transactions firm.

Opposing counsel has served a proposed list of search terms. Before the
partners argue about narrowing it, they want to know what one of those
terms hits inside our own correspondence — how many messages, written by
whom, out of which departments.

**A hit report is not a relevance review.** It says what the term matches,
not what the matches are about. Whether a message is responsive is somebody
else's decision, made later, from this list. Your job is the list the term
produces on its face, and it is only worth having if it is exactly that.

The term is **one word in two admitted forms**: «FORM_A» and «FORM_B».
That is the whole term — no stem, no wildcard, no synonym, no other
ending.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage**, and **calendar**.

## The window

Report only messages sent **on or before «MEASURE: the last day of the
window, as a weekday and a date — e.g. "Friday 16 January 2026". Choose it
so the register carries at least 12 rows and the reader's load stays near
the 213 messages the in-band ashgrove task settled on; measure both with
`measure_candidates.py --days N` before writing it here.»** — the firm's
first «MEASURE: how many working days that window is: the weekdays from the
record's first day to the boundary above, inclusive. This is *not* the
`--days` figure `measure_candidates.py` takes and *not* the offset
`solve.py` holds — both of those count calendar days, and the two numbers
differ by every weekend inside the window.» working days. A message sent
after that makes no row here, however squarely the term hits it.

Which side of that boundary a message falls on is decided by its date in
the firm's own time zone (New York) — the same date this register reports
as `sent_date` — not by UTC and not by any other clock a tool prints.

`messages_read` counts the messages **inside the window** — the ones you
actually had to read. There is no need to open anything sent later; the
rest of the record is not part of this question.

## What is in scope

**Mail**, and the workspace's **channels**. One-to-one direct conversations
are not part of this exercise: leave them out of the register and out of
`messages_read`.

## What counts as a hit

A message is a hit when its body carries either of these two forms, matched
case-insensitively, anywhere in the text:

| form | matches |
|---|---|
| `«FORM_A»` | the word *«FORM_A»* |
| `«FORM_B»` | the word *«FORM_B»* |

**The test is textual, not editorial.** A message counts when the word is
in it, whatever the sentence is doing with it — reporting, asking,
promising, quoting a document, or using the word for something with no
bearing on the firm's work at all. «MEASURE: two short real examples from
the window, one squarely on the term's own subject and one plainly off it,
both quoting the corpus rather than an invented sentence.» Both contain the
word and both are hits. Do not weigh up whether the message is about the
thing the term was written to find.

**A form counts only when it stands as its own word.** Letters, digits and
the underscore continue a word; every other character ends one. So a
hyphenated compound is two words and the form inside it counts —
`re-«FORM_B»` carries «FORM_B» — while a longer word that merely contains
the letters does not. This is a separate question from the one above, and
it is settled here: inside a longer *phrase* is a hit; inside a longer
*word* is not.

Nothing else counts, and that cuts two ways.

**No other ending counts.** «MEASURE: the inflections and derived forms of
this family that the window actually contains — with the count of each —
and a sentence naming them as excluded, in the manner of "*completion*
alone appears fifty times". Take the list and the counts from
`measure_candidates.py`; do not guess which endings a law firm writes.»

**No synonym counts.** «MEASURE: the synonyms the firm's traffic actually
uses for this idea, with a count of the messages that carry one and never
carry either admitted form. Name them, and say that every one of those
messages stays out.»

**One row per message**, however many times either form appears in it. For
`form_counts`, a message carrying both forms counts once, under `«FORM_A»`.

## What to produce

One file in your workspace: **`word_register.json`**, with exactly these
fields. Every figure is a count of **messages**, never of occurrences.

- `messages_read` — how many messages you examined, mail and channel chat
  together.
- `hits_total` — how many rows are in `hits`.
- `distinct_authors` — how many different people wrote one.
- `form_counts` — an object with **both** forms as keys, each spelled
  character for character as the table above spells it, each mapped to how
  many rows carry it. Both keys appear every time, including one at zero.
- `department_counts` — an object with **one key per department the
  directory records**, each mapped to how many rows were written by people
  in it. Every key appears every time, including the ones at zero. The keys
  are exactly, and in this spelling: «MEASURE: enumerate the exact
  department strings the served directory records, one per line, spelled and
  capitalised as the directory spells them. The cast as written carries
  seven — Client, Corporate, Employment, Firm Management, IP, Litigation,
  Practice Operations — six practice groups plus the one category every
  outsider in the cast belongs to. Confirm that against the built state
  rather than copying it: a correspondent at an opposing firm, a court or a
  vendor would add a key, and a roster that is short by one loses those rows
  silently while every other key still reads right.»
- `top_author` — the person on the most rows, written the way `author`
  writes them: the full name, never an id. Break a tie alphabetically by
  full name, earlier first.
- `hits` — one entry per matching message, sorted by `ref`, compared as
  text, ascending:
  - `ref` — how the message's own system names it. **Mail** uses an id like
    `msg-000104`. **Chat** has no such id on the wire: the workspace
    addresses a message by its timestamp, a string like `1767661500.000003`.
    Use that, unchanged, every digit.
  - `author` — the full name of whoever wrote the message.
  - `sent_date` — the date it was written, `YYYY-MM-DD`, in the firm's own
    time zone (New York).
  - `where` — for a **mail** message, its subject line exactly as the
    message carries it, `Re:` and all. For a **chat** message, the
    channel's name.

Chat identifies its authors by user id. Resolve each through the directory
— `author` is a person's full name, never an id. The directory also holds
the department each person belongs to; everyone it lists has one, people
outside the firm included, and `department_counts` uses whatever it records
for that person.

## A warning about completeness

Every figure here depends on having read the body of every message in the
window, mail and chat, not its subject or its snippet. The systems hand
them back a page at a time.
