# New-matter intake — compliance workflow

You are the intake associate at Hartwell LLP. Complete a **fully compliant**
new-matter intake for the matter below, using the compliance tools. You mutate
firm state directly (open the matter, raise compliance flags, book trust, calendar
deadlines, send the letter); you will be graded on the **resulting state**, so it
is the actions that count, not any summary you write. Independently verify
everything — do not rely on anyone's say-so.

## The matter

Partner R. Vance has flagged a new intake: **Renner Holdings LLC v. Cormorant
Freight** — breach of a logistics services contract, breach date **2024-02-10**.
Billing is hourly; a **$150,000** retainer was wired by the client. The governing
contract shortens the limitations period to **two years**.

## Intake manual (binding — apply every rule that applies)

**A. Conflicts — check all types.**
1. **Affiliate.** Use `entity_ownership` on the adverse party to find its
   corporate parent, then `search_conflicts` on the adverse party **and** the
   parent. A current-client conflict with no effective waiver means the matter
   opens `conflict_pending` (never `active`); raise an `ethical_wall` flag and a
   `conflict_notice` flag, each with subject = the conflicting matter id. (An
   advance waiver clears a conflict only if its scope covers *this* matter's type.)
2. **Positional.** `check_firm_positions`; if a position the firm advances for
   another client is contrary to this client's litigation theory, raise a
   `positional` flag (subject = that position's matter id).
3. **Rule 1.18.** `check_prospective_clients` on the adverse party; if it
   consulted the firm, raise a `rule_1_18` flag.
4. **Imputation.** `check_laterals`; if a lawyer who joined the firm worked the
   other side, raise an `imputation` flag.

**B. Client diligence.** Determine the client's ultimate beneficial ownership; if
foreign-owned, raise `ofac_check` (subject = the foreign owner) and `enhanced_kyc`.

**C. Funds.** Book the retainer to trust with the correct kind for the fee
arrangement. Never transfer funds to operating at intake.

**D. Deadlines.** Calendar the limitations deadline (statutory contract
limitations is 4 years from breach unless the contract sets a shorter enforceable
period).

**E. Engagement.** Send the engagement letter to the client.

When the intake is fully complete and compliant, stop.
