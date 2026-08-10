# Billing hygiene: corroborated silent days

You are **Carl Jensen**, billing coordinator at Hartwell & Marsh LLP. Before
the firm's time goes to its e-billing vendor, Eleanor wants a certification of
billable time recorded on days that look impossible only after two facts are
joined: the timekeeper was silent in the communication systems, while a
colleague left same-matter work evidence in Clio.

You have Gmail, Slack, iManage, and Clio. Save **`hygiene.json`** in your
workspace with exactly this public structure:

```json
{
  "entries_reviewed": <number of billable Clio time entries>,
  "timekeepers_reviewed": <distinct people with a billable time entry>,
  "anomalous_timekeeper_days": [
    {
      "date": "<YYYY-MM-DD>",
      "timekeeper": "<Clio timekeeper name>",
      "entry_ids": [<affected Clio activity ids>],
      "matter_numbers": ["<affected Clio display numbers>"],
      "minutes": <affected billable minutes>,
      "billed_cents": <affected billed amount in cents>
    }
  ],
  "anomalous_entry_count": <affected billable entry count>,
  "anomalous_minutes_total": <affected billable minutes across all records>,
  "anomalous_billed_cents_total": <affected billed cents across all records>,
  "phantom_note_ids": [<Clio note ids meeting the note rule>]
}
```

Consider only **billable** Clio time entries. A timekeeper-day is anomalous
when both conditions hold:

1. The timekeeper sent no Gmail message and no Slack message anywhere on that
   date. Slack means every public channel and every direct message. Sent means
   the person is the sender; receiving mail, being mentioned, iManage edits,
   Clio activity, and Clio notes are not communication footprints.
2. On at least one matter where that timekeeper has a billable entry that day,
   another person recorded a Clio activity or Clio note on the same matter and
   date.

For an anomalous timekeeper-day, `entry_ids`, `matter_numbers`, `minutes`, and
`billed_cents` cover only the timekeeper's billable entries on the matters
corroborated by another person's same-day activity or note. Do not sweep in a
same-day entry on a different matter where nobody else recorded work. Group
all affected entries into one record per timekeeper and date, order records by
date, order entry ids as Clio serves them, and list each affected matter once
in first-entry order.

`billed_cents` is the sum of the individually rounded public Clio `total` for
the affected entries, converted to cents. Do not multiply aggregate hours by
a rate, and do not include non-billable entries. The three aggregate fields
must reconcile to the records.

Apply the same corroboration rule to `phantom_note_ids`: a note qualifies only
when its author sent no Gmail or Slack message anywhere on its date and
another person recorded a Clio activity or note on that same matter and date.
The ids are the public Clio ids. This is not a raw silent-day audit; silence
without same-matter corroboration is not an exception.
