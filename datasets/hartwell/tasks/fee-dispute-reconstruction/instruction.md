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
same-day message. The firm runs the diligence file under the deal **code name
"Project Skylark"**, so the client's own name almost never rides the day-to-day
traffic. A message qualifies as same-day support under a two-tier rule:

- a **matter reference** always qualifies — the code name **Skylark** or the
  Clio matter number **00001**;
- the **client name "Meridian"** qualifies only when the same message also
  carries a **diligence work token**: a *data room*, *diligence*, a *tranche*,
  a *privilege* screen or log, an *index*, a *manifest*, a *QC* pass, or a
  *VDR*. A message that merely drops the client's name with no such work — a
  social note, a cross-matter aside — is **not** support.

Everything else is noise: a bare "data room" or "privilege screen" with no
matter reference could belong to any matter (the Solstice closing staged a
seller data room the same month), and a client-name mention with no diligence
work behind it is a distraction. Search Gmail, public Slack channels, and every
Slack DM; use Gmail message ids and Slack `ts` values as the evidence
identities. Slack `ts` and Gmail timestamps are UTC-sourced — take each
message's **Pacific** calendar date before matching it to a day, so an evening
message whose UTC date has already rolled to the next day still lands on the day
it was written. A row is `supported` exactly when at least one of its two
evidence lists is nonempty.

`unsupported_days` is the exception view of that complete workpaper. It must
cover every window entry — diligence-worded or not — with no qualifying message
anywhere in the firm's systems on its date. Group those unsupported entries by
date, one object per silent day in chronological order. Each daily object in
both views must list every affected activity id and sum that day's entry count,
minutes, and billed cents. `billed_cents` is the sum of the Clio `total` for each
billable entry, with each entry rounded to cents as Clio displays it;
non-billable entries contribute zero. Check every surface before calling a day
silent: on some days the only qualifying message sits in a DM that
channel search never returns, on others it names the deal only by its code
name and never the client, on others its one qualifying message lands late in
the Pacific evening, and on others the day carries client-name traffic with no
diligence work behind it — a keyword match on the client's name marks that day
supported when it is not. The complete workpaper and its exception view go
back to the client together, so they must reconcile exactly.
