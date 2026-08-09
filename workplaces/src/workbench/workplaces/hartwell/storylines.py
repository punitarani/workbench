"""Storyline directors: deterministic beat scripts for the five Phase 2 arcs.

Each storyline is a fixed calendar of beats — emails, chat, documents, time
entries, notes, and calendar events — that lands on specific workdays and
leaves cross-tool evidence spanning months. Prose comes from the content
store (LM-authored, cached); every load-bearing fact (terms, clauses, dates,
amounts) is a code constant composed into the text, so evidence properties
hold by construction. Ids are minted at realize time from the shared
chronicle minter, so directed beats and procedural traffic never collide.

Arcs (PLAN-phase2.md):
  S1 vendor-NDA standard drift, S2 acquisition fee dispute, S3 a contract
  silently losing its indemnity clause, S4 a client souring into
  termination, S5 a court hearing rescheduled three times.
"""

from collections.abc import Callable, Mapping
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarEventUpdatedPayload,
)
from workbench.core.events.chat import ChatMessagePayload, ChatReactionAddedPayload
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import Attachment, EmailMessagePayload
from workbench.core.events.tickets import (
    FieldChange,
    TicketCommentedPayload,
    TicketUpdatedPayload,
)
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.ids import IdMinter
from workbench.core.seed import Seed, derive_seed
from workbench.core.simtime import SimDuration, SimTime
from workbench.simulation.chronicle.builder import TimedDraft
from workbench.simulation.chronicle.content import ContentStore
from workbench.simulation.errors import ConfigError
from workbench.simulation.lm.protocol import LanguageModel
from workbench.workplaces.hartwell.genesis import WINDOW, HartwellGenesis

# Internal cast (person ids from people.py; stable slugs, not minted).
_EH = "per-eleanor-hartwell"
_SM = "per-samuel-marsh"
_DO = "per-diane-okonkwo"
_ML = "per-marcus-liang"
_SR = "per-sofia-ramirez"
_NF = "per-noah-feldstein"
_GA = "per-grace-adeyemi"
_PN = "per-peter-novak"
_AB = "per-anita-bailey"
_CJ = "per-carl-jensen"

# Externals.
_PRIYA = "per-priya-raman"  # Meridian BioLabs COO
_TOM = "per-tom-hollis"  # Cascadia Outfitters owner
_JUNE = "per-june-akana"  # Lumen Software GC
_RUTH = "per-ruth-calloway"  # LexiPoint Research
_STAN = "per-stan-obrien"  # Ironclad Discovery Services
_DAWN = "per-dawn-mcallister"  # Alameda County clerk
_VICTOR = "per-victor-crane"  # opposing counsel, Crane & Whitaker
_CALEB = "per-caleb-fontaine"  # licensor counsel, Pacific Counsel Group

# Matters from genesis declaration order.
S2_TICKET = "tkt-000001"  # Meridian diagnostics acquisition
S4_TICKET = "tkt-000002"  # Cascadia supplier dispute
S5_TICKET = "tkt-000008"  # Arroyo mechanics lien action
S3_TICKET = "tkt-000009"  # Lumen licensing agreement

# The day S4 closes the Cascadia matter; procedural traffic drops it after.
S4_CLOSED_DATE = "2026-06-04"

# Load-bearing clause text. These exact strings are the evidence the
# storylines hinge on; audits assert their presence and absence.
PLAYBOOK_TERM_STANDARD = (
    "Confidentiality obligations run three (3) years from the date of "
    "disclosure. Longer terms require Managing Partner sign-off before "
    "the redline goes back."
)
PLAYBOOK_RESIDUALS_STANDARD = (
    "Reject any residual-knowledge clause outright. Information retained "
    "in unaided memory is still Confidential Information under our form."
)
NDA_TERM_THREE = (
    "The receiving party's obligations under this Agreement shall continue "
    "for a period of three (3) years from the date of the disclosure "
    "concerned."
)
NDA_TERM_FIVE = (
    "The receiving party's obligations under this Agreement shall continue "
    "for a period of five (5) years from the date of the disclosure "
    "concerned."
)
NDA_RESIDUALS_CLAUSE = (
    "Residual Knowledge. Nothing in this Agreement restricts the receiving "
    "party from using general ideas, concepts, know-how, or techniques "
    "retained in the unaided memory of personnel who had authorized access "
    "to Confidential Information, provided such use does not disclose the "
    "disclosing party's Confidential Information."
)
NDA_INJUNCTIVE_CLAUSE = (
    "Equitable Relief. Each party acknowledges that unauthorized disclosure "
    "may cause irreparable harm, and either party may seek injunctive "
    "relief without posting bond, in addition to any other remedy."
)
INDEMNITY_PARAGRAPH = (
    "9.2 Indemnification by Licensor. Licensor shall defend, indemnify, "
    "and hold harmless Licensee and its officers, directors, and employees "
    "from and against any third-party claim alleging that the Licensed "
    "Software, as delivered and used in accordance with the Documentation, "
    "infringes any United States patent, copyright, or trade secret, and "
    "shall pay all damages finally awarded and reasonable attorneys' fees "
    "attributable to such claim."
)
LICENSEE_INDEMNITY_PARAGRAPH = (
    "9.1 Indemnification by Licensee. Licensee shall defend and indemnify "
    "Licensor against third-party claims arising from Licensee's use of "
    "the Licensed Software in violation of this Agreement or applicable "
    "law."
)

PLAYBOOK_TITLE = "Vendor NDA Playbook"
LEXIPOINT_NDA_TITLE = "Mutual NDA — LexiPoint Research (Draft)"
IRONCLAD_NDA_TITLE = "Mutual NDA — Ironclad Discovery Services (Draft)"
LUMEN_AGREEMENT_TITLE = (
    "Software License and Support Agreement — Lumen Software (Draft)"
)
CASCADIA_LETTER_TITLE = "Disengagement Letter — Cascadia Outfitters"
ARROYO_HEARING_TITLE = "Arroyo v. Fruitvale Partners — motion hearing"

_CONTENT_MODEL_PATH = ("hartwell.content",)


class ContentRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    prompt: str
    max_tokens: int = Field(gt=0, default=380)


def _email_prompt(
    *, writer: str, recipient: str, day: str, facts: str, tone: str
) -> str:
    return (
        f"Write only the body of a workplace email sent {day}. "
        f"Writer: {writer}. Recipient: {recipient}. "
        f"Convey these facts, plainly and specifically: {facts} "
        f"Tone: {tone}. 90-150 words, plain text, no subject line, no "
        "salutation headers beyond a simple greeting, and sign off with "
        "the writer's first name only."
    )


def _section_prompt(*, what: str, facts: str, length: str) -> str:
    return (
        f"Draft {what} for a legal document. Ground it in these facts: "
        f"{facts} Markdown body text only — no document title, no "
        f"commentary. {length}."
    )


