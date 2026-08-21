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

The term is **one word in two admitted forms**: agree and agreed.
That is the whole term — no stem, no wildcard, no synonym, no other
ending.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage**, and **calendar**.

## The window

Report only messages sent **on or before Wednesday 14 January 2026** — the firm's
first 8 working days. A message sent
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
| `agree` | the word *agree* |
| `agreed` | the word *agreed* |

**The test is textual, not editorial.** A message counts when the word is
in it, whatever the sentence is doing with it — reporting, asking,
promising, quoting a document, or using the word for something with no
bearing on the firm's work at all. For instance, *"yeah agreed — whoever's matter
partner on Atwater needs to make the split call"* is one colleague
assenting to another, and *"send me the sign/fund date the moment both
are done, same day, as agreed"* is about a funding date, with the word
carrying nothing but a reference to something settled earlier. Both
contain the word and both are hits. Do not weigh up whether the message is about the
thing the term was written to find.

**A form counts only when it stands as its own word.** Letters, digits and
the underscore continue a word; every other character ends one. So a
hyphenated compound is two words and the form inside it counts —
`re-agreed` carries agreed — while a longer word that merely contains
the letters does not. This is a separate question from the one above, and
it is settled here: inside a longer *phrase* is a hit; inside a longer
*word* is not.

Nothing else counts, and that cuts two ways.

**No other ending counts.** *agreement* alone appears in thirty-five of this window's messages, and twenty-eight of those carry no admitted form at all; *agreements* appears in nine, eight of them likewise. Not one makes a row. **The excluded form outnumbers the answer**: a reader who stems to `agree-` gains thirty-six rows against a register of twenty-two, and more than half of what they report is not the term. `disagree` is a longer word rather than a phrase, so it carries nothing.

**No synonym counts.** The firm also writes *sign* — twenty messages, seventeen of which never carry either admitted form — and *signed*, in eighteen, fourteen likewise; *align* in two and *consent* in one. Every one of those messages stays out. The term is the term, not the idea behind it.

**One row per message**, however many times either form appears in it. For
`form_counts`, a message carrying both forms counts once, under `agree`.

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
  are exactly, and in this spelling:
  `Client`, `Corporate`, `Employment`, `Firm Management`, `IP`,
  `Litigation`, `Practice Operations`
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
