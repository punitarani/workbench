# Settlement-authority audit: Project Marigold

You are **Samuel Marsh**, litigation partner at Hartwell & Marsh LLP. The
malpractice carrier has selected the Goldleaf franchise litigation for a
settlement-authority review. The client—not counsel—controls settlement, and
the audit must show whether each concrete proposal the firm sent to opposing
counsel was inside the authority documented at the moment it went out.

The file uses a negotiation code name. Resolve that name, the exact Clio matter
number, the client decision-maker, and opposing counsel from the firm record
before deciding what correspondence belongs to the matter. Review the July 1
through September 18, 2026 Pacific-time period. Gmail, Slack, iManage, and
Clio expose the firm-wide record; this task is intentionally seatless.

Save **`authority.json`** with exactly this public structure:

```json
{
  "matter_number": "<exact Clio display number>",
  "negotiation_alias": "<the code name used in negotiation traffic>",
  "client_decision_maker": "<full name>",
  "opposing_counsel": ["<full name>", "..."],
  "proposal_count": <number of outbound proposals reviewed>,
  "authorized_count": <number compliant with authority>,
  "breach_count": <number not compliant>,
  "breach_message_ids": ["<Gmail message id>", "..."],
  "authority_timeline": [
    {
      "effective_at": "<ISO-8601 timestamp with offset>",
      "surface": "gmail or slack",
      "source_ids": ["<Gmail message id or Slack ts>", "..."],
      "status": "grant or hold",
      "amount_cents": <integer; 0 for a hold>,
      "amount_rule": "minimum, exact, or none",
      "economic_basis": "exclusive, inclusive, net_plus_fees, or none",
      "required_terms": ["<normalized term>", "..."],
      "prohibited_terms": ["<normalized term>", "..."],
      "expires_at": "<ISO-8601 timestamp with offset, empty for none>"
    }
  ],
  "proposal_audit": [
    {
      "message_id": "<Gmail message id>",
      "sent_at": "<ISO-8601 timestamp with offset>",
      "sender": "<full name>",
      "amount_cents": <integer>,
      "economic_basis": "exclusive, inclusive, or net_plus_fees",
      "terms": ["<normalized term>", "..."],
      "authority_source_ids": ["<source ids for the authority state applied>", "..."],
      "disposition": "authorized, amount_outside_authority, economic_terms_mismatch, nonmonetary_terms_mismatch, authority_revoked, authority_expired, authority_not_yet_effective, or condition_unmet"
    }
  ]
}
```

An outbound proposal is a Gmail message from Hartwell & Marsh to the opposing
counsel identified in the matter record that communicates a concrete dollar
proposal for this dispute. Do not count the opponent's offers, internal drafts,
status mail, or client instructions. Review every qualifying outbound message,
including repeated numbers.

Build the authority state chronologically, ordered by the moment each
instruction becomes **operative** — which is not always the moment it is
written. A later instruction replaces an earlier one once it is operative. A
hold or revocation takes effect immediately. `amount_rule` is `minimum` when
any amount at or above the number is within authority, and `exact` when only
that number is.

Four independent rules govern which authority is in force, and each proposal's
disposition turns on getting all of them right. Resolve them in order:

1. **First-reliable-report docketing.** Most new client authority reaches the
   file first as a contemporaneous partner relay in the internal DM — the
   client grants authority by telephone and the partner relays it the same
   day — a day or two before the client's written email lands. Under firm
   policy that authority is **operative from the first reliable report (the
   relay), not from the later written email**. A proposal sent in the gap
   between the relay and the written email is governed by the newly reported
   authority, not by the authority the written record alone would suggest. The
   relay and the confirming email are both part of the state's source record.
   A grant relay states an operative amount ("exactly $X"); a bare dollar
   figure ("put the $300,000 authority on hold") is not a grant. Do not treat
   ordinary internal discussion as client authority.

2. **Expiry by time of day, in Pacific.** Each grant expires at a specific
   clock time ("5:00 p.m. Pacific on August 28", "noon Pacific on August 4").
   Timestamps are served in machine time — convert each to Pacific and compare
   the proposal's actual send **instant** to the expiry instant, to the
   minute, not to the calendar day. A proposal at or before the expiry instant
   is inside the window; one minute after is `authority_expired`.

3. **Conditional (contingent) authority.** A grant may be contingent on a fact
   recorded on another surface (an opposing-counsel confirmation that a
   document was executed). The grant is operative from its report, but a
   proposal sent **before** the confirming fact lands is `condition_unmet`,
   even if its amount and terms otherwise match; once the confirmation lands,
   the same proposal is authorized. The confirming item is part of the state's
   source record.

4. **Stated future effect.** Some authority is written to take effect only at a
   later stated moment ("takes effect at 9:00 a.m. Pacific on Wednesday — not
   before"). It is known when the email lands but is not operative until that
   moment. A proposal sent after the prior grant has lapsed but before the new
   grant takes effect is `authority_not_yet_effective`.

Test each proposal against all documented dimensions: the amount rule, whether
fees and costs are inclusive, exclusive, or separately payable, required
non-monetary terms, prohibited terms, and the time window. Use these normalized
term labels when they apply: `mutual_release`, `general_release`,
`release_unknown_claims`, `mutual_non_disparagement`, `confidentiality`,
`no_confidentiality`, `inventory_transition_60_days`, and
`payment_within_10_days`. A `no_confidentiality` requirement means the proposal
must carry an explicit no-confidentiality term; a prohibited `confidentiality`
means it must not offer one. Sort terms and names alphabetically. Keep source
ids in chronological order, and order both audit arrays chronologically.

Determine the authority operative at the proposal's send instant, then assign
exactly one disposition using this priority:

1. A hold or revocation is operative → `authority_revoked`.
2. The operative grant's expiry has passed → `authority_not_yet_effective` if a
   newer grant has been issued but has not yet taken effect, otherwise
   `authority_expired`. (If no grant is yet effective because the only one
   issued has a future effect, that too is `authority_not_yet_effective`.)
3. The operative grant is contingent and its condition was not yet confirmed at
   the send instant → `condition_unmet`.
4. The amount is outside the operative authority → `amount_outside_authority`.
5. The economic basis differs → `economic_terms_mismatch`.
6. A required term is missing or a prohibited term is present →
   `nonmonetary_terms_mismatch`.

Otherwise the proposal is `authorized`. The counts and breach list must
reconcile to the proposal schedule exactly. This is the carrier's retained
workpaper; a summary without the underlying chronology is not a certification.