def content_requests() -> tuple[ContentRequest, ...]:
    return (
        # S1 — vendor NDA playbook and the drifting redline practice.
        ContentRequest(
            name="s1.playbook.intro",
            prompt=_section_prompt(
                what=(
                    "the introduction (two short paragraphs) of an internal "
                    "law-firm playbook titled 'Vendor NDA Playbook' at "
                    "Hartwell & Marsh LLP"
                ),
                facts=(
                    "the playbook governs NDAs the firm signs with its own "
                    "vendors (research, e-discovery, IT); it exists so every "
                    "vendor NDA goes out on consistent terms; Noah Feldstein "
                    "maintains it; Diane Okonkwo is the reviewing attorney; "
                    "drafted March 2026."
                ),
                length="120-180 words",
            ),
        ),
        ContentRequest(
            name="s1.playbook.escalation",
            prompt=_section_prompt(
                what=("a short 'Escalation' section for the same vendor NDA playbook"),
                facts=(
                    "any deviation from a standard position goes to Diane "
                    "Okonkwo in writing before the redline is returned; "
                    "deviations are logged in the matter file; two deviations "
                    "on the same clause in a quarter trigger a playbook "
                    "review."
                ),
                length="80-120 words",
            ),
        ),
        ContentRequest(
            name="s1.playbook.process",
            prompt=_section_prompt(
                what=(
                    "a short 'Intake and signature routing' section for the "
                    "same vendor NDA playbook"
                ),
                facts=(
                    "vendor NDAs arrive through the operations manager Anita "
                    "Bailey; the assigned associate turns redlines within "
                    "five business days; signature routing goes through the "
                    "records clerk; fully executed copies are filed in the "
                    "firm workspace under vendor-ndas."
                ),
                length="80-120 words",
            ),
        ),
        ContentRequest(
            name="s1.nda.lexipoint.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and LexiPoint Research (a legal research vendor): "
                    "numbered sections for Definitions, Permitted Use, "
                    "Exclusions, Return of Materials, and No License"
                ),
                facts=(
                    "purpose is evaluation and provision of legal research "
                    "services; do NOT include any section on term or "
                    "duration, residual knowledge, injunctive or equitable "
                    "relief, or governing law — those are appended "
                    "separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.nda.ironclad.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and Ironclad Discovery Services (an e-discovery "
                    "vendor): numbered sections for Definitions, Permitted "
                    "Use, Exclusions, Return of Materials, and No License"
                ),
                facts=(
                    "purpose is evaluation and provision of litigation "
                    "e-discovery services including data hosting; do NOT "
                    "include any section on term or duration, residual "
                    "knowledge, injunctive or equitable relief, or governing "
                    "law — those are appended separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.email.playbook-draft",
            prompt=_email_prompt(
                writer="Noah Feldstein, associate at Hartwell & Marsh",
                recipient="Diane Okonkwo, of counsel (cc Marcus Liang)",
                day="2026-03-05",
                facts=(
                    "the first draft of the Vendor NDA Playbook is attached "
                    "and in the firm workspace; it fixes the standard "
                    "positions: three-year confidentiality term and no "
                    "residual-knowledge clauses; asks Diane to review the "
                    "standard positions this week."
                ),
                tone="collegial, brisk",
            ),
        ),
        ContentRequest(
            name="s1.email.playbook-feedback",
            prompt=_email_prompt(
                writer="Diane Okonkwo, of counsel at Hartwell & Marsh",
                recipient="Noah Feldstein, associate",
                day="2026-03-05",
                facts=(
                    "the draft playbook looks right; she wants the "
                    "three-year term stated as a hard rule with Managing "
                    "Partner sign-off for anything longer, and an "
                    "escalation section added; she will do a full pass next "
                    "week."
                ),
                tone="supportive, precise",
            ),
        ),
        ContentRequest(
            name="s1.email.lexipoint-send",
            prompt=_email_prompt(
                writer="Noah Feldstein, associate at Hartwell & Marsh",
                recipient=(
                    "Ruth Calloway, account manager at LexiPoint Research "
                    "(cc Anita Bailey, operations manager)"
                ),
                day="2026-05-04",
                facts=(
                    "attached is the firm's standard mutual NDA for the "
                    "research services renewal; it carries the firm's "
                    "standard three-year confidentiality term; asks for "
                    "signature or comments by end of next week."
                ),
                tone="professional, friendly",
            ),
        ),
        ContentRequest(
            name="s1.email.lexipoint-redline",
            prompt=_email_prompt(
                writer="Ruth Calloway, account manager at LexiPoint Research",
                recipient="Noah Feldstein, associate at Hartwell & Marsh",
                day="2026-05-07",
                facts=(
                    "LexiPoint's contracting standard requires two changes "
                    "to the NDA: a five-year confidentiality term instead "
                    "of three, and a residual-knowledge clause permitting "
                    "unaided-memory use; both are described as "
                    "non-negotiable house positions."
                ),
                tone="polite but firm vendor-contracting voice",
            ),
        ),
        ContentRequest(
            name="s1.email.lexipoint-accept-term",
            prompt=_email_prompt(
                writer="Noah Feldstein, associate at Hartwell & Marsh",
                recipient="Ruth Calloway at LexiPoint Research",
                day="2026-05-13",
                facts=(
                    "revised draft attached: the firm accepted the "
                    "five-year term to keep the renewal on schedule, but "
                    "is not including a residual-knowledge clause; hopes "
                    "this splits the difference."
                ),
                tone="accommodating, slightly hurried",
            ),
        ),
        ContentRequest(
            name="s1.email.lexipoint-close",
            prompt=_email_prompt(
                writer="Ruth Calloway, account manager at LexiPoint Research",
                recipient="Noah Feldstein at Hartwell & Marsh",
                day="2026-05-15",
                facts=(
                    "LexiPoint accepts the revised draft with the five-year "
                    "term and no residuals clause; signature to follow this "
                    "week; thanks Noah for the quick turnaround."
                ),
                tone="warm, closing a deal",
            ),
        ),
        ContentRequest(
            name="s1.email.ironclad-ask",
            prompt=_email_prompt(
                writer="Stan Obrien, project manager at Ironclad Discovery Services",
                recipient=(
                    "Noah Feldstein, associate at Hartwell & Marsh "
                    "(cc Grace Adeyemi, senior paralegal)"
                ),
                day="2026-06-03",
                facts=(
                    "Ironclad reviewed the draft NDA for the discovery "
                    "services engagement; the five-year term works, but "
                    "Ironclad requires a residual-knowledge clause because "
                    "its project staff rotate across client engagements; "
                    "asks the firm to add its standard residuals language."
                ),
                tone="direct vendor voice",
            ),
        ),
        ContentRequest(
            name="s1.email.ironclad-accept",
            prompt=_email_prompt(
                writer="Noah Feldstein, associate at Hartwell & Marsh",
                recipient=(
                    "Stan Obrien at Ironclad Discovery Services "
                    "(cc Diane Okonkwo, of counsel)"
                ),
                day="2026-06-10",
                facts=(
                    "revised NDA attached with a residual-knowledge clause "
                    "added; the firm has been flexible on this language "
                    "recently and wants the discovery engagement moving; "
                    "asks for signature this week."
                ),
                tone="accommodating, practical",
            ),
        ),
        ContentRequest(
            name="s1.email.playbook-drift",
            prompt=_email_prompt(
                writer="Diane Okonkwo, of counsel at Hartwell & Marsh",
                recipient="Noah Feldstein, associate (cc Marcus Liang)",
                day="2026-06-24",
                facts=(
                    "she noticed the last two vendor NDAs (LexiPoint and "
                    "Ironclad) went out with five-year terms and, in "
                    "Ironclad's case, a residuals clause, while the March "
                    "playbook still says three years and no residuals; "
                    "asks Noah to put a playbook review on the calendar "
                    "for next quarter rather than keep deviating silently."
                ),
                tone="measured, mildly concerned",
            ),
        ),
        # S2 — Meridian acquisition fee dispute.
        ContentRequest(
            name="s2.email.invoice",
            prompt=_email_prompt(
                writer=("Carl Jensen, billing coordinator at Hartwell & Marsh"),
                recipient=(
                    "Priya Raman, COO of Meridian BioLabs (cc Eleanor "
                    "Hartwell, managing partner, and Marcus Liang)"
                ),
                day="2026-05-05",
                facts=(
                    "the April invoice for the diagnostics acquisition "
                    "matter is attached to the portal; April fees total "
                    "$41,320, materially above prior months, driven by "
                    "expanded data-room diligence during April; payment "
                    "terms net 30."
                ),
                tone="neutral billing voice",
            ),
        ),
        ContentRequest(
            name="s2.email.dispute",
            prompt=_email_prompt(
                writer="Priya Raman, COO of Meridian BioLabs",
                recipient=(
                    "Eleanor Hartwell, managing partner at Hartwell & "
                    "Marsh (cc Marcus Liang)"
                ),
                day="2026-05-08",
                facts=(
                    "Meridian disputes the April invoice; on the April 3 "
                    "budget call, Marcus agreed that expanded data-room "
                    "diligence beyond the original scope would be capped "
                    "at $12,000; the invoice shows diligence hours far "
                    "beyond that; asks for a corrected invoice and a "
                    "written scope confirmation before paying anything."
                ),
                tone="firm, professional, clearly unhappy",
            ),
        ),
        ContentRequest(
            name="s2.email.pull-time",
            prompt=_email_prompt(
                writer=("Eleanor Hartwell, managing partner at Hartwell & Marsh"),
                recipient=("Carl Jensen, billing coordinator (cc Marcus Liang)"),
                day="2026-05-12",
                facts=(
                    "she needs every April time entry on the Meridian "
                    "acquisition matter pulled today, split into entries "
                    "dated on or before April 3 and entries after April 3, "
                    "with the diligence entries flagged; the client claims "
                    "a $12,000 cap was agreed on the April 3 call and she "
                    "wants the numbers before responding."
                ),
                tone="crisp, directive",
            ),
        ),
        ContentRequest(
            name="s2.email.time-summary",
            prompt=_email_prompt(
                writer="Carl Jensen, billing coordinator at Hartwell & Marsh",
                recipient="Eleanor Hartwell, managing partner (cc Marcus Liang)",
                day="2026-05-12",
                facts=(
                    "summary of April time on the Meridian matter: the "
                    "diligence entries dated after April 3 are the bulk of "
                    "the overage; he lists that the expanded data-room "
                    "review ran April 6 through April 16 across Marcus "
                    "Liang and Peter Novak; exact figures are in the "
                    "activity export he attached to the billing folder."
                ),
                tone="factual, careful",
            ),
        ),
        ContentRequest(
            name="s2.email.resolution",
            prompt=_email_prompt(
                writer=("Eleanor Hartwell, managing partner at Hartwell & Marsh"),
                recipient=(
                    "Priya Raman, COO of Meridian BioLabs (cc Marcus "
                    "Liang, Carl Jensen)"
                ),
                day="2026-05-14",
                facts=(
                    "the firm will honor the April 3 understanding: "
                    "expanded diligence time entered after April 3 will be "
                    "capped at $12,000 and the overage credited on the May "
                    "invoice; a written scope confirmation for the "
                    "remaining phases will follow within the week; she "
                    "values the relationship."
                ),
                tone="gracious, decisive",
            ),
        ),
        ContentRequest(
            name="s2.note.resolution",
            prompt=(
                "Write a matter note (plain text, 150-220 words) recorded "
                "by managing partner Eleanor Hartwell on 2026-05-15 in the "
                "firm's practice management system on the Meridian "
                "diagnostics acquisition matter. Record: Meridian disputed "
                "the April invoice on 2026-05-08; the client's position was "
                "that a $12,000 cap on expanded data-room diligence was "
                "agreed with Marcus Liang on the April 3 budget call; "
                "billing pulled all April activities and the diligence "
                "entries dated after April 3 substantially exceeded the "
                "cap; resolution agreed 2026-05-14 — cap honored, overage "
                "credited on the May invoice, written scope confirmation "
                "to be countersigned; going forward any scope expansion on "
                "this matter needs written confirmation before work starts. "
                "No headers, no signature block."
            ),
            max_tokens=450,
        ),
        ContentRequest(
            name="s2.email.thanks",
            prompt=_email_prompt(
                writer="Priya Raman, COO of Meridian BioLabs",
                recipient="Eleanor Hartwell at Hartwell & Marsh",
                day="2026-05-20",
                facts=(
                    "she received the corrected billing treatment and the "
                    "scope confirmation; Meridian will process the April "
                    "invoice as adjusted; appreciates the quick, direct "
                    "handling."
                ),
                tone="warm, relieved",
            ),
        ),
        # S3 — Lumen license agreement, indemnity silently dropped in v3.
        ContentRequest(
            name="s3.agreement.recitals",
            prompt=_section_prompt(
                what=(
                    "the recitals and sections 1-3 (Definitions, License "
                    "Grant, Delivery and Acceptance) of a software license "
                    "and support agreement under which Lumen Software (the "
                    "Licensee) licenses a workflow platform from Fathom "
                    "Systems Inc. (the Licensor)"
                ),
                facts=(
                    "inbound license negotiated by Hartwell & Marsh for "
                    "Lumen Software; perpetual license to the platform for "
                    "internal use; delivery by secure download; 30-day "
                    "acceptance window. Do NOT include fees, support, "
                    "indemnification, or general provisions — drafted "
                    "separately."
                ),
                length="250-350 words",
            ),
            max_tokens=650,
        ),
        ContentRequest(
            name="s3.agreement.fees.v1",
            prompt=_section_prompt(
                what=(
                    "section 4 (Fees and Payment) of the same software "
                    "license agreement"
                ),
                facts=(
                    "one-time license fee of $240,000 payable on "
                    "acceptance; annual support fee of $48,000; net 45; "
                    "late amounts accrue 1% monthly."
                ),
                length="90-130 words",
            ),
        ),
        ContentRequest(
            name="s3.agreement.fees.v2",
            prompt=_section_prompt(
                what=(
                    "section 4 (Fees and Payment) of the same software "
                    "license agreement, revised after licensee comments"
                ),
                facts=(
                    "license fee of $240,000 payable in two installments — "
                    "$140,000 on acceptance and $100,000 at ninety days; "
                    "annual support fee of $48,000 with a 3% annual cap on "
                    "increases; net 45; late amounts accrue 1% monthly."
                ),
                length="100-150 words",
            ),
        ),
        ContentRequest(
            name="s3.agreement.support",
            prompt=_section_prompt(
                what=(
                    "sections 5-7 (Support Services, Service Levels, Term "
                    "and Termination) of the same software license "
                    "agreement"
                ),
                facts=(
                    "business-hours support with four-hour response for "
                    "severity 1; quarterly updates included; either party "
                    "may terminate support on 90 days' notice after year "
                    "two; license survives termination of support."
                ),
                length="180-260 words",
            ),
            max_tokens=520,
        ),
        ContentRequest(
            name="s3.agreement.general",
            prompt=_section_prompt(
                what=(
                    "sections 10-12 (Limitation of Liability, "
                    "Confidentiality, General Provisions) of the same "
                    "software license agreement"
                ),
                facts=(
                    "liability capped at fees paid in the prior twelve "
                    "months except for indemnification obligations and "
                    "confidentiality breaches; California law; disputes in "
                    "San Francisco County; no assignment without consent."
                ),
                length="180-260 words",
            ),
            max_tokens=520,
        ),
        ContentRequest(
            name="s3.email.v1-send",
            prompt=_email_prompt(
                writer="Marcus Liang, senior associate at Hartwell & Marsh",
                recipient=(
                    "June Akana, general counsel of Lumen Software "
                    "(cc Peter Novak, paralegal)"
                ),
                day="2026-03-31",
                facts=(
                    "first draft of the Fathom Systems license and support "
                    "agreement is attached and in the workspace; it "
                    "includes the licensor IP indemnity Lumen asked for; "
                    "asks June for comments in two weeks."
                ),
                tone="confident, service-oriented",
            ),
        ),
        ContentRequest(
            name="s3.email.client-comments",
            prompt=_email_prompt(
                writer="June Akana, general counsel of Lumen Software",
                recipient="Marcus Liang at Hartwell & Marsh",
                day="2026-04-16",
                facts=(
                    "comments on the license draft: split the license fee "
                    "into two installments, cap support fee increases, and "
                    "tighten the severity-1 response time; the "
                    "indemnification article is exactly what she wants — "
                    "keep it as drafted."
                ),
                tone="engaged, specific",
            ),
        ),
        ContentRequest(
            name="s3.email.v2-send",
            prompt=_email_prompt(
                writer="Marcus Liang, senior associate at Hartwell & Marsh",
                recipient="June Akana, general counsel of Lumen Software",
                day="2026-04-21",
                facts=(
                    "revised draft attached reflecting all her comments on "
                    "fees and support; nothing else moved; ready to send "
                    "to Fathom's counsel."
                ),
                tone="brisk, reassuring",
            ),
        ),
        ContentRequest(
            name="s3.email.licensor-pushback",
            prompt=_email_prompt(
                writer=(
                    "Caleb Fontaine, partner at Pacific Counsel Group, "
                    "counsel to Fathom Systems"
                ),
                recipient=(
                    "Marcus Liang at Hartwell & Marsh (cc June Akana, Lumen Software)"
                ),
                day="2026-05-19",
                facts=(
                    "Fathom accepts the fee and support revisions but "
                    "cannot accept the uncapped licensor IP indemnity in "
                    "article 9; asks Hartwell to revisit that article "
                    "before the signing draft; proposes a call Thursday."
                ),
                tone="courteous opposing-counsel pressure",
            ),
        ),
        ContentRequest(
            name="s3.email.ready-to-sign",
            prompt=_email_prompt(
                writer="June Akana, general counsel of Lumen Software",
                recipient="Marcus Liang at Hartwell & Marsh",
                day="2026-06-09",
                facts=(
                    "her board approved the Fathom license at the June "
                    "meeting; asks whether the draft in the workspace is "
                    "final and whether anything substantive changed since "
                    "her April comments; wants to sign this month."
                ),
                tone="upbeat, trusting",
            ),
        ),
        ContentRequest(
            name="s3.email.final-confirm",
            prompt=_email_prompt(
                writer="Marcus Liang, senior associate at Hartwell & Marsh",
                recipient="June Akana, general counsel of Lumen Software",
                day="2026-06-09",
                facts=(
                    "the current draft in the workspace is the signing "
                    "version; the changes since April were conforming "
                    "cross-reference and formatting cleanup after a call "
                    "with Fathom's counsel; signature packets can go out "
                    "this week."
                ),
                tone="breezy, confident",
            ),
        ),
        # S4 — Cascadia relationship sours to termination.
        ContentRequest(
            name="s4.email.concern1",
            prompt=_email_prompt(
                writer="Tom Hollis, owner of Cascadia Outfitters",
                recipient="Sofia Ramirez, associate at Hartwell & Marsh",
                day="2026-04-15",
                facts=(
                    "he is checking in on the supplier dispute; it has "
                    "been quiet for a few weeks and the last update said "
                    "the demand letter would go out by early April; asks "
                    "where things stand and when he will see movement."
                ),
                tone="friendly but pointed",
            ),
        ),
        ContentRequest(
            name="s4.email.reassure",
            prompt=_email_prompt(
                writer="Sofia Ramirez, associate at Hartwell & Marsh",
                recipient="Tom Hollis, owner of Cascadia Outfitters",
                day="2026-04-15",
                facts=(
                    "apologizes for the quiet stretch; the demand letter "
                    "went through partner review and goes out this week; "
                    "she will send a written status memo and set a call "
                    "for next week."
                ),
                tone="apologetic, energetic",
            ),
        ),
        ContentRequest(
            name="s4.email.concern2",
            prompt=_email_prompt(
                writer="Tom Hollis, owner of Cascadia Outfitters",
                recipient=(
                    "Sofia Ramirez at Hartwell & Marsh (cc Samuel Marsh, partner)"
                ),
                day="2026-04-24",
                facts=(
                    "the promised call last Thursday never got scheduled "
                    "and nobody returned his message Monday; he also has "
                    "questions about the March invoice, which billed more "
                    "than he expected for a quiet month; asks the partner "
                    "to get involved."
                ),
                tone="frustrated, still civil",
            ),
        ),
        ContentRequest(
            name="s4.email.concern3",
            prompt=_email_prompt(
                writer="Tom Hollis, owner of Cascadia Outfitters",
                recipient=(
                    "Samuel Marsh, partner at Hartwell & Marsh (cc Sofia Ramirez)"
                ),
                day="2026-05-06",
                facts=(
                    "the supplier's counsel made a settlement overture two "
                    "weeks ago and he still has not seen the firm's "
                    "written assessment; fees keep climbing while the "
                    "case sits; he wants a plan in writing by Friday — "
                    "strategy, timeline, and budget — or a serious "
                    "conversation about the engagement."
                ),
                tone="openly frustrated, direct",
            ),
        ),
        ContentRequest(
            name="s4.email.cold",
            prompt=_email_prompt(
                writer="Tom Hollis, owner of Cascadia Outfitters",
                recipient=(
                    "Samuel Marsh, partner at Hartwell & Marsh (cc "
                    "Eleanor Hartwell, managing partner)"
                ),
                day="2026-05-20",
                facts=(
                    "he acknowledges the plan received last week; requests "
                    "a complete billing summary for the matter to date and "
                    "copies of the case file index, as Cascadia is "
                    "evaluating its options for the dispute going forward; "
                    "asks that future communications be in writing."
                ),
                tone="cold, formal, businesslike",
            ),
        ),
        ContentRequest(
            name="s4.email.terminate",
            prompt=_email_prompt(
                writer="Tom Hollis, owner of Cascadia Outfitters",
                recipient=(
                    "Eleanor Hartwell, managing partner at Hartwell & "
                    "Marsh (cc Samuel Marsh)"
                ),
                day="2026-05-27",
                facts=(
                    "Cascadia is terminating the engagement on the "
                    "supplier dispute effective June 5, 2026; new counsel "
                    "will contact the firm for the file; he asks for a "
                    "final invoice through the effective date and return "
                    "of any unearned retainer; the decision is final and "
                    "reflects months of slow communication."
                ),
                tone="final, controlled, unemotional",
            ),
        ),
        ContentRequest(
            name="s4.email.acknowledge",
            prompt=_email_prompt(
                writer=("Eleanor Hartwell, managing partner at Hartwell & Marsh"),
                recipient=(
                    "Tom Hollis, owner of Cascadia Outfitters (cc Samuel Marsh)"
                ),
                day="2026-05-28",
                facts=(
                    "she acknowledges the termination effective June 5, "
                    "2026; the firm will cooperate fully with successor "
                    "counsel, transfer the file promptly on request, "
                    "refund the unearned retainer balance, and send a "
                    "final invoice; a formal disengagement letter will "
                    "follow; she regrets the relationship ended this way."
                ),
                tone="professional, gracious, brief",
            ),
        ),
        ContentRequest(
            name="s4.email.transition",
            prompt=_email_prompt(
                writer=("Eleanor Hartwell, managing partner at Hartwell & Marsh"),
                recipient=(
                    "Samuel Marsh and Sofia Ramirez (cc Grace Adeyemi, "
                    "senior paralegal)"
                ),
                day="2026-05-28",
                facts=(
                    "Cascadia terminated effective June 5; Samuel stops "
                    "all substantive work now except deadline protection; "
                    "Grace prepares the file index and transfer package; "
                    "billing closes out time through June 5 and calculates "
                    "the trust refund; the matter closes in the system "
                    "once the disengagement letter goes out; she wants a "
                    "short lessons-learned discussion at the next partner "
                    "lunch."
                ),
                tone="calm, operational",
            ),
        ),
        ContentRequest(
            name="s4.letter.body",
            prompt=(
                "Write the body paragraphs (no letterhead, no date line, no "
                "signature block) of a formal disengagement letter from "
                "Eleanor Hartwell, managing partner of Hartwell & Marsh "
                "LLP, to Tom Hollis, owner of Cascadia Outfitters, "
                "confirming termination of the firm's engagement on the "
                "supplier dispute matter effective June 5, 2026. Cover: "
                "confirmation of termination per his May 27 instruction; "
                "the firm will take no further action after the effective "
                "date except protecting imminent deadlines through that "
                "date; the complete file will be transferred to successor "
                "counsel within ten business days of a written request; "
                "the unearned trust balance will be refunded with the "
                "final accounting; a final invoice through the effective "
                "date follows under the engagement agreement; the client "
                "should calendar the supplier dispute's limitation "
                "periods. Formal, courteous, 180-260 words."
            ),
            max_tokens=520,
        ),
        ContentRequest(
            name="s4.note.closeout",
            prompt=(
                "Write a matter close-out note (plain text, 120-180 words) "
                "recorded by Grace Adeyemi, senior paralegal at Hartwell & "
                "Marsh, on 2026-06-04 on the Cascadia supplier dispute "
                "matter. Record: client terminated by email 2026-05-27 "
                "effective 2026-06-05; disengagement letter sent 2026-06-01; "
                "matter closed in the system 2026-06-04; file index and "
                "transfer package staged with the records clerk pending "
                "successor counsel's written request; final invoice "
                "issued through the effective date; trust refund "
                "processed with the final accounting; all internal "
                "deadlines released after limitations dates were served "
                "on the client in the disengagement letter. No headers, "
                "no signature."
            ),
            max_tokens=400,
        ),
        # S5 — Arroyo hearing continued three times.
        ContentRequest(
            name="s5.email.set1",
            prompt=_email_prompt(
                writer=(
                    "Dawn McAllister, courtroom clerk, Alameda County Superior Court"
                ),
                recipient=(
                    "Grace Adeyemi, senior paralegal at Hartwell & Marsh "
                    "(cc Samuel Marsh, counsel for plaintiff Arroyo "
                    "Construction)"
                ),
                day="2026-03-16",
                facts=(
                    "in Arroyo Construction v. Fruitvale Partners LLC, the "
                    "motion hearing is set for Tuesday April 28, 2026 at "
                    "10:00 a.m. in Department 511; courtesy copies due "
                    "five court days prior; remote appearance available "
                    "through the court's platform."
                ),
                tone="neutral court-clerk register",
            ),
        ),
        ContentRequest(
            name="s5.email.reset1",
            prompt=_email_prompt(
                writer=(
                    "Dawn McAllister, courtroom clerk, Alameda County Superior Court"
                ),
                recipient=("Grace Adeyemi at Hartwell & Marsh (cc Samuel Marsh)"),
                day="2026-04-17",
                facts=(
                    "due to a courtroom reassignment in Department 511, "
                    "the April 28 motion hearing in Arroyo Construction v. "
                    "Fruitvale Partners is continued to Wednesday May 20, "
                    "2026 at 10:00 a.m.; all briefing deadlines track the "
                    "new date; an amended notice will issue."
                ),
                tone="neutral court-clerk register",
            ),
        ),
        ContentRequest(
            name="s5.email.stip",
            prompt=_email_prompt(
                writer=(
                    "Victor Crane, partner at Crane & Whitaker LLP, "
                    "counsel for Fruitvale Partners"
                ),
                recipient=(
                    "Samuel Marsh, partner at Hartwell & Marsh (cc Grace Adeyemi)"
                ),
                day="2026-05-12",
                facts=(
                    "his lead declarant has a medical conflict the week "
                    "of May 18; proposes stipulating to continue the "
                    "May 20 hearing in Arroyo v. Fruitvale roughly four "
                    "weeks; offers to prepare the stipulation and proposed "
                    "order if Hartwell agrees."
                ),
                tone="courteous opposing counsel",
            ),
        ),
        ContentRequest(
            name="s5.email.stip-agree",
            prompt=_email_prompt(
                writer="Samuel Marsh, partner at Hartwell & Marsh",
                recipient=("Victor Crane at Crane & Whitaker (cc Grace Adeyemi)"),
                day="2026-05-12",
                facts=(
                    "he agrees to the continuance as a professional "
                    "courtesy provided discovery cutoffs are unaffected; "
                    "asks Victor to circulate the stipulation today so it "
                    "reaches the clerk this week."
                ),
                tone="brisk, professional",
            ),
        ),
        ContentRequest(
            name="s5.email.reset2",
            prompt=_email_prompt(
                writer=(
                    "Dawn McAllister, courtroom clerk, Alameda County Superior Court"
                ),
                recipient=("Grace Adeyemi at Hartwell & Marsh (cc Samuel Marsh)"),
                day="2026-05-13",
                facts=(
                    "the stipulated continuance in Arroyo Construction v. "
                    "Fruitvale Partners is granted; the motion hearing is "
                    "reset to Thursday June 18, 2026 at 10:00 a.m. in "
                    "Department 511; the signed order will be served on "
                    "all parties."
                ),
                tone="neutral court-clerk register",
            ),
        ),
    )


