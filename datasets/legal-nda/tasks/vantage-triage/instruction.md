# Triage memo: Vantage Data Services NDA

You are **Priya Nair**, Counsel (Privacy) at Argent Systems. It is the end
of Thursday and you are on matter-hygiene duty this week. Daniel took the
inbound Vantage NDA today — marked it up, told the commercial team where
he landed, and moved on to the next thing — but the matter file still has
no structured triage memo, and it does not close without one.

Everything you need is in the systems you use every day: Gmail, Slack, the
iManage document repository, and Clio. Reconstruct the clause-by-clause
triage of the **inbound Vantage draft** and save it in your workspace as
**`triage.json`**:

```json
{
  "clauses": {
    "definition":      {"decision": "...", "basis": "..."},
    "term":            {"decision": "...", "basis": "..."},
    "mutuality":       {"decision": "...", "basis": "..."},
    "non_solicit":     {"decision": "...", "basis": "..."},
    "injunctive_relief": {"decision": "...", "basis": "..."}
  }
}
```

`decision` is one of `accept`, `negotiate`, `reject`. `basis` is one or two
sentences stating the firm's actual position and where it comes from.

Be precise: the memo has to reflect the positions the firm actually took
today, not generic best practice. The vendor NDA playbook covers some of
the clauses; for the rest, the position is the one Daniel took in his
markup and said out loud in writing.
