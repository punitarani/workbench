# Chain of custody: the visitor log nobody sent back

You are **Omar Haddad**, records clerk at Hartwell & Marsh LLP. The
reception sign-in sheet is a firm record — the retention policy in the
firm's own repository says so, and it is you who administers the
schedule. In practice the sheet wanders: somebody takes yesterday's page
upstairs for a conflicts note or a billing query, and it is supposed to
come back.

The annual records review found gaps in the log. Anita wants to know
where the chain broke, and she wants it from the record rather than from
whoever remembers what. The asking happens where people ask each other
for things: one to one, in Slack direct messages. Chat search does not
reach into those, so there is no shortcut — the conversations have to be
opened, one at a time.

Save **`visitor-log.json`** in your workspace:

```json
{
  "requests_reviewed": <how many times the sheet was asked for, all conversations>,
  "conversations_reviewed": <how many one-to-one conversations you went through>,
  "open_handover_ts": ["<Slack ts of the request>", "..."],
  "open_handovers": [
    {
      "ts": "<Slack ts of the request>",
      "date": "<YYYY-MM-DD it was asked>",
      "asked_by": "<who asked for the sheet>",
      "asked_of": "<who was asked>"
    }
  ],
  "closed_same_day": <how many requests drew something back the same day>,
  "closed_next_day": ["<Slack ts of each request answered after the day it was asked but still inside the standard>"],
  "open_requesters": ["<each person who asked and got nothing>"]
}
```

The firm asks for the sheet in one standing form of words: *do you still
have the sign-in sheet from yesterday?* Every instance of that request,
in every one-to-one conversation, is in scope.

A request is **closed** when the person who was asked comes back to the
person who asked — anywhere in the firm's systems — by the end of the
next working day. The firm works Monday through Friday, so a Friday
request is still inside the standard if the answer lands on the Monday.
Coming back means either a message from them later in that same one-to-one
conversation, or an email from them to the person who asked. It does not
mean the asker writing again, it does not mean the two of them being
active somewhere else in the firm, and it does not mean somebody else
answering on their behalf.

`open_handover_ts` lists the request's own Slack `ts` for every request
that got neither, inside that window. The near misses are the whole
difficulty: several requests sat overnight and were picked up the next
working day, and one of those was answered by mail rather than chat —
close the audit at the end of the day it was asked, or look only at chat,
and the list comes out wrong in a different way each time. Sweep every
one-to-one conversation from March through June; they run to thousands of
messages and none of the long ones comes back in a single read.

You are certifying this to Anita as the complete list of breaks in the
chain. One request named that was in fact answered, or one true break left
off, and the certification is worth nothing.