def author_content_offline(fake: Callable[[ContentRequest], str]) -> dict[str, str]:
    """Deterministic stand-in texts for offline tests."""

    return {request.name: fake(request) for request in content_requests()}


async def author_content(
    *, store: ContentStore, lm: LanguageModel, model: str, seed: Seed
) -> dict[str, str]:
    texts: dict[str, str] = {}
    for request in content_requests():
        texts[request.name] = await store.author(
            request.prompt,
            lm=lm,
            model=model,
            seed=content_seed(seed, request.name),
            max_tokens=request.max_tokens,
        )
    return texts


def content_seed(seed: Seed, name: str) -> int:
    return derive_seed(seed, *_CONTENT_MODEL_PATH, name)


def missing_content(
    store: ContentStore, *, model: str, seed: Seed
) -> tuple[ContentRequest, ...]:
    return tuple(
        request
        for request in content_requests()
        if store.get(request.prompt, model=model, seed=content_seed(seed, request.name))
        is None
    )


def _entity(person_id: str) -> str:
    return person_id.partition("-")[2]


def _at(hour: int, minute: int = 0) -> int:
    return hour * 3600 + minute * 60


def _day_start(day: str) -> int:
    return (date.fromisoformat(day) - WINDOW.date_of(0)).days * 86_400


