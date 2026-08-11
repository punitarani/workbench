# Billing reconstruction: the Meridian April invoice dispute

You are **Carl Jensen**, billing coordinator at Hartwell & Marsh LLP. The
May 2026 dispute over the Meridian BioLabs April invoice was resolved,
but the file needs a precise numeric record of what was actually disputed
— the client's challenge turned on time entered *after* the budget call
that re-scoped the data-room diligence, and the resolution capped exactly
that work.

You have the firm's systems: Gmail, Slack, iManage, and Clio, where the
time entries live.

Save **`dispute.json`** in your workspace:

```json
{
  "cutoff_date": "<YYYY-MM-DD budget-call cutoff the parties agreed>",
  "total_minutes": <total minutes of the disputed diligence work>,
  "entry_count": <number of time entries that make it up>,
  "entries": [
    {
      "id": <Clio activity id of the disputed time entry>,
      "date": "<YYYY-MM-DD of the entry>",
      "minutes": <minutes of the entry>
    }
  ],
  "minutes_by_timekeeper": {"<timekeeper name>": <their disputed minutes>},
  "timekeepers": ["<everyone who logged that work>"],
  "challenged_by": "<who challenged the invoice>",
  "challenge_date": "<YYYY-MM-DD the client disputed the invoice>",
  "support_audit": [
    {
      "date": "<YYYY-MM-DD in the post-cutoff April review window>",
      "entry_ids": [<every Meridian Clio activity id that day>],
      "entry_count": <number of those entries>,
      "minutes": <their total minutes>,
      "billed_cents": <their billed amount in cents>,
      "gmail_message_ids": ["<every qualifying same-day Gmail message id>"],
      "slack_message_ts": ["<every qualifying same-day Slack ts>"],
      "supported": <true when either evidence list is nonempty>
    }
  ],
  "unsupported_days": [
    {
      "date": "<YYYY-MM-DD with no qualifying support>",
      "entry_ids": [<every Clio activity id on that date>],
      "entry_count": <number of those entries>,
      "minutes": <their total minutes>,
      "billed_cents": <their billed amount in cents>
    }
  ]
}
```

The disputed work is every time entry on the Meridian diagnostics
acquisition matter dated **strictly after the budget-call cutoff** whose
narrative describes the data-room diligence (the entries whose notes
mention diligence or the data room). Establish the cutoff date yourself —
the emails and the matter note describe the split but never state the
date — and beware of near misses on every side of the join: diligence
work on this matter began before the cutoff, an entry landed on the
cutoff day itself, other matters carried diligence and data-room work
that April, and post-cutoff Meridian entries describe the expanded scope
without the diligence wording. A sum over every diligence entry, over the
whole billing month, or over every matter is wrong. `entries` must list
the exact disputed Clio time entries — id, date, and minutes each — and
the minutes have to be counted off the entries themselves; no email
states the figures.

The resolution also ordered a **complete daily support audit** over the
disputed window. `support_audit` has one chronological row for every date with
a Meridian time entry strictly after the budget-call cutoff through the end of
April. Each row must account for every entry on that date and every qualifying
same-day email or Slack message. A message qualifies when its subject or body
text names the engagement — the client (Meridian), the deal (the diagnostics
acquisition), or the matter number (00001). Search Gmail, public Slack channels,
and every Slack DM; use Gmail message ids and Slack `ts` values as the evidence
identities. Vague
references do not count: a data room, a tranche, a privilege screen, or
a diligence call could belong to any matter (the Solstice closing
staged a seller data room the same month), so a message supports an
entry only when it names the engagement in one of those three forms. A row is
`supported` exactly when at least one of its two evidence lists is nonempty.

`unsupported_days` is the exception view of that complete workpaper. It must
cover every window entry — diligence-worded or not — with no qualifying message
anywhere in the firm's systems on its date. Group those unsupported entries by
date, one object per silent day in chronological order. Each daily object in
both views must list every affected activity id and sum that day's entry count,
minutes, and billed cents. `billed_cents` is the sum of the Clio `total` for each
billable entry, with each entry rounded to cents as Clio displays it;
non-billable entries contribute zero. Check every surface before calling a day
silent: on some days the only qualifying message sits in a DM that
channel search never returns, on others it never uses the client's
name, and on others the day is full of deal-flavored traffic that never
names the engagement at all. The complete workpaper and its exception view go
back to the client together, so they must reconcile exactly.
