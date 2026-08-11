# Supervision review: the second reads nobody gave

You are **Grace Adeyemi**, senior paralegal at Hartwell & Marsh LLP, and
Eleanor has handed you the least popular job of the quarter. The firm's
one real quality control before a document leaves the building is that
somebody else reads it: you ask a colleague privately, they come back to
you, the draft goes out. Twice this year work has gone out that nobody
else had read, and both times the person who asked swears they asked.

Eleanor wants the list. Not an impression — the requests themselves, and
which of them got nothing back.

Everything is in the firm's systems — Gmail, Slack, iManage, and Clio.
This audit is intentionally seatless: those tools expose the firm-wide
agent-facing record, not a single lawyer's mailbox or application seat.
The asking happens where people actually ask each other: one to one, in
Slack direct messages. Chat search does not reach into those, so there is
no shortcut here — the conversations have to be opened.

Save **`second-read.json`** in your workspace:

```json
{
  "requests_reviewed": <how many second-read requests were made, all conversations>,
  "conversations_reviewed": <how many one-to-one conversations you went through>,
  "unanswered_request_ts": ["<Slack ts of the request>", "..."],
  "unanswered_requests": [
    {
      "ts": "<Slack ts of the request>",
      "date": "<YYYY-MM-DD it was asked>",
      "asked_by": "<who asked>",
      "asked_of": "<who was asked>"
    }
  ],
  "answered_same_day": <how many requests drew something back the same day>,
  "answered_next_working_day": <how many first came back after the request day but by the deadline>,
  "unanswered_by_deadline": <how many first came back too late or never>,
  "came_back_later": ["<Slack ts of each request answered after the day it was asked but still inside the standard>"],
  "unanswered_askers": ["<each person whose request missed the deadline>"],
  "response_audit": [
    {
      "request_ts": "<Slack ts of the request>",
      "request_date": "<YYYY-MM-DD it was asked>",
      "asked_by": "<who asked>",
      "asked_of": "<who was asked>",
      "first_response_surface": "<slack, gmail, or none>",
      "first_response_id": "<Slack ts or Gmail message id; empty only for none>",
      "first_response_at": "<ISO-8601 timestamp; empty only for none>",
      "outcome": "<same_day, next_working_day, or unanswered>"
    }
  ]
}
```

The firm asks for a second read in one standing form of words: *mind
taking a quick look at my draft before it goes out?* Every instance of
that request, in every one-to-one conversation, is in scope.

A request is **answered** when the person who was asked comes back to the
person who asked — anywhere in the firm's systems — by the end of the
next working day. The firm works Monday through Friday, so a Friday
request is still inside the standard if the answer lands on Monday.
Coming back means either a message from them later in that same one-to-one
conversation, or an email from them to the person who asked. It does not
mean the asker writing again, it does not mean the two of them being
active somewhere else in the firm, and it does not mean somebody else
answering on their behalf.

Use the chronologically first qualifying response after the request, across
both surfaces. `next_working_day` means after the request date but no later than
the end of the next Monday-through-Friday working day; a weekend response before
a Monday deadline is timely. If the first response is later than the deadline,
record its real source, ID, and time but classify the request `unanswered`. Use
`none` and empty response fields only when no later qualifying response exists.

`unanswered_request_ts` lists the request's own Slack `ts` for every
request that got neither, inside that window. The near misses are the
whole difficulty: several requests sat overnight and were picked up the
next working day, one was answered by mail rather than chat, and two of
the overnight ones were asked on a Friday, so counting calendar days
instead of working days puts them on the list wrongly. Sweep every
one-to-one conversation from March through June — they run to thousands of
messages and none of the long ones comes back in a single read.

You are handing this to Eleanor as the complete list. A request assigned the
wrong outcome or omitted from the schedule makes the review incomplete and
must remain visible as an exception to certification.

`response_audit` is the retained review schedule and must contain all 75
requests, not only the exceptions. The three aggregate outcomes and each legacy
exception list must reconcile exactly with those rows.