def _playbook(texts: Mapping[str, str], *, revision: int) -> str:
    parts = [
        f"# {PLAYBOOK_TITLE}",
        "",
        texts["s1.playbook.intro"],
        "",
        "## Standard positions",
        "",
        f"1. **Term.** {PLAYBOOK_TERM_STANDARD}",
        f"2. **Residuals.** {PLAYBOOK_RESIDUALS_STANDARD}",
        "3. **Injunctive relief.** Keep the mutual equitable-relief "
        "carve-out; either party may seek injunctive relief without "
        "posting bond.",
        "4. **Governing law.** California, venue in Alameda County.",
    ]
    if revision >= 2:
        parts += ["", "## Escalation", "", texts["s1.playbook.escalation"]]
    if revision >= 3:
        parts += [
            "",
            "## Intake and signature routing",
            "",
            texts["s1.playbook.process"],
        ]
    return "\n".join(parts) + "\n"


def _nda(
    texts: Mapping[str, str],
    *,
    title: str,
    body_key: str,
    term: str,
    residuals: bool,
) -> str:
    parts = [
        f"# {title.removesuffix(' (Draft)')}",
        "",
        texts[body_key],
        "",
        "## Term",
        "",
        term,
    ]
    if residuals:
        parts += ["", "## Residual Knowledge", "", NDA_RESIDUALS_CLAUSE]
    parts += [
        "",
        "## Equitable Relief",
        "",
        NDA_INJUNCTIVE_CLAUSE,
        "",
        "## Governing Law",
        "",
        "This Agreement is governed by California law; venue lies in Alameda County.",
    ]
    return "\n".join(parts) + "\n"


