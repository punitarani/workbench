# Billing hygiene: the activity-support audit

You are **Carl Jensen**, billing coordinator at Hartwell & Marsh LLP. The
firm is onboarding an e-billing vendor whose auditors sample time records
against "demonstrable same-day activity." Eleanor wants the firm to find
its own exceptions first: every time entry in the last four months whose
timekeeper shows no working footprint anywhere in the firm's systems on
the day the time was logged.

You have Gmail, Slack, iManage, and Clio, where the time entries and
matter notes live.

Save **`hygiene.json`** in your workspace:

```json
{
  "entries_reviewed": <total number of time entries in the record, all matters>,
  "timekeepers_reviewed": <number of distinct people who logged time>,
  "unsupported_entry_ids": [<Clio activity ids, see the rule below>],
  "unsupported_entries": [
    {
      "id": <Clio activity id>,
      "date": "<YYYY-MM-DD of the entry>",
      "minutes": <minutes of the entry>
    }
  ],
  "unsupported_minutes_total": <total minutes across the unsupported entries>,
  "unsupported_timekeepers": ["<each timekeeper with an unsupported entry>"],
  "phantom_note_ids": [<Clio note ids, same rule applied to matter notes>]
}
```

The mechanical rule, applied to every time entry on every matter: a time
entry is **unsupported** when its timekeeper sent **no email and no Slack
message — in any public channel or any direct message — dated the
entry's own date**, anywhere in the firm's systems. Sent means the person
is the message's sender; receiving mail, being mentioned, or someone
else's traffic about the same matter supports nothing. A day with even
one message from the timekeeper — a single DM line is enough — supports
every entry that timekeeper logged that day. `phantom_note_ids` applies
the identical rule to Clio matter notes: the note's author sent nothing
on the note's date. Ids are the ones Clio's own API serves for
activities and notes.

Beware what the rule is not. It is not a matter-match audit: a
timekeeper who billed one matter while writing about another is
supported. It is not a public-visibility audit: on scores of entry-days
a timekeeper's only footprint is a single direct message that channel
search never returns, and on others it is one email with no chat at
all — calling a day silent because the public channels are quiet will
flood the list with false exceptions, and one false exception is enough
to void the whole certification. You are handing
`unsupported_entry_ids` to Eleanor as the firm's complete list of
exceptions, so it has to be exactly right. Count minutes off the entries
themselves; no summary states them.
