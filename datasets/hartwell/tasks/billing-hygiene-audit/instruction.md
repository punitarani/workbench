# Billing hygiene: corroborated silent days

You are **Carl Jensen**, billing coordinator at Hartwell & Marsh LLP. Before
the firm's time goes to its e-billing vendor, Eleanor wants a certification of
billable time recorded on days that look impossible only after two facts are
joined: the timekeeper was silent in the communication systems, while a
colleague left same-matter work evidence in Clio.

You have Gmail, Slack, iManage, and Clio. Save **`hygiene.json`** in your
workspace with exactly this public structure:

The certification period is March 2 through June 30, 2026, inclusive. Do not
fold later activity or communications into this closed billing review.

```json
{
  "entries_reviewed": <number of billable Clio time entries>,
  "timekeepers_reviewed": <distinct people with a billable time entry>,
  "person_days_reviewed": <distinct billable timekeeper-days reviewed>,
  "cleared_by_communication": <person-days with sent Gmail or Slack evidence>,
  "cleared_no_corroboration": <silent person-days with no corroborated entries>,
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
  "anomalous_timekeeper_day_count": <anomalous person-day count>,
  "anomalous_entry_count": <affected billable entry count>,
  "anomalous_minutes_total": <affected billable minutes across all records>,
  "anomalous_billed_cents_total": <affected billed cents across all records>,
  "phantom_note_ids": [<Clio note ids meeting the note rule>],
  "daily_review": [
    {
      "date": "<YYYY-MM-DD>",
      "timekeeper": "<Clio timekeeper name>",
      "billable_entry_ids": [<all billable Clio activity ids for this person-day>],
      "sent_gmail_ids": ["<all Gmail message ids sent by the timekeeper that date>"],
      "sent_slack_ts": ["<all Slack message ts values sent by the timekeeper that date>"],
      "corroborated_entry_ids": [<billable entry ids on corroborated matters>],
      "corroborated_matter_numbers": ["<corroborated Clio display numbers>"],
      "disposition": "<cleared_by_communication, cleared_no_corroboration, or anomalous>"
    }
  ]
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

`daily_review` is the certification workpaper and must contain one row for
every distinct timekeeper and date represented in the billable population.
List all billable activity ids for that person-day and all source-native Gmail
message ids and Slack `ts` values sent by that timekeeper anywhere on the same
date. Independently list the subset of billable ids whose matters carry
another person's same-day Clio activity or note, plus those distinct matter
numbers. Use `cleared_by_communication` whenever either sent-message list is
nonempty, `cleared_no_corroboration` when both communication and corroboration
lists are empty, and `anomalous` only when communication is empty but
corroboration is present. The daily ledger, person-day counts, and anomaly
summary must reconcile without duplicate rows or evidence ids.

Apply the same corroboration rule to `phantom_note_ids`: a note qualifies only
when its author sent no Gmail or Slack message anywhere on its date and
another person recorded a Clio activity or note on that same matter and date.
The ids are the public Clio ids. This is not a raw silent-day audit; silence
without same-matter corroboration is not an exception.