def _lumen_agreement(
    texts: Mapping[str, str], *, fees_key: str, indemnity: bool
) -> str:
    parts = [
        "# Software License and Support Agreement",
        "",
        "**Licensor:** Fathom Systems Inc.  ",
        "**Licensee:** Lumen Software",
        "",
        texts["s3.agreement.recitals"],
        "",
        texts[fees_key],
        "",
        texts["s3.agreement.support"],
        "",
        "## 9. Indemnification",
        "",
        LICENSEE_INDEMNITY_PARAGRAPH,
    ]
    if indemnity:
        parts += ["", INDEMNITY_PARAGRAPH]
    parts += ["", texts["s3.agreement.general"]]
    return "\n".join(parts) + "\n"


def _cascadia_letter(texts: Mapping[str, str]) -> str:
    return (
        f"# {CASCADIA_LETTER_TITLE}\n\n"
        "June 1, 2026\n\n"
        "Tom Hollis\nCascadia Outfitters\n\n"
        "Re: Termination of engagement — supplier dispute "
        "(effective June 5, 2026)\n\n"
        f"{texts['s4.letter.body']}\n\n"
        "Very truly yours,\n\nEleanor Hartwell\nManaging Partner, "
        "Hartwell & Marsh LLP\n"
    )


_Beat = Callable[[IdMinter, list[TimedDraft]], None]


