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
  "came_back_later": ["<Slack ts of each request answered after the day it was asked but still inside the standard>"],
  "unanswered_askers": ["<each person who asked and got nothing>"]
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

`unanswered_request_ts` lists the request's own Slack `ts` for every
request that got neither, inside that window. The near misses are the
whole difficulty: several requests sat overnight and were picked up the
next working day, one was answered by mail rather than chat, and two of
the overnight ones were asked on a Friday, so counting calendar days
instead of working days puts them on the list wrongly. Sweep every
one-to-one conversation from March through June — they run to thousands of
messages and none of the long ones comes back in a single read.

You are handing this to Eleanor as the complete list. One request named
that did get a second read, or one that truly went unanswered left off,
and the review is worth nothing.
