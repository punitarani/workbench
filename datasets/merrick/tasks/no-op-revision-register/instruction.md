# The revisions that changed nothing

You are the practice manager at **Merrick Stanton LLP**, a litigation and
transactions firm.

Before this quarter's bills go out, the billing partner wants to know which
document revisions were **no-ops** — a new version saved, filed and
recorded against a matter, where the person who saved it says in the
version comment that nothing substantive changed.

These are not misconduct. A document gets reopened, reviewed, and closed
again with nothing to alter, and the honest thing to do is say so in the
comment — which is exactly what these people did. The partner is not
hunting anyone. She wants the list before a client asks for it.

**This is a record of what the comment says, not of what the document did.**
You are not being asked to diff two versions or to judge whether an edit
was really substantive. A comment that says nothing changed makes a row
even if the document changed enormously, and a comment that describes a
trivial one-word fix makes no row at all.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage**, and **calendar**. Documents and their version
histories are on **imanage**.

## The window

Register revisions saved **on or before «MEASURE: the last day of the
window, as a weekday and a date — e.g. "Friday 30 January 2026". At the
recorded rate this world saves ~7.4 revisions per working day and about one
in five is a no-op, so a four-week window puts ~150 version comments in
front of the reader for ~28 rows. Comments run ~69 words, so 150 of them is
a read comparable to the 213 messages the in-band comparison task settled
on. Re-measure on the finished record.»** — the firm's «MEASURE: how many
working days that window is, counted as weekdays from the record's first
day to the boundary above, inclusive. This is *not* a calendar-day count;
the two differ by every weekend inside the window.» working days.

A revision saved after that boundary makes no row.

Which side of the boundary a revision falls on is decided by its date in
the firm's own time zone (New York) — the same date this register reports
as `revised_date` — not by UTC and not by any other clock a tool prints.

## What makes a row

A version makes a row when its **comment** carries one of exactly these
phrases:

    no substantive edits, no substantive changes,
    no substantive revisions, no changes made,
    no changes were made, no edits made

Case does not matter. Nothing else admits a row.

Two things this rule will tempt you to do, and neither is right.

**It will not read like a rule while you are applying it.** These comments
run to seventy words. Most of them open by describing what the document
*is* — *"This document is a rate card listing timekeepers, titles,
practices and standard rates"* — and a comment can spend sixty words on the
document's contents, mention what was checked, and admit in one clause that
nothing was altered. The clause is the row. The seventy words around it are
not evidence of anything.

**A comment can say both.** A version whose comment describes edits *and*
carries an admitted phrase is a row. You are recording the phrase, not
adjudicating the contradiction.

And the reverse: a comment saying *"only formatting"*, *"typo fix"*,
*"minor cleanup"*, *"nothing material"* or *"cosmetic only"* is **not** a
row. Those plainly describe a trivial revision. They are not on the list.

A document's **first version is its creation, not a revision**, and never
makes a row.

## The register

Write `no_op_revisions.json` to the workspace root:

```json
{
  "window_end": "2026-01-30",
  "versions_read": 0,
  "no_op_revisions": [
    {
      "document_ref": "LEGAL!12.3",
      "author": "Rosalie Duchamp",
      "revised_date": "2026-01-21",
      "document_name": "Standard rates card"
    }
  ]
}
```

One row per no-op version. A document revised nine times can contribute
several rows.

`document_ref` is the **version's own id, exactly as iManage gives it** —
`LEGAL!12.3` is version 3 of document 12, and it is the `id` field on every
profile and every row `get_document_versions` returns. It already names the
version, so there is no separate version column to fill in.

`author` is the person's full name as the firm's records give it, not the
internal identifier. `document_name` is the document's own name as iManage
holds it.

`versions_read` counts the **revisions** inside the window — the ones you
had to read. A document's first version is its creation, not a revision, so
it is not counted here any more than it makes a row. Every later version
is counted whatever its comment says.

## What is being measured

Whether the register is exactly the rule's output. Two failures cost the
same: admitting a revision that was plainly trivial without saying one of
the phrases, and dropping one that said a phrase inside seventy words of
description.