class StorylineDirector:
    """Realizes the beat calendar day by day against the shared minter.

    ``drafts_for`` must be called in ascending date order: later beats
    reference ids (threads, documents, calendar events) minted by earlier
    ones through the internal ref table.
    """

    def __init__(self, *, genesis: HartwellGenesis, texts: Mapping[str, str]) -> None:
        missing = [
            request.name for request in content_requests() if request.name not in texts
        ]
        if missing:
            raise ConfigError(f"storyline texts missing: {missing}")
        self._texts = dict(texts)
        self._matters_channel = next(
            event.payload.conversation_id
            for event in genesis.events
            if event.payload.kind == "chat.conversation.created"
            and event.payload.name == "#matters"
        )
        self._refs: dict[str, str] = {}
        self._beats: dict[str, list[tuple[int, _Beat]]] = {}
        self._register_s1()
        self._register_s2()
        self._register_s3()
        self._register_s4()
        self._register_s5()
        workdays = {WINDOW.iso_date(index) for index in WINDOW.workdays()}
        strays = sorted(set(self._beats) - workdays)
        if strays:
            raise ConfigError(f"storyline beats on non-workdays: {strays}")

    @property
    def dates(self) -> tuple[str, ...]:
        return tuple(sorted(self._beats))

    def drafts_for(self, day: str, minter: IdMinter) -> tuple[TimedDraft, ...]:
        drafts: list[TimedDraft] = []
        for _, beat in sorted(self._beats.get(day, ()), key=lambda pair: pair[0]):
            beat(minter, drafts)
        return tuple(drafts)

    def _on(self, day: str, clock: int, beat: _Beat) -> None:
        self._beats.setdefault(day, []).append((clock, beat))

    # Draft constructors. Each mints ids at realize time and records them
    # under symbolic refs for later beats.

    def _email(
        self,
        minter: IdMinter,
        drafts: list[TimedDraft],
        *,
        at: int,
        sender: str,
        to: tuple[str, ...],
        cc: tuple[str, ...] = (),
        subject: str,
        text: str,
        thread: str,
        reply: bool,
        attach: str | None = None,
        attach_name: str | None = None,
    ) -> None:
        message_id = minter.mint("msg")
        if reply:
            thread_id = self._refs[f"t:{thread}"]
            in_reply_to = self._refs[f"m:{thread}"]
        else:
            thread_id = minter.mint("thr")
            self._refs[f"t:{thread}"] = thread_id
            in_reply_to = None
        self._refs[f"m:{thread}"] = message_id
        attachments: tuple[Attachment, ...] = ()
        if attach is not None and attach_name is not None:
            attachments = (
                Attachment(
                    filename=attach_name,
                    media_type="text/markdown",
                    document_id=self._refs[f"d:{attach}"],
                ),
            )
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(sender),
                payload=EmailMessagePayload(
                    kind="email.message",
                    message_id=message_id,
                    thread_id=thread_id,
                    in_reply_to=in_reply_to,
                    sender=sender,
                    to=to,
                    cc=cc,
                    subject=subject,
                    body=text,
                    attachments=attachments,
                ),
            )
        )

    def _chat(
        self,
        minter: IdMinter,
        drafts: list[TimedDraft],
        *,
        at: int,
        sender: str,
        body: str,
        ref: str | None = None,
        reply_ref: str | None = None,
    ) -> None:
        message_id = minter.mint("chm")
        if ref is not None:
            self._refs[f"ch:{ref}"] = message_id
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(sender),
                payload=ChatMessagePayload(
                    kind="chat.message",
                    chat_message_id=message_id,
                    conversation_id=self._matters_channel,
                    reply_to=(
                        self._refs[f"ch:{reply_ref}"] if reply_ref is not None else None
                    ),
                    sender=sender,
                    body=body,
                ),
            )
        )

    def _react(
        self,
        drafts: list[TimedDraft],
        *,
        at: int,
        ref: str,
        person: str,
        emoji: str,
    ) -> None:
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(person),
                payload=ChatReactionAddedPayload(
                    kind="chat.reaction.added",
                    conversation_id=self._matters_channel,
                    chat_message_id=self._refs[f"ch:{ref}"],
                    person_id=person,
                    emoji=emoji,
                ),
            )
        )

    def _doc(
        self,
        minter: IdMinter,
        drafts: list[TimedDraft],
        *,
        at: int,
        ref: str,
        author: str,
        title: str,
        path: str,
        content: str,
    ) -> None:
        document_id = minter.mint("doc")
        self._refs[f"d:{ref}"] = document_id
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(author),
                payload=DocumentCreatedPayload(
                    kind="document.created",
                    document_id=document_id,
                    author=author,
                    title=title,
                    path=path,
                    location="repository",
                    content_format="markdown",
                    content=content,
                ),
            )
        )

    def _revise(
        self,
        drafts: list[TimedDraft],
        *,
        at: int,
        ref: str,
        revision: int,
        author: str,
        content: str,
        summary: str,
    ) -> None:
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(author),
                payload=DocumentRevisedPayload(
                    kind="document.revised",
                    document_id=self._refs[f"d:{ref}"],
                    revision=revision,
                    author=author,
                    content=content,
                    change_summary=summary,
                ),
            )
        )

    def _time(
        self,
        drafts: list[TimedDraft],
        *,
        at: int,
        person: str,
        ticket: str,
        minutes: int,
        note: str,
    ) -> None:
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(person),
                payload=TimeLoggedPayload(
                    kind="work.time.logged",
                    person_id=person,
                    ticket_id=ticket,
                    minutes=minutes,
                    note=note,
                ),
            )
        )

    def _note(
        self,
        drafts: list[TimedDraft],
        *,
        at: int,
        actor: str,
        ticket: str,
        body: str,
    ) -> None:
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(actor),
                payload=TicketCommentedPayload(
                    kind="ticket.commented",
                    ticket_id=ticket,
                    actor=actor,
                    body=body,
                ),
            )
        )

    def _calendar(
        self,
        minter: IdMinter,
        drafts: list[TimedDraft],
        *,
        at: int,
        ref: str,
        organizer: str,
        title: str,
        day: str,
        start_clock: int,
        minutes: int,
        attendees: tuple[str, ...],
        description: str,
    ) -> None:
        calendar_event_id = minter.mint("cal")
        self._refs[f"c:{ref}"] = calendar_event_id
        start = _day_start(day) + start_clock
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(organizer),
                payload=CalendarEventScheduledPayload(
                    kind="calendar.event.scheduled",
                    calendar_event_id=calendar_event_id,
                    organizer=organizer,
                    title=title,
                    start=SimTime(start),
                    end=SimTime(start + minutes * 60),
                    attendees=attendees,
                    description=description,
                ),
            )
        )

    def _calendar_update(
        self,
        drafts: list[TimedDraft],
        *,
        at: int,
        ref: str,
        actor: str,
        old: str,
        new: str,
    ) -> None:
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(actor),
                payload=CalendarEventUpdatedPayload(
                    kind="calendar.event.updated",
                    calendar_event_id=self._refs[f"c:{ref}"],
                    actor=actor,
                    changes=(FieldChange(field="status", old=old, new=new),),
                ),
            )
        )

    # S1 — vendor NDA standard drift.

    def _register_s1(self) -> None:
        texts = self._texts

        def playbook_created(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._doc(
                minter,
                drafts,
                at=_at(10, 10),
                ref="s1.playbook",
                author=_NF,
                title=PLAYBOOK_TITLE,
                path="/firm/playbooks/vendor-nda-playbook.md",
                content=_playbook(texts, revision=1),
            )

        def playbook_sent(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 40),
                sender=_NF,
                to=(_DO,),
                cc=(_ML,),
                subject="Vendor NDA playbook — first draft",
                text=texts["s1.email.playbook-draft"],
                thread="s1.playbook",
                reply=False,
                attach="s1.playbook",
                attach_name="vendor-nda-playbook.md",
            )

        def playbook_feedback(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(15, 20),
                sender=_DO,
                to=(_NF,),
                subject="Re: Vendor NDA playbook — first draft",
                text=texts["s1.email.playbook-feedback"],
                thread="s1.playbook",
                reply=True,
            )

        self._on("2026-03-05", _at(10, 10), playbook_created)
        self._on("2026-03-05", _at(10, 40), playbook_sent)
        self._on("2026-03-05", _at(15, 20), playbook_feedback)

        def playbook_v2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(11, 5),
                ref="s1.playbook",
                revision=2,
                author=_DO,
                content=_playbook(texts, revision=2),
                summary="Tightened the standard positions and added the "
                "escalation section after partner review.",
            )

        self._on("2026-03-12", _at(11, 5), playbook_v2)

        def playbook_v3(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(14, 30),
                ref="s1.playbook",
                revision=3,
                author=_PN,
                content=_playbook(texts, revision=3),
                summary="Added intake and signature-routing process notes.",
            )

        self._on("2026-03-25", _at(14, 30), playbook_v3)

        def lexipoint_v1(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._doc(
                minter,
                drafts,
                at=_at(9, 50),
                ref="s1.lexipoint",
                author=_NF,
                title=LEXIPOINT_NDA_TITLE,
                path="/firm/vendor-ndas/mutual-nda-lexipoint.md",
                content=_nda(
                    texts,
                    title=LEXIPOINT_NDA_TITLE,
                    body_key="s1.nda.lexipoint.body",
                    term=NDA_TERM_THREE,
                    residuals=False,
                ),
            )

        def lexipoint_sent(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 20),
                sender=_NF,
                to=(_RUTH,),
                cc=(_AB,),
                subject="Mutual NDA for the research services renewal",
                text=texts["s1.email.lexipoint-send"],
                thread="s1.lexipoint",
                reply=False,
                attach="s1.lexipoint",
                attach_name="mutual-nda-lexipoint.md",
            )

        self._on("2026-05-04", _at(9, 50), lexipoint_v1)
        self._on("2026-05-04", _at(10, 20), lexipoint_sent)

        def lexipoint_redline(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(13, 40),
                sender=_RUTH,
                to=(_NF,),
                subject="Re: Mutual NDA for the research services renewal",
                text=texts["s1.email.lexipoint-redline"],
                thread="s1.lexipoint",
                reply=True,
            )

        self._on("2026-05-07", _at(13, 40), lexipoint_redline)

        def lexipoint_v2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(11, 15),
                ref="s1.lexipoint",
                revision=2,
                author=_NF,
                content=_nda(
                    texts,
                    title=LEXIPOINT_NDA_TITLE,
                    body_key="s1.nda.lexipoint.body",
                    term=NDA_TERM_FIVE,
                    residuals=False,
                ),
                summary="Accepted the counterparty's term revision after "
                "the renewal call.",
            )

        def lexipoint_v2_sent(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(11, 35),
                sender=_NF,
                to=(_RUTH,),
                subject="Re: Mutual NDA for the research services renewal",
                text=texts["s1.email.lexipoint-accept-term"],
                thread="s1.lexipoint",
                reply=True,
                attach="s1.lexipoint",
                attach_name="mutual-nda-lexipoint.md",
            )

        self._on("2026-05-13", _at(11, 15), lexipoint_v2)
        self._on("2026-05-13", _at(11, 35), lexipoint_v2_sent)

        def lexipoint_close(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(9, 55),
                sender=_RUTH,
                to=(_NF,),
                subject="Re: Mutual NDA for the research services renewal",
                text=texts["s1.email.lexipoint-close"],
                thread="s1.lexipoint",
                reply=True,
            )

        self._on("2026-05-15", _at(9, 55), lexipoint_close)

        def ironclad_v1(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._doc(
                minter,
                drafts,
                at=_at(15, 5),
                ref="s1.ironclad",
                author=_NF,
                title=IRONCLAD_NDA_TITLE,
                path="/firm/vendor-ndas/mutual-nda-ironclad.md",
                content=_nda(
                    texts,
                    title=IRONCLAD_NDA_TITLE,
                    body_key="s1.nda.ironclad.body",
                    term=NDA_TERM_FIVE,
                    residuals=False,
                ),
            )

        self._on("2026-05-27", _at(15, 5), ironclad_v1)

        def ironclad_ask(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 45),
                sender=_STAN,
                to=(_NF,),
                cc=(_GA,),
                subject="NDA — residuals language",
                text=texts["s1.email.ironclad-ask"],
                thread="s1.ironclad",
                reply=False,
            )

        self._on("2026-06-03", _at(10, 45), ironclad_ask)

        def ironclad_v2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(14, 10),
                ref="s1.ironclad",
                revision=2,
                author=_NF,
                content=_nda(
                    texts,
                    title=IRONCLAD_NDA_TITLE,
                    body_key="s1.nda.ironclad.body",
                    term=NDA_TERM_FIVE,
                    residuals=True,
                ),
                summary="Conformed the confidentiality article to the agreed markup.",
            )

        def ironclad_v2_sent(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(14, 30),
                sender=_NF,
                to=(_STAN,),
                cc=(_DO,),
                subject="Re: NDA — residuals language",
                text=texts["s1.email.ironclad-accept"],
                thread="s1.ironclad",
                reply=True,
                attach="s1.ironclad",
                attach_name="mutual-nda-ironclad.md",
            )

        self._on("2026-06-10", _at(14, 10), ironclad_v2)
        self._on("2026-06-10", _at(14, 30), ironclad_v2_sent)

        def drift_flagged(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(9, 35),
                sender=_DO,
                to=(_NF,),
                cc=(_ML,),
                subject="Vendor NDA playbook vs. practice",
                text=texts["s1.email.playbook-drift"],
                thread="s1.drift",
                reply=False,
            )

        self._on("2026-06-24", _at(9, 35), drift_flagged)

    # S2 — Meridian acquisition fee dispute.

    def _register_s2(self) -> None:
        texts = self._texts

        def budget_call(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._calendar(
                minter,
                drafts,
                at=_at(9, 20),
                ref="s2.call",
                organizer=_ML,
                title="Meridian — diligence scope and budget call",
                day="2026-04-03",
                start_clock=_at(13, 0),
                minutes=45,
                attendees=(_ML, _EH, _PN, _PRIYA),
                description="Scope and budget for the expanded data-room "
                "diligence on the diagnostics acquisition.",
            )

        self._on("2026-04-01", _at(9, 20), budget_call)

        def call_time(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._time(
                drafts,
                at=_at(15, 30),
                person=_ML,
                ticket=S2_TICKET,
                minutes=45,
                note="Prepare for and attend diligence scope and budget "
                "call with client (Meridian diagnostics acquisition).",
            )

        self._on("2026-04-03", _at(15, 30), call_time)

        spike: tuple[tuple[str, int, str, int, str], ...] = (
            (
                "2026-04-06",
                _at(17, 40),
                _ML,
                130,
                "Expanded data room review, tranche 2 — regulatory files "
                "(Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-06",
                _at(18, 5),
                _PN,
                95,
                "Index and stage tranche 2 data room documents (Meridian "
                "diagnostics acquisition).",
            ),
            (
                "2026-04-08",
                _at(17, 55),
                _ML,
                145,
                "Continue expanded diligence review per revised scope — "
                "supplier agreements (Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-10",
                _at(18, 10),
                _ML,
                160,
                "Diligence review, tranche 3; scope now well beyond the "
                "original estimate (Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-10",
                _at(18, 25),
                _PN,
                120,
                "Data room QC and privilege screen, tranche 3 (Meridian "
                "diagnostics acquisition).",
            ),
            (
                "2026-04-14",
                _at(17, 45),
                _ML,
                150,
                "Expanded diligence — IP assignments; flag budget overrun "
                "for billing review (Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-16",
                _at(18, 0),
                _ML,
                90,
                "Complete diligence memo; unbudgeted hours flagged for the "
                "April prebill (Meridian diagnostics acquisition).",
            ),
        )
        for day, clock, person, minutes, note in spike:

            def entry(
                minter: IdMinter,
                drafts: list[TimedDraft],
                clock: int = clock,
                person: str = person,
                minutes: int = minutes,
                note: str = note,
            ) -> None:
                self._time(
                    drafts,
                    at=clock,
                    person=person,
                    ticket=S2_TICKET,
                    minutes=minutes,
                    note=note,
                )

            self._on(day, clock, entry)

        def invoice(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 15),
                sender=_CJ,
                to=(_PRIYA,),
                cc=(_EH, _ML),
                subject="Hartwell & Marsh — April invoice, Meridian "
                "diagnostics acquisition",
                text=texts["s2.email.invoice"],
                thread="s2.invoice",
                reply=False,
            )

        self._on("2026-05-05", _at(10, 15), invoice)

        def dispute(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(9, 40),
                sender=_PRIYA,
                to=(_EH,),
                cc=(_ML,),
                subject="Re: Hartwell & Marsh — April invoice, Meridian "
                "diagnostics acquisition",
                text=texts["s2.email.dispute"],
                thread="s2.invoice",
                reply=True,
            )

        self._on("2026-05-08", _at(9, 40), dispute)

        def pull_time(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(8, 55),
                sender=_EH,
                to=(_CJ,),
                cc=(_ML,),
                subject="Meridian April time — need it split today",
                text=texts["s2.email.pull-time"],
                thread="s2.internal",
                reply=False,
            )

        def time_summary(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(13, 20),
                sender=_CJ,
                to=(_EH,),
                cc=(_ML,),
                subject="Re: Meridian April time — need it split today",
                text=texts["s2.email.time-summary"],
                thread="s2.internal",
                reply=True,
            )

        self._on("2026-05-12", _at(8, 55), pull_time)
        self._on("2026-05-12", _at(13, 20), time_summary)

        def resolution(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(11, 30),
                sender=_EH,
                to=(_PRIYA,),
                cc=(_ML, _CJ),
                subject="Re: Hartwell & Marsh — April invoice, Meridian "
                "diagnostics acquisition",
                text=texts["s2.email.resolution"],
                thread="s2.invoice",
                reply=True,
            )

        self._on("2026-05-14", _at(11, 30), resolution)

        def clio_note(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._note(
                drafts,
                at=_at(14, 45),
                actor=_EH,
                ticket=S2_TICKET,
                body=texts["s2.note.resolution"],
            )

        self._on("2026-05-15", _at(14, 45), clio_note)

        def thanks(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 5),
                sender=_PRIYA,
                to=(_EH,),
                subject="Re: Hartwell & Marsh — April invoice, Meridian "
                "diagnostics acquisition",
                text=texts["s2.email.thanks"],
                thread="s2.invoice",
                reply=True,
            )

        self._on("2026-05-20", _at(10, 5), thanks)

    # S3 — Lumen agreement drops its licensor indemnity in v3.

    def _register_s3(self) -> None:
        texts = self._texts

        def v1(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._doc(
                minter,
                drafts,
                at=_at(11, 20),
                ref="s3.agreement",
                author=_ML,
                title=LUMEN_AGREEMENT_TITLE,
                path="/lumen-licensing/license-and-support-agreement.md",
                content=_lumen_agreement(
                    texts, fees_key="s3.agreement.fees.v1", indemnity=True
                ),
            )

        def v1_sent(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(11, 50),
                sender=_ML,
                to=(_JUNE,),
                cc=(_PN,),
                subject="Lumen — license and support agreement, first draft",
                text=texts["s3.email.v1-send"],
                thread="s3.draft",
                reply=False,
                attach="s3.agreement",
                attach_name="license-and-support-agreement.md",
            )

        self._on("2026-03-31", _at(11, 20), v1)
        self._on("2026-03-31", _at(11, 50), v1_sent)

        def client_comments(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(15, 10),
                sender=_JUNE,
                to=(_ML,),
                subject="Re: Lumen — license and support agreement, first draft",
                text=texts["s3.email.client-comments"],
                thread="s3.draft",
                reply=True,
            )

        self._on("2026-04-16", _at(15, 10), client_comments)

        def v2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(10, 30),
                ref="s3.agreement",
                revision=2,
                author=_ML,
                content=_lumen_agreement(
                    texts, fees_key="s3.agreement.fees.v2", indemnity=True
                ),
                summary="Incorporated licensee comments on fees and support terms.",
            )

        def v2_sent(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 55),
                sender=_ML,
                to=(_JUNE,),
                subject="Re: Lumen — license and support agreement, first draft",
                text=texts["s3.email.v2-send"],
                thread="s3.draft",
                reply=True,
                attach="s3.agreement",
                attach_name="license-and-support-agreement.md",
            )

        self._on("2026-04-21", _at(10, 30), v2)
        self._on("2026-04-21", _at(10, 55), v2_sent)

        def pushback(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(16, 20),
                sender=_CALEB,
                to=(_ML,),
                cc=(_JUNE,),
                subject="Lumen / Fathom — remaining open items",
                text=texts["s3.email.licensor-pushback"],
                thread="s3.licensor",
                reply=False,
            )

        self._on("2026-05-19", _at(16, 20), pushback)

        def v3(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(9, 45),
                ref="s3.agreement",
                revision=3,
                author=_ML,
                content=_lumen_agreement(
                    texts, fees_key="s3.agreement.fees.v2", indemnity=False
                ),
                summary="Conformed cross-references and cleaned up "
                "formatting after the drafting call.",
            )

        self._on("2026-05-21", _at(9, 45), v3)

        def ready_to_sign(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 40),
                sender=_JUNE,
                to=(_ML,),
                subject="Re: Lumen — license and support agreement, first draft",
                text=texts["s3.email.ready-to-sign"],
                thread="s3.draft",
                reply=True,
            )

        def final_confirm(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(13, 15),
                sender=_ML,
                to=(_JUNE,),
                subject="Re: Lumen — license and support agreement, first draft",
                text=texts["s3.email.final-confirm"],
                thread="s3.draft",
                reply=True,
            )

        self._on("2026-06-09", _at(10, 40), ready_to_sign)
        self._on("2026-06-09", _at(13, 15), final_confirm)

    # S4 — Cascadia sours across six weeks, then terminates.

    def _register_s4(self) -> None:
        texts = self._texts

        def happy_chat(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(16, 40),
                sender=_SR,
                body="Good call with Tom Hollis today — Cascadia is happy "
                "with the discovery plan on the supplier dispute.",
                ref="s4.chat1",
            )
            self._react(
                drafts, at=_at(16, 55), ref="s4.chat1", person=_SM, emoji="thumbsup"
            )
            self._react(drafts, at=_at(17, 5), ref="s4.chat1", person=_GA, emoji="tada")
            self._react(
                drafts, at=_at(17, 20), ref="s4.chat1", person=_EH, emoji="thumbsup"
            )

        self._on("2026-03-24", _at(16, 40), happy_chat)

        def concern1(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 25),
                sender=_TOM,
                to=(_SR,),
                subject="Cascadia — where do we stand?",
                text=texts["s4.email.concern1"],
                thread="s4.status",
                reply=False,
            )

        def reassure(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(14, 30),
                sender=_SR,
                to=(_TOM,),
                subject="Re: Cascadia — where do we stand?",
                text=texts["s4.email.reassure"],
                thread="s4.status",
                reply=True,
            )

        self._on("2026-04-15", _at(10, 25), concern1)
        self._on("2026-04-15", _at(14, 30), reassure)

        def antsy_chat(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(9, 15),
                sender=_SR,
                body="Cascadia is getting antsy about the supplier dispute "
                "timeline — pulling together a status memo today.",
                ref="s4.chat2",
            )
            self._react(drafts, at=_at(9, 40), ref="s4.chat2", person=_SM, emoji="eyes")
            self._react(
                drafts, at=_at(10, 10), ref="s4.chat2", person=_GA, emoji="thumbsup"
            )

        self._on("2026-04-16", _at(9, 15), antsy_chat)

        def concern2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(11, 35),
                sender=_TOM,
                to=(_SR,),
                cc=(_SM,),
                subject="Re: Cascadia — where do we stand?",
                text=texts["s4.email.concern2"],
                thread="s4.status",
                reply=True,
            )

        self._on("2026-04-24", _at(11, 35), concern2)

        def partner_chat(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(9, 5),
                sender=_SM,
                body="I'll take the Hollis call myself this week. Sofia, "
                "send me the Cascadia file summary before Wednesday.",
                ref="s4.chat3",
            )
            self._react(
                drafts, at=_at(9, 30), ref="s4.chat3", person=_GA, emoji="thumbsup"
            )

        self._on("2026-04-27", _at(9, 5), partner_chat)

        def concern3(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(15, 45),
                sender=_TOM,
                to=(_SM,),
                cc=(_SR,),
                subject="Re: Cascadia — where do we stand?",
                text=texts["s4.email.concern3"],
                thread="s4.status",
                reply=True,
            )

        self._on("2026-05-06", _at(15, 45), concern3)

        def memo_chat(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(10, 20),
                sender=_SR,
                body="Cascadia status memo went out last night. Tom's "
                "reply was one line.",
                ref="s4.chat4",
            )

        self._on("2026-05-07", _at(10, 20), memo_chat)

        def declined_chat(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(14, 5),
                sender=_GA,
                body="Cascadia file: Tom declined the Thursday call and "
                "asked for everything in email going forward.",
                ref="s4.chat5",
            )

        self._on("2026-05-13", _at(14, 5), declined_chat)

        def cold(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(9, 30),
                sender=_TOM,
                to=(_SM,),
                cc=(_EH,),
                subject="Re: Cascadia — where do we stand?",
                text=texts["s4.email.cold"],
                thread="s4.status",
                reply=True,
            )

        self._on("2026-05-20", _at(9, 30), cold)

        def terminate(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(8, 50),
                sender=_TOM,
                to=(_EH,),
                cc=(_SM,),
                subject="Cascadia Outfitters — termination of engagement",
                text=texts["s4.email.terminate"],
                thread="s4.termination",
                reply=False,
            )

        self._on("2026-05-27", _at(8, 50), terminate)

        def acknowledge(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(9, 25),
                sender=_EH,
                to=(_TOM,),
                cc=(_SM,),
                subject="Re: Cascadia Outfitters — termination of engagement",
                text=texts["s4.email.acknowledge"],
                thread="s4.termination",
                reply=True,
            )

        def transition(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(9, 50),
                sender=_EH,
                to=(_SM, _SR),
                cc=(_GA,),
                subject="Cascadia wind-down — assignments",
                text=texts["s4.email.transition"],
                thread="s4.winddown",
                reply=False,
            )

        self._on("2026-05-28", _at(9, 25), acknowledge)
        self._on("2026-05-28", _at(9, 50), transition)

        def letter(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._doc(
                minter,
                drafts,
                at=_at(11, 10),
                ref="s4.letter",
                author=_EH,
                title=CASCADIA_LETTER_TITLE,
                path="/cascadia-supplier-dispute/disengagement-letter.md",
                content=_cascadia_letter(texts),
            )

        self._on("2026-06-01", _at(11, 10), letter)

        def close_matter(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            drafts.append(
                TimedDraft(
                    at=SimDuration(_at(10, 30)),
                    source=_entity(_SM),
                    payload=TicketUpdatedPayload(
                        kind="ticket.updated",
                        ticket_id=S4_TICKET,
                        actor=_SM,
                        changes=(
                            FieldChange(field="status", old="open", new="closed"),
                        ),
                    ),
                )
            )
            self._note(
                drafts,
                at=_at(10, 45),
                actor=_GA,
                ticket=S4_TICKET,
                body=texts["s4.note.closeout"],
            )
            self._chat(
                minter,
                drafts,
                at=_at(11, 0),
                sender=_SM,
                body="Cascadia is closed as of this morning. Records to "
                "Omar for the transfer package; final invoice is out.",
            )

        self._on(S4_CLOSED_DATE, _at(10, 30), close_matter)

    # S5 — the Arroyo hearing moves three times; the last move is chat-only.

    def _register_s5(self) -> None:
        texts = self._texts

        def set1_email(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(14, 20),
                sender=_DAWN,
                to=(_GA,),
                cc=(_SM,),
                subject="Arroyo Construction v. Fruitvale Partners — hearing setting",
                text=texts["s5.email.set1"],
                thread="s5.court",
                reply=False,
            )

        self._on("2026-03-16", _at(14, 20), set1_email)

        def cal1(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._calendar(
                minter,
                drafts,
                at=_at(9, 10),
                ref="s5.cal1",
                organizer=_GA,
                title=f"{ARROYO_HEARING_TITLE} (Dept. 511)",
                day="2026-04-28",
                start_clock=_at(10, 0),
                minutes=60,
                attendees=(_GA, _SM, _SR),
                description="Motion hearing, Alameda County Superior "
                "Court, Dept. 511. Courtesy copies due five court days "
                "prior.",
            )

        self._on("2026-03-17", _at(9, 10), cal1)

        def reset1_email(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(15, 35),
                sender=_DAWN,
                to=(_GA,),
                cc=(_SM,),
                subject="Re: Arroyo Construction v. Fruitvale Partners — "
                "hearing setting",
                text=texts["s5.email.reset1"],
                thread="s5.court",
                reply=True,
            )

        self._on("2026-04-17", _at(15, 35), reset1_email)

        def cal2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._calendar_update(
                drafts,
                at=_at(9, 20),
                ref="s5.cal1",
                actor=_GA,
                old="scheduled",
                new="vacated — continued to 2026-05-20 per clerk notice",
            )
            self._calendar(
                minter,
                drafts,
                at=_at(9, 25),
                ref="s5.cal2",
                organizer=_GA,
                title=f"{ARROYO_HEARING_TITLE} (reset, Dept. 511)",
                day="2026-05-20",
                start_clock=_at(10, 0),
                minutes=60,
                attendees=(_GA, _SM, _SR),
                description="Continued from April 28 by clerk notice "
                "(courtroom reassignment).",
            )

        self._on("2026-04-20", _at(9, 20), cal2)

        def stip(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(11, 45),
                sender=_VICTOR,
                to=(_SM,),
                cc=(_GA,),
                subject="Arroyo — stipulation to continue the motion hearing",
                text=texts["s5.email.stip"],
                thread="s5.stip",
                reply=False,
            )

        def stip_agree(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(16, 30),
                sender=_SM,
                to=(_VICTOR,),
                cc=(_GA,),
                subject="Re: Arroyo — stipulation to continue the motion hearing",
                text=texts["s5.email.stip-agree"],
                thread="s5.stip",
                reply=True,
            )

        self._on("2026-05-12", _at(11, 45), stip)
        self._on("2026-05-12", _at(16, 30), stip_agree)

        def reset2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(14, 15),
                sender=_DAWN,
                to=(_GA,),
                cc=(_SM,),
                subject="Re: Arroyo Construction v. Fruitvale Partners — "
                "hearing setting",
                text=texts["s5.email.reset2"],
                thread="s5.court",
                reply=True,
            )
            self._calendar_update(
                drafts,
                at=_at(15, 0),
                ref="s5.cal2",
                actor=_GA,
                old="scheduled",
                new="vacated — reset to 2026-06-18 per stipulated order",
            )
            self._calendar(
                minter,
                drafts,
                at=_at(15, 5),
                ref="s5.cal3",
                organizer=_GA,
                title=f"{ARROYO_HEARING_TITLE} (second reset, Dept. 511)",
                day="2026-06-18",
                start_clock=_at(10, 0),
                minutes=60,
                attendees=(_GA, _SM, _SR),
                description="Reset from May 20 by stipulated order.",
            )

        self._on("2026-05-13", _at(14, 15), reset2)

        def correction(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(11, 25),
                sender=_GA,
                body="Clerk's office called on Arroyo v. Fruitvale: the "
                "June 18 reset notice went out with the wrong date. The "
                "motion hearing is actually Thursday June 25, 9:00 a.m., "
                "Dept. 511. I'll fix the calendar entry tomorrow — "
                "flagging here first so nobody plans around the 18th.",
                ref="s5.correction",
            )
            self._chat(
                minter,
                drafts,
                at=_at(11, 40),
                sender=_SM,
                body="Thanks Grace — noted. Sofia, adjust the prep "
                "schedule for the 25th.",
                reply_ref="s5.correction",
            )

        self._on("2026-06-11", _at(11, 25), correction)
