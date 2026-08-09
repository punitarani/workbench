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
from workbench.core.events.chat import (
    ChatMessagePayload,
    ChatReactionAddedPayload,
)
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
# Round-6 substantive riders: operative clauses added to NDA histories in
# June. They are playbook-neutral (the survey's conforms/deviates calls do
# not move), and which additions have same-day covering mail is the S1
# silent-versions reconciliation.
NDA_RETURN_CLAUSE = (
    "Return of Materials. Upon the disclosing party's written request, the "
    "receiving party shall promptly return or destroy all Confidential "
    "Information, including copies, extracts, and summaries, and certify "
    "the destruction in writing within fourteen (14) days of the request."
)
NDA_NONSOLICIT_CLAUSE = (
    "Non-Solicitation. For one (1) year following the last disclosure, "
    "neither party will solicit for employment personnel of the other "
    "party who were directly involved in the engagement, except through "
    "general postings not directed at such personnel."
)
NDA_NOTICES_SECTION = (
    "Notices under this Agreement shall be delivered to the parties at the "
    "addresses stated in the signature blocks, with a courtesy copy by "
    "electronic mail to the negotiating contacts."
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
BAYMARK_NDA_TITLE = "Mutual NDA — BayMark IT Solutions (Draft)"
ARCHWAY_NDA_TITLE = "Mutual NDA — Archway Court Reporting (Draft)"
TRUELINE_NDA_TITLE = "Mutual NDA — Trueline Process Servers (Draft)"
COBALT_NDA_TITLE = "Mutual NDA — Cobalt Language Services (Draft)"
HARBORLIGHT_NDA_TITLE = "Mutual NDA — Harborlight Records Storage (Draft)"
BRIGHTWATER_NDA_TITLE = "Mutual NDA — Brightwater Trial Graphics (Draft)"
SUMMIT_NDA_TITLE = "Mutual NDA — Summit Staffing Partners (Draft)"

# Every vendor NDA on file, conforming histories included: the S1 drift
# task grades a per-NDA survey over this whole corpus.
CONFORMING_NDA_TITLES = (
    BAYMARK_NDA_TITLE,
    ARCHWAY_NDA_TITLE,
    TRUELINE_NDA_TITLE,
    COBALT_NDA_TITLE,
    HARBORLIGHT_NDA_TITLE,
    BRIGHTWATER_NDA_TITLE,
    SUMMIT_NDA_TITLE,
)
LUMEN_AGREEMENT_TITLE = (
    "Software License and Support Agreement — Lumen Software (Draft)"
)
LUMEN_SOW_TITLE = "Support Services Statement of Work — Lumen Software (Draft)"
CASCADIA_LETTER_TITLE = "Disengagement Letter — Cascadia Outfitters"
ARROYO_HEARING_TITLE = "Arroyo v. Fruitvale Partners — motion hearing"

# S5: the operative-date correction lives only in a Grace<->Samuel DM; the
# text deliberately carries no case name, no party, and no docket noun —
# just the Clio display-number prefix of the Arroyo matter.
S5_DM_CORRECTION = (
    "clerk just called about 00008 — moved again, the 25th at 9, not the "
    "18th. i'm out after tomorrow — will fix the calendar entry when i'm "
    "back."
)
S5_DM_ACK = "noted — thanks grace. flag it to sofia when you're back on."

# S5: a formal-looking internal recap sent AFTER the correction that
# restates the superseded June 18 setting (compiled from the stale master
# calendar while Grace is out). Load-bearing trap text stays in code.
S5_RECAP_SUBJECT = "Docket recap — weeks of June 15 and June 22"
S5_RECAP_BODY = (
    "Team,\n\n"
    "Docket recap for the next two weeks, pulled from the master calendar "
    "this morning while Grace is out. Flag anything that looks off:\n\n"
    "- Tue June 16, 2:00 p.m. — Brightline Logistics: position statement "
    "working session (internal).\n"
    "- Thu June 18, 10:00 a.m. — Arroyo Construction v. Fruitvale "
    "Partners: motion hearing, Dept. 511 (second reset per the stipulated "
    "order). Courtesy copies went out last week.\n"
    "- Mon June 22, 9:30 a.m. — Goldleaf Hospitality: case management "
    "hearing, Dept. 17.\n"
    "- Tue June 30 — Pelican Bay Marina: lease renewal option notice "
    "deadline (certified mail).\n\n"
    "Full details are on the master calendar. Grace was chasing the "
    "clerk's office about one of the litigation settings the week "
    "before she went out — we'll confirm everything stands when she is "
    "back on, and I'll recirculate if anything moves.\n\n"
    "Peter"
)

# S5 round-6: constructed stale citations — communications that keep
# citing a superseded hearing date after its supersession record. Load-
# bearing trap text stays in code; the graded set is exactly these plus
# the stale recap. Messages that announce a move or negate a date are
# corrections, not citations, and stay out of the set by construction.
S5_STALE_OUTLINE_SUBJECT = "Arroyo — argument outline for the motion hearing"
S5_STALE_OUTLINE_BODY = (
    "Samuel,\n\n"
    "Argument outline for the April 28 hearing is attached for your markup "
    "— lien priority first, then the bond question. I will have the "
    "authorities binder ready well ahead of the courtesy-copy deadline.\n\n"
    "Sofia"
)
S5_OUTLINE_REPLY_BODY = (
    "Sofia — that setting moved; the clerk reset the Arroyo hearing for "
    "May 20. Grace has the notice. Recalendar before you spend more time "
    "on the binder.\n\nSamuel"
)
S5_STALE_COPIES_CHAT = (
    "Arroyo courtesy copies — Dept. 511 wants them several court days "
    "ahead of the May 20 motion hearing. Who is handling the drop?"
)
S5_COPIES_REPLY_CHAT = (
    "that one moved — stipulated order reset it to June 18. i'll "
    "recirculate the clerk notice."
)
S5_STALE_VICTOR_SUBJECT = "Arroyo — logistics for the June 18 hearing"
S5_STALE_VICTOR_BODY = (
    "Counsel,\n\n"
    "For the June 18 hearing in Dept. 511: we will have two attorneys "
    "appearing and expect argument to run under the hour. Please confirm "
    "your courtesy copies went to chambers.\n\n"
    "Victor Crane\nCrane & Whitaker"
)
S5_STALE_BINDER_CHAT = (
    "Arroyo binder is assembled for Thursday's motion hearing on the 18th "
    "— courtesy copies boxed and ready."
)

# S4 round-6: the client-side correspondence fabric. Most of Tom's emails
# get in-thread firm replies; the graded anti-join is the ones that never
# did. Bodies are code constants so the reply topology is load-bearing.
S4_DOCS_SUBJECT = "Cascadia — supplier contract file"
S4_DOCS_ASK = (
    "Sofia,\n\nCan you send me copies of the two supplier contracts your "
    "team pulled for the dispute file? Our ops manager wants them for the "
    "insurance folder.\n\nTom"
)
S4_DOCS_REPLY = (
    "Tom,\n\nBoth supplier contracts are in the client portal folder now — "
    "I flagged the signature pages for your ops manager.\n\nSofia"
)
S4_DOCS_FOLLOWUP = (
    "Sofia,\n\nOne more: is the 2024 amendment part of the dispute record, "
    "or do we need to produce it separately?\n\nTom"
)
S4_DOCS_FOLLOWUP_REPLY = (
    "Tom,\n\nIt is already in the record — produced with the first set. "
    "Nothing more needed from your side.\n\nSofia"
)
S4_INVOICE_SUBJECT = "Cascadia — March invoice question"
S4_INVOICE_ASK = (
    "Anita,\n\nThe March invoice shows two lines for the same court filing "
    "fee — is that a duplicate?\n\nTom"
)
S4_INVOICE_REPLY = (
    "Tom,\n\nGood catch — one line is the filing fee and the other the "
    "courier charge for the same filing; the descriptions read alike. No "
    "duplicate.\n\nAnita"
)
S4_MEMO_SUBJECT = "Cascadia supplier dispute — status memorandum"
S4_MEMO_BODY = (
    "Tom,\n\nSending the status memorandum you asked for: current posture, "
    "the discovery schedule as ordered, and our settlement read. Samuel "
    "will follow up on next steps this week.\n\nSofia"
)
S4_NOTES_SUBJECT = "Cascadia — supplier meeting notes"
S4_NOTES_FIRST = (
    "Samuel,\n\nNotes from Friday's supplier meeting are below — the "
    "delivery dispute came up again in front of their counsel.\n\nTom"
)
S4_NOTES_SECOND = (
    "Samuel,\n\nForgot to add: their counsel floated a standstill "
    "proposal. Worth discussing before Thursday.\n\nTom"
)
S4_NOTES_REPLY = (
    "Tom,\n\nThanks — reviewed both. Let's take the standstill question on "
    "Thursday's call; Sofia will circulate a dial-in.\n\nSamuel"
)
S4_TRANSFER_SUBJECT = "Cascadia — file transfer logistics"
S4_TRANSFER_ASK = (
    "Grace,\n\nOmar's office says two of the boxes listed on the transfer "
    "memo have not arrived. Who should his paralegal call?\n\nTom"
)

# Round-6 document-mention fabric: short public-channel notes that name a
# document on the day a version of it was saved. They exist so the
# vanished-clause unreviewed-revisions anti-join has a dense covered side;
# the handful of revision days deliberately left without a mention are the
# graded set. Lines avoid every audited leak token (no term lengths, no
# residuals, no support markers, no client-arc names, no hearing dates).
MENTION_FABRIC: tuple[tuple[str, int, int, str, str, str], ...] = (
    # day, hour, minute, sender, channel ("matters"/"billing"), body
    (
        "2026-03-12",
        15,
        10,
        _DO,
        "matters",
        "Vendor NDA playbook rev 2 is filed — standard positions tightened "
        "per partner review.",
    ),
    (
        "2026-03-19",
        16,
        5,
        _DO,
        "matters",
        "Refreshed engagement letter template is in the repository — new "
        "rate schedule language included.",
    ),
    (
        "2026-03-24",
        15,
        35,
        _GA,
        "matters",
        "Trueline process servers NDA — conformed copy is filed; signature "
        "packet goes out with the next records run.",
    ),
    (
        "2026-03-25",
        15,
        0,
        _PN,
        "matters",
        "Vendor NDA playbook rev 3 is up — intake and signature-routing notes added.",
    ),
    (
        "2026-04-08",
        12,
        15,
        _GA,
        "matters",
        "Matter intake checklist updated — conflicts screening steps "
        "expanded per the quarterly review.",
    ),
    (
        "2026-04-21",
        15,
        5,
        _NF,
        "matters",
        "Cobalt language services NDA refiled after proofread — defined "
        "terms cleaned up.",
    ),
    (
        "2026-04-22",
        11,
        0,
        _SR,
        "matters",
        "Discovery response playbook now carries the ESI protocol checklist "
        "— comments welcome.",
    ),
    (
        "2026-04-24",
        11,
        30,
        _PN,
        "matters",
        "Support services statement of work rev 2 is filed — formatting cleanup only.",
    ),
    (
        "2026-04-28",
        16,
        30,
        _ML,
        "matters",
        "License and support agreement rev 3 posted after internal review.",
    ),
    (
        "2026-04-29",
        10,
        30,
        _CJ,
        "billing",
        "Billing guidelines refresh is in — narrative standards clarified "
        "ahead of the May prebills.",
    ),
    (
        "2026-05-06",
        16,
        40,
        _PN,
        "matters",
        "Harborlight records storage NDA is conformed and filed — renewal "
        "entities updated in the signature blocks.",
    ),
    (
        "2026-05-07",
        15,
        35,
        _SR,
        "matters",
        "Litigation hold notice template — preservation scope list now "
        "covers messaging applications; take a look before the next hold "
        "goes out.",
    ),
    (
        "2026-05-21",
        14,
        20,
        _PN,
        "matters",
        "Lumen file: closing sequence looks good for early June — signature "
        "packet prep starts next week.",
    ),
    (
        "2026-05-22",
        15,
        15,
        _NF,
        "matters",
        "Engagement letter template now carries the client portal and "
        "electronic signature consent language.",
    ),
    (
        "2026-05-27",
        14,
        50,
        _ML,
        "matters",
        "Statement of work exhibits — the staffing table needs one more "
        "pass before the packet.",
    ),
    (
        "2026-05-28",
        16,
        45,
        _PN,
        "matters",
        "License and support agreement rev 5 — formatting and numbering "
        "cleanup, filed.",
    ),
    (
        "2026-06-02",
        16,
        10,
        _NF,
        "matters",
        "Brightwater trial graphics NDA refiled after proofread — citations fixed.",
    ),
    (
        "2026-06-03",
        12,
        0,
        _ML,
        "matters",
        "License and support agreement rev 6 filed — defined terms tidied "
        "ahead of the signature packet.",
    ),
    (
        "2026-06-08",
        16,
        15,
        _PN,
        "matters",
        "Final proofs are in: license and support agreement rev 7 and the "
        "support services statement of work rev 4, both staged for the "
        "signature packet.",
    ),
    (
        "2026-06-15",
        12,
        5,
        _NF,
        "matters",
        "Trueline process servers NDA — returns rider folded in and refiled.",
    ),
    (
        "2026-06-16",
        15,
        10,
        _NF,
        "matters",
        "Cobalt language services NDA — returns rider folded in and refiled.",
    ),
    (
        "2026-06-17",
        15,
        50,
        _GA,
        "matters",
        "Matter intake checklist updated — signature routing aligned with "
        "the current records workflow.",
    ),
    (
        "2026-06-18",
        11,
        0,
        _NF,
        "matters",
        "Archway court reporting NDA — staffing rider folded in and refiled.",
    ),
    (
        "2026-06-19",
        12,
        20,
        _SM,
        "matters",
        "Discovery response playbook — meet and confer timing guidance recorded.",
    ),
    (
        "2026-06-22",
        15,
        15,
        _PN,
        "matters",
        "Summit staffing partners NDA — conformed copy filed; signature "
        "blocks updated.",
    ),
    (
        "2026-06-23",
        16,
        35,
        _CJ,
        "billing",
        "Billing guidelines — prebill calendar updated for the third quarter.",
    ),
    (
        "2026-06-24",
        15,
        30,
        _PN,
        "matters",
        "Brightwater trial graphics NDA — notice addresses recorded and refiled.",
    ),
    (
        "2026-06-25",
        10,
        50,
        _NF,
        "matters",
        "Summit staffing partners NDA — staffing rider folded in and refiled.",
    ),
)

# S2: the only place in the record that states the dispute's cutoff date.
S2_CUTOFF_CHAT = (
    "Meridian April split is done. Cutoff per Eleanor is the April 3 "
    "budget call: diligence and data-room entries dated after April 3 are "
    "the disputed bucket; the tranche-1 work before the call stays as "
    "originally scoped. Export is in the billing folder."
)

# S2 support audit: an April entry on the Meridian matter is "supported"
# when a same-day email or chat message names the engagement — the client
# (Meridian), the deal (the diagnostics acquisition), or the matter
# number (00001). These markers are the whole rule; the audit, the
# grader, and the reference solution all apply exactly this list.
S2_SUPPORT_MARKERS = ("meridian", "diagnostics", "00001")

# The deal team's April data-room sprint runs through the Marcus<->Peter
# DM. The rotation lines are deliberately matter-blind — the Solstice
# closing staged a seller data room the same month, so a tranche or a
# privilege screen could be either file — which means they never support
# an entry under the marker rule. The dated exceptions below name the
# client and are, by construction, the only support their days have.
S2_SPRINT_DAYS = (
    "2026-04-06",
    "2026-04-07",
    "2026-04-08",
    "2026-04-09",
    "2026-04-10",
    "2026-04-13",
    "2026-04-14",
    "2026-04-15",
    "2026-04-16",
    "2026-04-17",
)
S2_SPRINT_CLOCKS = (
    (8, 40),
    (9, 35),
    (11, 20),
    (13, 5),
    (14, 15),
    (15, 40),
    (16, 55),
    (18, 5),
)
S2_SPRINT_LINES = (
    "staging the next folder batch now — index refresh once it lands.",
    "qc pass on this morning's uploads is done; two files flagged for "
    "privilege review.",
    "can you re-run the checksum on yesterday's batch? counts look off by three.",
    "privilege screen through the new folder is clean. moving on.",
    "the seller's team re-uploaded the corrupted set — pulling it into "
    "the review queue.",
    "index rebuilt. the numbering gap was a duplicate folder, not a missing one.",
    "tagging pass done through this afternoon's tranche; nothing unusual to flag.",
    "hold uploads for an hour — running the dedupe script.",
    "dedupe finished, forty-one exact duplicates dropped from the review set.",
    "who has the access log? need to reconcile reviewer names before close of day.",
    "review queue is empty as of now. next batch lands tomorrow morning.",
    "flagging one folder for your eyes before it goes in the index — odd date stamps.",
    "checked the odd date stamps: scanner artifacts, not edits. cleared it.",
    "closing the log for today; summary sheet is in the shared drive.",
)

# S2 support-audit coverage exceptions. The DM texts name the client on
# days whose only reference lives in the DM (search excludes DMs); the
# oblique emails name only the deal — never the client — on days whose
# only reference is that email, so a client-name grep calls those days
# unsupported and lists entries that have support.
S2_DM_COVERAGE_TEXTS = {
    "2026-04-07": (
        "meridian folder counts jumped again overnight — hold the index "
        "until i re-run it against the seller's manifest."
    ),
    "2026-04-15": (
        "meridian qc log is clean through this week's uploads; posting "
        "the refreshed index tonight."
    ),
}
S2_OBLIQUE_EMAILS = (
    (
        "2026-04-09",
        (16, 35),
        _PN,
        _ML,
        "Data room index — diagnostics acquisition",
        "Marcus,\n\nRebuilt the tranche index for the diagnostics "
        "acquisition after today's uploads and reconciled it against the "
        "seller's manifest. Three folders are flagged for privilege "
        "review before they go to the client team; the rest are staged "
        "for tomorrow's pass.\n\nPeter",
    ),
    (
        "2026-04-21",
        (10, 10),
        _CJ,
        _AB,
        "Prebill watch — diagnostics acquisition",
        "Anita,\n\nFlagging early: this month's time on the diagnostics "
        "acquisition is pacing well ahead of the estimate we gave the "
        "client, mostly review hours out of the expanded document set. "
        "Nothing to action yet — I want it on your radar before the "
        "prebill run.\n\nCarl",
    ),
)

# April is the firm's crunch month, and two more DM lanes carry it: the
# billing pair works the prebill cycle and the paralegals work the
# records desk, every workday. Like the data-room sprint, the lines are
# matter-blind — they support nothing under the S2 marker rule — and
# they push each thread's April window past a single 100-message read.
APRIL_WORKDAYS = (
    "2026-04-01",
    "2026-04-02",
    "2026-04-03",
    *S2_SPRINT_DAYS,
    "2026-04-20",
    "2026-04-21",
    "2026-04-22",
    "2026-04-23",
    "2026-04-24",
    "2026-04-27",
    "2026-04-28",
    "2026-04-29",
    "2026-04-30",
)
APRIL_BILLING_DM_CLOCKS = ((9, 10), (12, 40), (14, 35), (16, 20))
APRIL_BILLING_DM_LINES = (
    "prebill run kicks off thursday — send me any write-down flags before then.",
    "two receivables crossed sixty days this morning. drafting the reminder letters.",
    "trust ledger reconciled through last month; one shortfall flagged separately.",
    "can you pull the expense backups for the march couriers? scanning gaps again.",
    "rate table check is done — three timekeepers still on the old schedule.",
    "the portal upload failed overnight; re-sending this morning's statements.",
    "edits are back on about half the prebills. chasing the rest after lunch.",
    "reminder to the team going out: narratives due before the run, not after.",
    "wrote off the copy charges on the closed file per the partner note.",
    "collections call went fine — payment promised by the end of the month.",
)
APRIL_RECORDS_DM_CLOCKS = ((8, 55), (10, 40), (11, 45), (14, 50), (17, 25))
APRIL_RECORDS_DM_LINES = (
    "filing run at noon — anything for the court drop besides the two on my list?",
    "boxes 14 and 19 came back from offsite; logging them into the index now.",
    "service list update done; the new addresses are in the master sheet.",
    "the transcript from tuesday's depo is in — routing it for exhibit stamping.",
    "can you cover the records desk for an hour this afternoon?",
    "courtesy copies are assembled; binding them after lunch.",
    "the scanner queue is backed up — flagging the oversized exhibits "
    "for outside copying.",
    "chron file is current through yesterday. starting today's intake.",
    "retention review: three closed files are past the hold window; "
    "circulating the list.",
    "signature packet came back unsigned on one tab — sending it around again.",
)

# Round 6: the document-mention rule for the unreviewed-revisions
# reconciliation. A message mentions a document when its text (email
# subject, body, or attachment filename; public-channel chat body)
# carries one of the document's markers — the way the firm actually
# names that file. Naming the matter, the client, or the workspace
# alone never counts. The audit, the grader's ground truth, and the
# reference solution all apply exactly this table.
DOC_MENTION_MARKERS: dict[str, tuple[str, ...]] = {
    PLAYBOOK_TITLE: ("nda playbook", "vendor-nda-playbook"),
    "Engagement Letter (Standard Form)": ("engagement letter",),
    "Matter Intake Checklist": ("intake checklist", "matter-intake-checklist"),
    "Billing & Time Entry Guidelines": (
        "billing guidelines",
        "time entry guidelines",
        "billing-guidelines",
    ),
    "Litigation Hold Notice (Template)": ("litigation hold", "litigation-hold"),
    "Discovery Response Playbook": (
        "discovery response playbook",
        "discovery playbook",
        "discovery-responses",
    ),
    LUMEN_AGREEMENT_TITLE: (
        "license and support agreement",
        "license-and-support-agreement",
    ),
    LUMEN_SOW_TITLE: ("statement of work", "support-services-sow"),
}
DOC_MENTION_MARKERS.update(
    {
        title: (title.split(" — ")[1].split()[0].lower(),)
        for title in (LEXIPOINT_NDA_TITLE, IRONCLAD_NDA_TITLE, *CONFORMING_NDA_TITLES)
    }
)

# S1: the only discussion of the Ironclad concession, in a #matters thread
# reply that never uses the clause's name.
S1_IRONCLAD_THREAD_PARENT = (
    "Ironclad discovery NDA: markup back from their PM this morning. Term "
    "is fine; one clause left to land before it goes back."
)
S1_IRONCLAD_THREAD_REPLY = (
    "Closing out the Ironclad NDA today — folding in the carve-out "
    "LexiPoint asked for back in May. Only way to keep the discovery "
    "engagement moving; flagging here for the file."
)

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
            name="s1.nda.baymark.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and BayMark IT Solutions (a managed IT services "
                    "vendor): numbered sections for Definitions, Permitted "
                    "Use, Exclusions, Return of Materials, and No License"
                ),
                facts=(
                    "purpose is evaluation and provision of managed IT and "
                    "helpdesk services for the firm; do NOT include any "
                    "section on term or duration, residual knowledge, "
                    "injunctive or equitable relief, or governing law — "
                    "those are appended separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.nda.archway.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and Archway Court Reporting (a deposition and "
                    "court-reporting vendor): numbered sections for "
                    "Definitions, Permitted Use, Exclusions, Return of "
                    "Materials, and No License"
                ),
                facts=(
                    "purpose is provision of court reporting, "
                    "transcription, and deposition services; do NOT "
                    "include any section on term or duration, residual "
                    "knowledge, injunctive or equitable relief, or "
                    "governing law — those are appended separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.nda.trueline.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and Trueline Process Servers (a process service and "
                    "court filing vendor): numbered sections for "
                    "Definitions, Permitted Use, Exclusions, Return of "
                    "Materials, and No License"
                ),
                facts=(
                    "purpose is provision of process service, court "
                    "filing, and skip tracing services; do NOT include "
                    "any section on term or duration, residual knowledge, "
                    "injunctive or equitable relief, or governing law — "
                    "those are appended separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.nda.cobalt.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and Cobalt Language Services (a translation and "
                    "interpreting vendor): numbered sections for "
                    "Definitions, Permitted Use, Exclusions, Return of "
                    "Materials, and No License"
                ),
                facts=(
                    "purpose is provision of certified translation and "
                    "deposition interpreting services; do NOT include any "
                    "section on term or duration, residual knowledge, "
                    "injunctive or equitable relief, or governing law — "
                    "those are appended separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.nda.harborlight.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and Harborlight Records Storage (an offsite records "
                    "storage and destruction vendor): numbered sections "
                    "for Definitions, Permitted Use, Exclusions, Return "
                    "of Materials, and No License"
                ),
                facts=(
                    "purpose is provision of offsite records storage, "
                    "retrieval, and certified destruction services; do "
                    "NOT include any section on term or duration, "
                    "residual knowledge, injunctive or equitable relief, "
                    "or governing law — those are appended separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.nda.brightwater.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and Brightwater Trial Graphics (a litigation graphics "
                    "and trial technology vendor): numbered sections for "
                    "Definitions, Permitted Use, Exclusions, Return of "
                    "Materials, and No License"
                ),
                facts=(
                    "purpose is provision of demonstrative exhibits, "
                    "trial presentation technology, and courtroom "
                    "support; do NOT include any section on term or "
                    "duration, residual knowledge, injunctive or "
                    "equitable relief, or governing law — those are "
                    "appended separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.nda.summit.body",
            prompt=_section_prompt(
                what=(
                    "the core sections of a mutual nondisclosure agreement "
                    "between Hartwell & Marsh LLP (a California law firm) "
                    "and Summit Staffing Partners (a contract attorney and "
                    "paralegal staffing vendor): numbered sections for "
                    "Definitions, Permitted Use, Exclusions, Return of "
                    "Materials, and No License"
                ),
                facts=(
                    "purpose is provision of contract attorneys and "
                    "paralegals for document review engagements; do NOT "
                    "include any section on term or duration, residual "
                    "knowledge, injunctive or equitable relief, or "
                    "governing law — those are appended separately."
                ),
                length="280-380 words",
            ),
            max_tokens=700,
        ),
        ContentRequest(
            name="s1.email.vendor-intake",
            prompt=_email_prompt(
                writer="Anita Bailey, operations manager at Hartwell & Marsh",
                recipient=("Noah Feldstein, associate (cc Diane Okonkwo, of counsel)"),
                day="2026-03-18",
                facts=(
                    "two vendor NDAs came in through intake this week — "
                    "the BayMark IT Solutions renewal and a new engagement "
                    "with Archway Court Reporting; both are going out on "
                    "the firm's standard form with the standard positions "
                    "unchanged; the drafts are filed in the vendor-ndas "
                    "workspace for Noah's review."
                ),
                tone="organized, brisk",
            ),
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
                    "to the NDA, both set out in the redlined draft "
                    "attached to the email: a confidentiality term "
                    "materially longer than the draft carries, and a "
                    "residual-knowledge clause permitting unaided-memory "
                    "use; both are described as non-negotiable house "
                    "positions. STRICT: never state the length of any "
                    "term in words or digits — no counts of years "
                    "anywhere; call it only the survival period from "
                    "their house form."
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
                    "revised draft attached: the firm accepted the longer "
                    "confidentiality term from LexiPoint's markup to keep "
                    "the renewal on schedule, but is not including a "
                    "residual-knowledge clause; hopes this splits the "
                    "difference. STRICT: never state the length of any "
                    "term in words or digits — no counts of years "
                    "anywhere."
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
                    "LexiPoint accepts the revised draft as sent — the "
                    "term as revised, without the memory carve-out they "
                    "had asked for; signature to follow this week; thanks "
                    "Noah for the quick turnaround. STRICT: never state "
                    "the length of any term in words or digits, and never "
                    "use the word residual or residuals."
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
                    "services engagement; the term as drafted works; one "
                    "comment remains: because Ironclad's project staff "
                    "rotate across client engagements, Ironclad asks the "
                    "firm to fold in the rider from Stan's attached markup "
                    "protecting what its people generally learn on an "
                    "engagement. Describe the request only in those "
                    "general words — never use the word residual or "
                    "residuals, never use the phrase unaided memory, and "
                    "never state the length of any term in words or "
                    "digits."
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
                    "revised NDA attached with the confidentiality article "
                    "conformed to Ironclad's markup from last week; the "
                    "firm wants the discovery engagement moving; asks for "
                    "signature this week. Do not name or describe the "
                    "clause that changed, and never use the word residual "
                    "or residuals."
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
                    "Ironclad) both went out with confidentiality terms "
                    "longer than the playbook's standard position, which "
                    "the March playbook still makes the hard rule; she "
                    "also wants the final Ironclad draft checked clause "
                    "by clause against the playbook's standard positions, "
                    "because she believes at least one other position "
                    "moved without sign-off; asks Noah to put a playbook "
                    "review on next quarter's calendar rather than keep "
                    "deviating silently. STRICT: do not name which other "
                    "clause moved, never use the word residual or "
                    "residuals, and never state the length of any term "
                    "in words or digits."
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
                    "Meridian disputes the April invoice; when the "
                    "expanded data-room diligence was scoped on the budget "
                    "call, Marcus agreed that diligence beyond the "
                    "original scope would be capped at $12,000; the "
                    "invoice shows diligence hours far beyond that; asks "
                    "for a corrected invoice and a written scope "
                    "confirmation before paying anything. Refer to the "
                    "call only as the budget call — never state the date "
                    "it happened."
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
                    "dated on or before the budget-call date and entries "
                    "after it, with the diligence entries flagged; the "
                    "client claims a diligence cap was agreed on that call "
                    "and she wants the numbers before responding; Carl has "
                    "the call date in the billing file. Never state the "
                    "call's date or any dollar figure."
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
                    "diligence entries dated after the budget call are the "
                    "bulk of the overage, spread across Marcus Liang and "
                    "Peter Novak; the exact entry dates and figures are in "
                    "the activity export he attached to the billing "
                    "folder, and he posted the agreed cutoff to the "
                    "billing channel for the record. Never state any "
                    "calendar date or numeric figure in the email itself."
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
                    "the firm will honor the understanding from the budget "
                    "call: expanded diligence time entered after the "
                    "agreed cutoff will be capped at $12,000 and the "
                    "overage credited on the May invoice; a written scope "
                    "confirmation for the remaining phases will follow "
                    "within the week; she values the relationship. Refer "
                    "to the call only as the budget call — never state "
                    "its date."
                ),
                tone="gracious, decisive",
            ),
        ),
        ContentRequest(
            name="s2.note.resolution",
            prompt=(
                "Write a matter note (plain text, 150-220 words) recorded "
                "by managing partner Eleanor Hartwell in the firm's "
                "practice management system on the Meridian diagnostics "
                "acquisition matter, after a fee dispute was resolved. "
                "Record, as narrative: the client disputed the April "
                "invoice shortly after it issued; the client's position "
                "was that a cap on expanded data-room diligence had been "
                "agreed with Marcus Liang on the budget call that scoped "
                "that work; billing split the April activities around the "
                "call date and the diligence entries after it "
                "substantially exceeded the cap; the firm honored the "
                "cap, credited the overage on the May invoice, and is "
                "countersigning a written scope confirmation; going "
                "forward any scope expansion on this matter needs written "
                "confirmation before work starts. STRICT: no day-level "
                "calendar dates (month names alone are fine), no dollar "
                "amounts, no hour or minute figures, and no client "
                "contact names anywhere in the note. No headers, no "
                "signature block."
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
            name="s3.sow.body",
            prompt=_section_prompt(
                what=(
                    "the body (numbered sections for Scope of Services, "
                    "Deliverables, Personnel, Fees and Invoicing, and Term "
                    "of this SOW) of a support-services statement of work "
                    "under the software license and support agreement "
                    "between Lumen Software (Licensee) and Fathom Systems "
                    "Inc. (Licensor)"
                ),
                facts=(
                    "the SOW covers implementation assistance and premium "
                    "support for the Fathom workflow platform: onboarding "
                    "workshops, configuration review, a named support "
                    "engineer, quarterly service reviews; fees are billed "
                    "monthly at the rates in Exhibit B; the SOW runs "
                    "twelve months from its effective date. Do NOT "
                    "include any indemnification, liability, or "
                    "confidentiality language — those live in the master "
                    "agreement."
                ),
                length="250-350 words",
            ),
            max_tokens=650,
        ),
        ContentRequest(
            name="s3.email.quote-indemnity",
            prompt=_email_prompt(
                writer="June Akana, general counsel of Lumen Software",
                recipient="Marcus Liang at Hartwell & Marsh",
                day="2026-06-09",
                facts=(
                    "for her board minutes she is pasting, directly below "
                    "her sign-off, the indemnification language from the "
                    "April draft she approved, and asks Marcus to confirm "
                    "the signing draft still carries it word for word; "
                    "end the email by introducing the quoted language "
                    "with a colon (the quotation itself is appended "
                    "separately — do not write the clause text)."
                ),
                tone="precise, trusting",
            ),
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
        # Firm fabric — revision histories for the genesis firm documents,
        # so the repository carries many multi-version drafts with clean,
        # additive diffs. Every fabric revision only adds; nothing
        # substantive ever disappears from these histories.
        ContentRequest(
            name="fabric.engagement.fees",
            prompt=_section_prompt(
                what=(
                    "a 'Fees and billing practices' section for a "
                    "California law firm's standard engagement letter "
                    "template"
                ),
                facts=(
                    "hourly rates are set out in a schedule reviewed "
                    "annually; invoices issue monthly with detailed "
                    "narratives; costs are passed through at actual; "
                    "retainers are replenished on request; billing "
                    "questions go to the billing coordinator."
                ),
                length="90-140 words",
            ),
        ),
        ContentRequest(
            name="fabric.intake.conflicts",
            prompt=_section_prompt(
                what=(
                    "a 'Conflicts screening' section for a law firm "
                    "matter-intake checklist"
                ),
                facts=(
                    "run the conflicts database against all adverse "
                    "parties and their affiliates before opening; "
                    "circulate a firm-wide conflicts memo when a new "
                    "adverse party appears; document any waiver in the "
                    "matter file; repeat the check whenever parties are "
                    "added."
                ),
                length="80-130 words",
            ),
        ),
        ContentRequest(
            name="fabric.billing.narratives",
            prompt=_section_prompt(
                what=(
                    "a 'Narrative standards' section for a law firm "
                    "billing and time-entry guideline"
                ),
                facts=(
                    "narratives state the action taken, the subject, and "
                    "the work product; block billing is discouraged; "
                    "entries are recorded within 48 hours; only "
                    "abbreviations from the approved list are used."
                ),
                length="80-130 words",
            ),
        ),
        ContentRequest(
            name="fabric.hold.scope",
            prompt=_section_prompt(
                what=(
                    "a 'Preservation scope' paragraph for a litigation "
                    "hold notice template"
                ),
                facts=(
                    "scope covers email, chat and messaging applications, "
                    "shared drives, laptops and phones, and third-party "
                    "hosted data; automatic deletion must be suspended; "
                    "questions go to the issuing attorney."
                ),
                length="70-110 words",
            ),
        ),
        ContentRequest(
            name="fabric.discovery.esi",
            prompt=_section_prompt(
                what=(
                    "an 'ESI protocol checklist' section for a law firm "
                    "discovery-response playbook"
                ),
                facts=(
                    "agree custodians, date ranges, and search terms in "
                    "writing; document collection methods; track "
                    "production numbering and confidentiality "
                    "designations; log meet-and-confer positions."
                ),
                length="80-130 words",
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
    extras: tuple[tuple[str, str], ...] = (),
) -> str:
    """``extras`` appends late-history sections (heading, text) after the
    equitable-relief article, so extended versions strictly contain their
    predecessors' paragraphs."""
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
    ]
    for heading, text in extras:
        parts += ["", f"## {heading}", "", text]
    parts += [
        "",
        "## Governing Law",
        "",
        "This Agreement is governed by California law; venue lies in Alameda County.",
    ]
    return "\n".join(parts) + "\n"


def _lumen_agreement(
    texts: Mapping[str, str], *, fees_key: str, indemnity: bool, circulated: str
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
    parts += [
        "",
        f"*Working draft circulated {circulated} for internal review; "
        "not for execution.*",
    ]
    return "\n".join(parts) + "\n"


def _lumen_sow(texts: Mapping[str, str], *, circulated: str) -> str:
    return (
        "# Support Services Statement of Work\n\n"
        "**Licensor:** Fathom Systems Inc.  \n"
        "**Licensee:** Lumen Software\n\n"
        "Entered into under the Software License and Support Agreement "
        "between the parties.\n\n"
        f"{texts['s3.sow.body']}\n\n"
        f"*Working draft circulated {circulated} for internal review; "
        "not for execution.*\n"
    )


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

        def channel(name: str) -> str:
            return next(
                event.payload.conversation_id
                for event in genesis.events
                if event.payload.kind == "chat.conversation.created"
                and event.payload.name == name
            )

        self._matters_channel = channel("#matters")
        self._billing_channel = channel("#billing")

        def dm_between(first: str, second: str) -> str:
            return next(
                event.payload.conversation_id
                for event in genesis.events
                if event.payload.kind == "chat.conversation.created"
                and event.payload.conversation_type == "dm"
                and set(event.payload.members) == {first, second}
            )

        self._grace_samuel_dm = dm_between(_GA, _SM)
        self._marcus_peter_dm = dm_between(_ML, _PN)
        self._anita_carl_dm = dm_between(_AB, _CJ)
        self._grace_peter_dm = dm_between(_GA, _PN)
        self._refs: dict[str, str] = {}
        self._beats: dict[str, list[tuple[int, _Beat]]] = {}
        self._register_s1()
        self._register_s2()
        self._register_s3()
        self._register_s4()
        self._register_s5()
        self._register_fabric(genesis)
        self._register_april_dm_lanes()
        self._register_mention_fabric()
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
        conversation: str | None = None,
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
                    conversation_id=(
                        conversation
                        if conversation is not None
                        else self._matters_channel
                    ),
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

        # Distractor vendor NDAs with clean, conforming histories: both
        # stay on the playbook's three-year term with no residuals clause.
        def baymark_v1(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._doc(
                minter,
                drafts,
                at=_at(9, 40),
                ref="s1.baymark",
                author=_NF,
                title=BAYMARK_NDA_TITLE,
                path="/firm/vendor-ndas/mutual-nda-baymark.md",
                content=_nda(
                    texts,
                    title=BAYMARK_NDA_TITLE,
                    body_key="s1.nda.baymark.body",
                    term=NDA_TERM_THREE,
                    residuals=False,
                ),
            )

        def vendor_intake(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 5),
                sender=_AB,
                to=(_NF,),
                cc=(_DO,),
                subject="Vendor NDA intake — BayMark renewal and Archway",
                text=texts["s1.email.vendor-intake"],
                thread="s1.intake",
                reply=False,
            )

        self._on("2026-03-18", _at(9, 40), baymark_v1)
        self._on("2026-03-18", _at(10, 5), vendor_intake)

        def baymark_v2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(15, 25),
                ref="s1.baymark",
                revision=2,
                author=_PN,
                content=_nda(
                    texts,
                    title=BAYMARK_NDA_TITLE,
                    body_key="s1.nda.baymark.body",
                    term=NDA_TERM_THREE,
                    residuals=False,
                ),
                summary="Conformed notice addresses and signature blocks.",
            )

        self._on("2026-03-26", _at(15, 25), baymark_v2)

        def archway_v1(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._doc(
                minter,
                drafts,
                at=_at(11, 15),
                ref="s1.archway",
                author=_NF,
                title=ARCHWAY_NDA_TITLE,
                path="/firm/vendor-ndas/mutual-nda-archway.md",
                content=_nda(
                    texts,
                    title=ARCHWAY_NDA_TITLE,
                    body_key="s1.nda.archway.body",
                    term=NDA_TERM_THREE,
                    residuals=False,
                ),
            )

        self._on("2026-04-09", _at(11, 15), archway_v1)

        def archway_v2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(14, 50),
                ref="s1.archway",
                revision=2,
                author=_NF,
                content=_nda(
                    texts,
                    title=ARCHWAY_NDA_TITLE,
                    body_key="s1.nda.archway.body",
                    term=NDA_TERM_THREE,
                    residuals=False,
                ),
                summary="Typo and citation fixes from proofread.",
            )

        self._on("2026-04-14", _at(14, 50), archway_v2)

        # Five more conforming vendor NDAs: the drift survey grades the
        # whole corpus, so the clean histories must outnumber the
        # divergent ones and cost real version walks.
        conforming_plans: tuple[
            tuple[str, str, str, tuple[str, int, str], tuple[str, int, str, str]], ...
        ] = (
            (
                "s1.trueline",
                TRUELINE_NDA_TITLE,
                "/firm/vendor-ndas/mutual-nda-trueline.md",
                ("2026-03-11", _at(10, 25), _NF),
                (
                    "2026-03-24",
                    _at(15, 10),
                    _PN,
                    "Conformed notice addresses and exhibit references.",
                ),
            ),
            (
                "s1.cobalt",
                COBALT_NDA_TITLE,
                "/firm/vendor-ndas/mutual-nda-cobalt.md",
                ("2026-04-02", _at(9, 45), _NF),
                (
                    "2026-04-21",
                    _at(14, 20),
                    _NF,
                    "Typo fixes and defined-terms cleanup from proofread.",
                ),
            ),
            (
                "s1.harborlight",
                HARBORLIGHT_NDA_TITLE,
                "/firm/vendor-ndas/mutual-nda-harborlight.md",
                ("2026-04-23", _at(11, 40), _NF),
                (
                    "2026-05-06",
                    _at(16, 15),
                    _PN,
                    "Updated the signature blocks for the renewal entities.",
                ),
            ),
            (
                "s1.brightwater",
                BRIGHTWATER_NDA_TITLE,
                "/firm/vendor-ndas/mutual-nda-brightwater.md",
                ("2026-05-18", _at(10, 5), _NF),
                (
                    "2026-06-02",
                    _at(15, 35),
                    _NF,
                    "Citation and cross-reference fixes from proofread.",
                ),
            ),
            (
                "s1.summit",
                SUMMIT_NDA_TITLE,
                "/firm/vendor-ndas/mutual-nda-summit.md",
                ("2026-06-09", _at(9, 30), _NF),
                (
                    "2026-06-22",
                    _at(14, 45),
                    _PN,
                    "Conformed notice addresses and signature blocks.",
                ),
            ),
        )
        for ref, title, path, created, revised in conforming_plans:
            body_key = f"s1.nda.{ref.removeprefix('s1.')}.body"
            content = _nda(
                texts,
                title=title,
                body_key=body_key,
                term=NDA_TERM_THREE,
                residuals=False,
            )
            v1_day, v1_clock, v1_author = created
            v2_day, v2_clock, v2_author, v2_summary = revised

            def create_beat(
                minter: IdMinter,
                drafts: list[TimedDraft],
                ref: str = ref,
                clock: int = v1_clock,
                author: str = v1_author,
                title: str = title,
                path: str = path,
                content: str = content,
            ) -> None:
                self._doc(
                    minter,
                    drafts,
                    at=clock,
                    ref=ref,
                    author=author,
                    title=title,
                    path=path,
                    content=content,
                )

            def revise_beat(
                minter: IdMinter,
                drafts: list[TimedDraft],
                ref: str = ref,
                clock: int = v2_clock,
                author: str = v2_author,
                content: str = content,
                summary: str = v2_summary,
            ) -> None:
                self._revise(
                    drafts,
                    at=clock,
                    ref=ref,
                    revision=2,
                    author=author,
                    content=content,
                    summary=summary,
                )

            self._on(v1_day, v1_clock, create_beat)
            self._on(v2_day, v2_clock, revise_beat)

        # June vendor re-papering: substantive riders land as v3s across
        # the corpus. Whether the day carries a covering email naming the
        # vendor is the silent-versions reconciliation: LexiPoint v2,
        # Ironclad v2, BayMark v3, and Harborlight v3 are covered;
        # Trueline, Cobalt, Archway, and Summit gain their riders with no
        # email that day (Summit's email lands the day after — the
        # off-by-one trap). Brightwater's v3 is a notices-only edit: a
        # real diff, but not a substantive one.
        extension_plans: tuple[
            tuple[str, str, str, str, int, str, tuple[tuple[str, str], ...], str],
            ...,
        ] = (
            (
                "s1.trueline",
                TRUELINE_NDA_TITLE,
                "2026-06-15",
                _NF,
                _at(11, 30),
                "Added the returns rider from the June vendor re-papering.",
                (("Return of Materials", NDA_RETURN_CLAUSE),),
                "trueline",
            ),
            (
                "s1.cobalt",
                COBALT_NDA_TITLE,
                "2026-06-16",
                _NF,
                _at(14, 45),
                "Added the returns rider from the June vendor re-papering.",
                (("Return of Materials", NDA_RETURN_CLAUSE),),
                "cobalt",
            ),
            (
                "s1.archway",
                ARCHWAY_NDA_TITLE,
                "2026-06-18",
                _NF,
                _at(10, 20),
                "Folded in the staffing rider agreed at the vendor call.",
                (("Non-Solicitation", NDA_NONSOLICIT_CLAUSE),),
                "archway",
            ),
            (
                "s1.baymark",
                BAYMARK_NDA_TITLE,
                "2026-06-18",
                _PN,
                _at(15, 40),
                "Added the returns rider from the June vendor re-papering.",
                (("Return of Materials", NDA_RETURN_CLAUSE),),
                "baymark",
            ),
            (
                "s1.harborlight",
                HARBORLIGHT_NDA_TITLE,
                "2026-06-23",
                _PN,
                _at(11, 15),
                "Added the returns rider from the June vendor re-papering.",
                (("Return of Materials", NDA_RETURN_CLAUSE),),
                "harborlight",
            ),
            (
                "s1.summit",
                SUMMIT_NDA_TITLE,
                "2026-06-25",
                _NF,
                _at(10, 35),
                "Folded in the staffing rider agreed at the vendor call.",
                (("Non-Solicitation", NDA_NONSOLICIT_CLAUSE),),
                "summit",
            ),
            (
                "s1.brightwater",
                BRIGHTWATER_NDA_TITLE,
                "2026-06-24",
                _PN,
                _at(9, 50),
                "Recorded the notice addresses for the renewal entities.",
                (("Notices", NDA_NOTICES_SECTION),),
                "brightwater",
            ),
        )
        for ref, title, day, author, clock, summary, extras, name in extension_plans:
            v3_content = _nda(
                texts,
                title=title,
                body_key=f"s1.nda.{name}.body",
                term=NDA_TERM_THREE,
                residuals=False,
                extras=extras,
            )

            def extend_beat(
                minter: IdMinter,
                drafts: list[TimedDraft],
                ref: str = ref,
                clock: int = clock,
                author: str = author,
                content: str = v3_content,
                summary: str = summary,
            ) -> None:
                self._revise(
                    drafts,
                    at=clock,
                    ref=ref,
                    revision=3,
                    author=author,
                    content=content,
                    summary=summary,
                )

            self._on(day, clock, extend_beat)

        def baymark_v3_cover(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(16, 10),
                sender=_PN,
                to=(_AB,),
                cc=(_NF,),
                subject="BayMark NDA — returns rider added",
                text=(
                    "Anita,\n\nAdded the returns rider to the BayMark IT "
                    "Solutions NDA and refiled the draft. No other changes "
                    "to the form.\n\nPeter"
                ),
                thread="s1.baymark-rider",
                reply=False,
            )

        self._on("2026-06-18", _at(16, 10), baymark_v3_cover)

        def harborlight_v3_cover(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(11, 45),
                sender=_PN,
                to=(_AB,),
                cc=(_NF,),
                subject="Harborlight NDA — returns rider added",
                text=(
                    "Anita,\n\nAdded the returns rider to the Harborlight "
                    "Records Storage NDA and refiled the draft. Signature "
                    "routing can pick it up with the next packet.\n\nPeter"
                ),
                thread="s1.harborlight-rider",
                reply=False,
            )

        self._on("2026-06-23", _at(11, 45), harborlight_v3_cover)

        def summit_rider_trap(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # The day-after email: it names Summit, but the rider landed
            # yesterday, so Summit's v3 day itself stays email-silent.
            self._email(
                minter,
                drafts,
                at=_at(9, 25),
                sender=_NF,
                to=(_AB,),
                cc=(_PN,),
                subject="Summit NDA — rider status",
                text=(
                    "Anita,\n\nFolded the staffing rider into the Summit "
                    "Staffing Partners draft yesterday; the refiled copy is "
                    "ready for signature routing.\n\nNoah"
                ),
                thread="s1.summit-rider",
                reply=False,
            )

        self._on("2026-06-26", _at(9, 25), summit_rider_trap)

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
                subject="Ironclad NDA — one remaining comment",
                text=texts["s1.email.ironclad-ask"],
                thread="s1.ironclad",
                reply=False,
            )

        def ironclad_thread(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(16, 5),
                sender=_NF,
                body=S1_IRONCLAD_THREAD_PARENT,
                ref="s1.ironclad-thread",
            )

        self._on("2026-06-03", _at(10, 45), ironclad_ask)
        self._on("2026-06-03", _at(16, 5), ironclad_thread)

        def ironclad_thread_reply(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(9, 40),
                sender=_NF,
                body=S1_IRONCLAD_THREAD_REPLY,
                reply_ref="s1.ironclad-thread",
            )

        self._on("2026-06-10", _at(9, 40), ironclad_thread_reply)

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
                subject="Re: Ironclad NDA — one remaining comment",
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

        # Near-miss distractors: tranche-1 diligence before the budget-call
        # cutoff. A whole-April (or all-diligence) keyword sum is wrong.
        spike: tuple[tuple[str, int, str, int, str], ...] = (
            (
                "2026-03-31",
                _at(17, 30),
                _PN,
                85,
                "Data room setup and document index, tranche 1 — original "
                "scope (Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-01",
                _at(17, 50),
                _ML,
                110,
                "Initial data room diligence review, tranche 1 — corporate "
                "records (Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-02",
                _at(18, 0),
                _PN,
                70,
                "Data room QC pass, tranche 1 (Meridian diagnostics acquisition).",
            ),
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
        # Precision decoys around the disputed bucket: an entry ON the
        # cutoff day (excluded by the strict "after"), diligence-worded
        # entries on OTHER matters after the cutoff (excluded by the
        # matter join), and post-cutoff Meridian work that describes the
        # expanded scope without the diligence/data-room wording
        # (excluded by the stated narrative filter). None of them move
        # the true totals; every looser query sweeps some of them in.
        decoys: tuple[tuple[str, int, str, str, int, str], ...] = (
            (
                "2026-04-03",
                _at(17, 15),
                _PN,
                S2_TICKET,
                60,
                "Data room access coordination ahead of the tranche 2 "
                "kickoff (Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-08",
                _at(18, 20),
                _ML,
                S3_TICKET,
                95,
                "Diligence review of Fathom Systems IP chain-of-title "
                "representations (Lumen licensing agreement).",
            ),
            (
                "2026-04-14",
                _at(18, 35),
                _PN,
                "tkt-000005",
                120,
                "Organize seller data room and confirm disclosure "
                "schedule index (Solstice asset purchase closing).",
            ),
            (
                "2026-04-22",
                _at(17, 35),
                _ML,
                S2_TICKET,
                105,
                "Follow-up review of regulatory files flagged in the "
                "April scope expansion (Meridian diagnostics acquisition).",
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
        # Unsupported window work: post-cutoff Meridian entries on days
        # where no message names the engagement. Their notes stay clear
        # of the diligence wording so the disputed set never moves; they
        # exist to be found by the support audit, not the fee join.
        unsupported: tuple[tuple[str, int, str, int, str], ...] = (
            (
                "2026-04-17",
                _at(17, 20),
                _PN,
                55,
                "Update the closing checklist and signature tracker "
                "(Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-22",
                _at(18, 15),
                _ML,
                40,
                "Call with client team on regulatory consent timing "
                "(Meridian diagnostics acquisition).",
            ),
            (
                "2026-04-28",
                _at(17, 50),
                _PN,
                50,
                "Assemble the regulatory consent tracker for signing "
                "(Meridian diagnostics acquisition).",
            ),
        )
        for day, clock, person, minutes, note in unsupported:

            def unsupported_entry(
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

            self._on(day, clock, unsupported_entry)
        for day, clock, person, ticket, minutes, note in decoys:

            def decoy_entry(
                minter: IdMinter,
                drafts: list[TimedDraft],
                clock: int = clock,
                person: str = person,
                ticket: str = ticket,
                minutes: int = minutes,
                note: str = note,
            ) -> None:
                self._time(
                    drafts,
                    at=clock,
                    person=person,
                    ticket=ticket,
                    minutes=minutes,
                    note=note,
                )

            self._on(day, clock, decoy_entry)

        # The April data-room sprint: a heavy, matter-blind DM lane
        # between the deal associate and the deal paralegal. Two dated
        # texts name the client (the only support their days have); every
        # other line stays ambiguous between the Meridian and Solstice
        # data rooms, so it supports nothing under the marker rule.
        for day_index, sprint_day in enumerate(S2_SPRINT_DAYS):
            for slot, (hour, minute) in enumerate(S2_SPRINT_CLOCKS):
                body = S2_SPRINT_LINES[
                    (day_index * len(S2_SPRINT_CLOCKS) + slot) % len(S2_SPRINT_LINES)
                ]
                if slot == 2 and sprint_day in S2_DM_COVERAGE_TEXTS:
                    body = S2_DM_COVERAGE_TEXTS[sprint_day]
                sender = _PN if slot % 2 == 0 else _ML

                def sprint_beat(
                    minter: IdMinter,
                    drafts: list[TimedDraft],
                    clock: int = _at(hour, minute),
                    sender: str = sender,
                    body: str = body,
                ) -> None:
                    self._chat(
                        minter,
                        drafts,
                        at=clock,
                        sender=sender,
                        body=body,
                        conversation=self._marcus_peter_dm,
                    )

                self._on(sprint_day, _at(hour, minute), sprint_beat)

        for day, clock, sender, recipient, subject, body in S2_OBLIQUE_EMAILS:

            def oblique_beat(
                minter: IdMinter,
                drafts: list[TimedDraft],
                clock: int = _at(*clock),
                sender: str = sender,
                recipient: str = recipient,
                subject: str = subject,
                body: str = body,
            ) -> None:
                self._email(
                    minter,
                    drafts,
                    at=clock,
                    sender=sender,
                    to=(recipient,),
                    subject=subject,
                    text=body,
                    thread=f"s2.oblique.{subject}",
                    reply=False,
                )

            self._on(day, _at(*clock), oblique_beat)

        def consent_tracker_oblique(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # Same-day-oblique near miss on the new orphan day: deal-
            # flavored mail that never names the engagement under the
            # marker rule, so the day stays silent for the support audit.
            self._email(
                minter,
                drafts,
                at=_at(16, 40),
                sender=_PN,
                to=(_ML,),
                subject="Consent tracker — signing prep",
                text=(
                    "Marcus,\n\nConsent tracker is assembled through "
                    "today's mail. Two counterparties have not returned "
                    "countersigned consents; chasing both tomorrow "
                    "morning.\n\nPeter"
                ),
                thread="s2.consents",
                reply=False,
            )

        self._on("2026-04-28", _at(16, 40), consent_tracker_oblique)

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

        def cutoff_posted(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(14, 5),
                sender=_CJ,
                body=S2_CUTOFF_CHAT,
                conversation=self._billing_channel,
            )

        self._on("2026-05-12", _at(8, 55), pull_time)
        self._on("2026-05-12", _at(13, 20), time_summary)
        self._on("2026-05-12", _at(14, 5), cutoff_posted)

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
                    texts,
                    fees_key="s3.agreement.fees.v1",
                    indemnity=True,
                    circulated="March 31, 2026",
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
                    texts,
                    fees_key="s3.agreement.fees.v2",
                    indemnity=True,
                    circulated="April 21, 2026",
                ),
                summary="Incorporated licensee review comments; recirculated.",
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

        def v3(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(15, 40),
                ref="s3.agreement",
                revision=3,
                author=_ML,
                content=_lumen_agreement(
                    texts,
                    fees_key="s3.agreement.fees.v2",
                    indemnity=True,
                    circulated="April 28, 2026",
                ),
                summary="Drafting pass after internal review.",
            )

        self._on("2026-04-28", _at(15, 40), v3)

        # Distractor: a similarly named Lumen document with a clean,
        # uneventful four-version history and no indemnity language.
        def sow_v1(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._doc(
                minter,
                drafts,
                at=_at(14, 25),
                ref="s3.sow",
                author=_ML,
                title=LUMEN_SOW_TITLE,
                path="/lumen-licensing/support-services-sow.md",
                content=_lumen_sow(texts, circulated="April 7, 2026"),
            )

        self._on("2026-04-07", _at(14, 25), sow_v1)

        def sow_v2(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(10, 50),
                ref="s3.sow",
                revision=2,
                author=_PN,
                content=_lumen_sow(texts, circulated="April 24, 2026"),
                summary="Formatting cleanup and exhibit relabeling.",
            )

        self._on("2026-04-24", _at(10, 50), sow_v2)

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

        def v4(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(9, 45),
                ref="s3.agreement",
                revision=4,
                author=_ML,
                content=_lumen_agreement(
                    texts,
                    fees_key="s3.agreement.fees.v2",
                    indemnity=False,
                    circulated="May 21, 2026",
                ),
                summary="Conformed the draft following the call with "
                "licensor's counsel.",
            )

        self._on("2026-05-21", _at(9, 45), v4)

        def v5(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(16, 20),
                ref="s3.agreement",
                revision=5,
                author=_PN,
                content=_lumen_agreement(
                    texts,
                    fees_key="s3.agreement.fees.v2",
                    indemnity=False,
                    circulated="May 28, 2026",
                ),
                summary="Formatting and numbering cleanup.",
            )

        self._on("2026-05-28", _at(16, 20), v5)

        def sow_v3(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(15, 30),
                ref="s3.sow",
                revision=3,
                author=_ML,
                content=_lumen_sow(texts, circulated="May 26, 2026"),
                summary="Updated the staffing exhibit after internal review.",
            )

        self._on("2026-05-26", _at(15, 30), sow_v3)

        def v6(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(11, 35),
                ref="s3.agreement",
                revision=6,
                author=_ML,
                content=_lumen_agreement(
                    texts,
                    fees_key="s3.agreement.fees.v2",
                    indemnity=False,
                    circulated="June 3, 2026",
                ),
                summary="Defined-terms tidy ahead of the signature packet.",
            )

        self._on("2026-06-03", _at(11, 35), v6)

        def v7(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(15, 15),
                ref="s3.agreement",
                revision=7,
                author=_PN,
                content=_lumen_agreement(
                    texts,
                    fees_key="s3.agreement.fees.v2",
                    indemnity=False,
                    circulated="June 8, 2026",
                ),
                summary="Final proof for the signature packet.",
            )

        def sow_v4(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._revise(
                drafts,
                at=_at(15, 45),
                ref="s3.sow",
                revision=4,
                author=_PN,
                content=_lumen_sow(texts, circulated="June 8, 2026"),
                summary="Proof pass for the signature packet.",
            )

        self._on("2026-06-08", _at(15, 15), v7)
        self._on("2026-06-08", _at(15, 45), sow_v4)

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

        def quote_indemnity(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # Tempting wrong anchor: after the drop, the client quotes the
            # OLD (v2-era) licensor indemnity verbatim in the email record.
            self._email(
                minter,
                drafts,
                at=_at(11, 35),
                sender=_JUNE,
                to=(_ML,),
                subject="Re: Lumen — license and support agreement, first draft",
                text=texts["s3.email.quote-indemnity"] + "\n\n> " + INDEMNITY_PARAGRAPH,
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
        self._on("2026-06-09", _at(11, 35), quote_indemnity)
        self._on("2026-06-09", _at(13, 15), final_confirm)

    # S4 — Cascadia sours across six weeks, then terminates.

    def _register_s4(self) -> None:
        texts = self._texts

        # Client-side correspondence fabric: most of Tom's emails draw an
        # in-thread firm reply (some late, one only after a double-send);
        # the ignored ones are the unanswered-client-emails anti-join.
        def docs_ask(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(9, 55),
                sender=_TOM,
                to=(_SR,),
                subject=S4_DOCS_SUBJECT,
                text=S4_DOCS_ASK,
                thread="s4.docs",
                reply=False,
            )

        def docs_reply(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(15, 45),
                sender=_SR,
                to=(_TOM,),
                subject=f"Re: {S4_DOCS_SUBJECT}",
                text=S4_DOCS_REPLY,
                thread="s4.docs",
                reply=True,
            )

        self._on("2026-03-10", _at(9, 55), docs_ask)
        self._on("2026-03-10", _at(15, 45), docs_reply)

        def docs_followup(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 35),
                sender=_TOM,
                to=(_SR,),
                subject=f"Re: {S4_DOCS_SUBJECT}",
                text=S4_DOCS_FOLLOWUP,
                thread="s4.docs",
                reply=True,
            )

        self._on("2026-03-31", _at(10, 35), docs_followup)

        def docs_followup_reply(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # Answered the next day — in-thread, so still answered under
            # the thread rule; a same-day misreading lists it anyway.
            self._email(
                minter,
                drafts,
                at=_at(9, 40),
                sender=_SR,
                to=(_TOM,),
                subject=f"Re: {S4_DOCS_SUBJECT}",
                text=S4_DOCS_FOLLOWUP_REPLY,
                thread="s4.docs",
                reply=True,
            )

        self._on("2026-04-01", _at(9, 40), docs_followup_reply)

        def invoice_ask(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(10, 5),
                sender=_TOM,
                to=(_AB,),
                subject=S4_INVOICE_SUBJECT,
                text=S4_INVOICE_ASK,
                thread="s4.invoice",
                reply=False,
            )

        def invoice_reply(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(14, 10),
                sender=_AB,
                to=(_TOM,),
                subject=f"Re: {S4_INVOICE_SUBJECT}",
                text=S4_INVOICE_REPLY,
                thread="s4.invoice",
                reply=True,
            )

        self._on("2026-04-08", _at(10, 5), invoice_ask)
        self._on("2026-04-08", _at(14, 10), invoice_reply)

        def notes_first(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(11, 5),
                sender=_TOM,
                to=(_SM,),
                subject=S4_NOTES_SUBJECT,
                text=S4_NOTES_FIRST,
                thread="s4.notes",
                reply=False,
            )

        def notes_second(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._email(
                minter,
                drafts,
                at=_at(11, 20),
                sender=_TOM,
                to=(_SM,),
                subject=f"Re: {S4_NOTES_SUBJECT}",
                text=S4_NOTES_SECOND,
                thread="s4.notes",
                reply=True,
            )

        def notes_reply(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # One firm reply after a client double-send answers both under
            # the thread rule; listing the first is the trap.
            self._email(
                minter,
                drafts,
                at=_at(15, 30),
                sender=_SM,
                to=(_TOM,),
                cc=(_SR,),
                subject=f"Re: {S4_NOTES_SUBJECT}",
                text=S4_NOTES_REPLY,
                thread="s4.notes",
                reply=True,
            )

        self._on("2026-05-11", _at(11, 5), notes_first)
        self._on("2026-05-11", _at(11, 20), notes_second)
        self._on("2026-05-11", _at(15, 30), notes_reply)

        def transfer_ask(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # Post-termination logistics question nobody ever answers —
            # the fourth member of the anti-join.
            self._email(
                minter,
                drafts,
                at=_at(10, 15),
                sender=_TOM,
                to=(_GA,),
                subject=S4_TRANSFER_SUBJECT,
                text=S4_TRANSFER_ASK,
                thread="s4.transfer",
                reply=False,
            )

        self._on("2026-06-08", _at(10, 15), transfer_ask)

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

        def memo_email(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # The status memo goes out the evening of concern3 — but in a
            # NEW thread, so under the thread rule it answers nothing.
            self._email(
                minter,
                drafts,
                at=_at(19, 5),
                sender=_SR,
                to=(_TOM,),
                cc=(_SM,),
                subject=S4_MEMO_SUBJECT,
                text=S4_MEMO_BODY,
                thread="s4.memo",
                reply=False,
            )

        self._on("2026-05-06", _at(19, 5), memo_email)

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

        def stale_outline(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # Sofia was not on the clerk's reset notice: four days after
            # the reset she still briefs against the April 28 setting.
            self._email(
                minter,
                drafts,
                at=_at(14, 5),
                sender=_SR,
                to=(_SM,),
                cc=(_GA,),
                subject=S5_STALE_OUTLINE_SUBJECT,
                text=S5_STALE_OUTLINE_BODY,
                thread="s5.outline",
                reply=False,
            )

        def outline_reply(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # The correction cites the then-operative May 20 — a date
            # mention that is NOT stale, because it reports the move.
            self._email(
                minter,
                drafts,
                at=_at(16, 20),
                sender=_SM,
                to=(_SR,),
                cc=(_GA,),
                subject=f"Re: {S5_STALE_OUTLINE_SUBJECT}",
                text=S5_OUTLINE_REPLY_BODY,
                thread="s5.outline",
                reply=True,
            )

        self._on("2026-04-21", _at(14, 5), stale_outline)
        self._on("2026-04-21", _at(16, 20), outline_reply)

        def stale_copies_chat(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # Sofia works from Samuel's April correction ("May 20") and
            # never saw the stipulated reset — stale again, and corrected
            # again in the reply.
            self._chat(
                minter,
                drafts,
                at=_at(10, 25),
                sender=_SR,
                body=S5_STALE_COPIES_CHAT,
                ref="s5.copies",
            )
            self._chat(
                minter,
                drafts,
                at=_at(10, 50),
                sender=_GA,
                body=S5_COPIES_REPLY_CHAT,
                reply_ref="s5.copies",
            )

        self._on("2026-05-15", _at(10, 25), stale_copies_chat)

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

        # The week of the correction: unrelated deadline chatter in
        # #matters so date-and-deadline keyword searches surface noise.
        def goldleaf_moved(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(9, 50),
                sender=_SR,
                body="Goldleaf: the court moved our case management "
                "hearing — now Monday June 22, 9:30 a.m., Dept. 17. "
                "Briefing dates track the new date.",
                ref="s5.goldleaf",
            )
            self._chat(
                minter,
                drafts,
                at=_at(10, 5),
                sender=_SM,
                body="Calendared, thanks.",
                reply_ref="s5.goldleaf",
            )

        self._on("2026-06-08", _at(9, 50), goldleaf_moved)

        def pelican_deadline(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(14, 35),
                sender=_DO,
                body="Pelican Bay: the renewal option notice deadline is "
                "June 30 — Noah, the draft notice is with you; it needs "
                "to go out certified mail.",
                ref="s5.pelican",
            )
            self._chat(
                minter,
                drafts,
                at=_at(15, 0),
                sender=_NF,
                body="On it — notice out by Friday.",
                reply_ref="s5.pelican",
            )

        self._on("2026-06-10", _at(14, 35), pelican_deadline)

        def correction_dm(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # The operative date exists only here, buried mid-stream in the
            # long-running Grace<->Samuel DM that public-channel search
            # cannot reach, with no case name and no docket vocabulary —
            # just the Clio display-number prefix.
            self._chat(
                minter,
                drafts,
                at=_at(11, 25),
                sender=_GA,
                body=S5_DM_CORRECTION,
                ref="s5.correction",
                conversation=self._grace_samuel_dm,
            )
            self._chat(
                minter,
                drafts,
                at=_at(11, 40),
                sender=_SM,
                body=S5_DM_ACK,
                reply_ref="s5.correction",
                conversation=self._grace_samuel_dm,
            )

        self._on("2026-06-11", _at(11, 25), correction_dm)

        def brightline_deadline(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(11, 10),
                sender=_SM,
                body="Brightline: position statement is due to the agency "
                "July 2. Sofia, let's lock the outline Thursday.",
            )

        self._on("2026-06-12", _at(11, 10), brightline_deadline)

        def stale_victor_email(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # Opposing counsel never got the clerk's call: the day after
            # the DM correction he confirms logistics for June 18. Nobody
            # replies — a correction by email would leak the operative
            # date out of the DM.
            self._email(
                minter,
                drafts,
                at=_at(11, 30),
                sender=_VICTOR,
                to=(_SM,),
                cc=(_SR,),
                subject=S5_STALE_VICTOR_SUBJECT,
                text=S5_STALE_VICTOR_BODY,
                thread="s5.logistics",
                reply=False,
            )

        self._on("2026-06-12", _at(11, 30), stale_victor_email)

        def stale_binder_chat(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            self._chat(
                minter,
                drafts,
                at=_at(9, 45),
                sender=_SR,
                body=S5_STALE_BINDER_CHAT,
            )

        self._on("2026-06-15", _at(9, 45), stale_binder_chat)

        def stale_recap(minter: IdMinter, drafts: list[TimedDraft]) -> None:
            # Post-correction trap: a formal-looking recap compiled from
            # the stale master calendar restates the superseded June 18
            # setting five days after the DM correction.
            self._email(
                minter,
                drafts,
                at=_at(9, 35),
                sender=_PN,
                to=(_SM, _SR),
                cc=(_GA,),
                subject=S5_RECAP_SUBJECT,
                text=S5_RECAP_BODY,
                thread="s5.recap",
                reply=False,
            )

        self._on("2026-06-16", _at(9, 35), stale_recap)

    # Firm fabric — additive revision histories for the genesis firm
    # documents. They exist so version surveys cost real work: many
    # multi-version drafts with innocuous comments where nothing
    # substantive ever disappears.

    def _register_fabric(self, genesis: HartwellGenesis) -> None:
        texts = self._texts

        def genesis_doc(title: str) -> tuple[str, str]:
            payload = next(
                event.payload
                for event in genesis.events
                if event.payload.kind == "document.created"
                and event.payload.title == title
            )
            return payload.document_id, payload.content

        def extended(base: str, sections: tuple[tuple[str, str], ...]) -> str:
            parts = [base.rstrip()]
            for heading, body in sections:
                parts += ["", f"## {heading}", "", body.strip()]
            return "\n".join(parts) + "\n"

        def revise_on(
            day: str,
            clock: int,
            *,
            ref: str,
            revision: int,
            author: str,
            content: str,
            summary: str,
        ) -> None:
            def beat(minter: IdMinter, drafts: list[TimedDraft]) -> None:
                self._revise(
                    drafts,
                    at=clock,
                    ref=ref,
                    revision=revision,
                    author=author,
                    content=content,
                    summary=summary,
                )

            self._on(day, clock, beat)

        ecomm = (
            "The firm and the client consent to electronic delivery of "
            "correspondence, invoices, and drafts through the client "
            "portal, and to signatures by a reliable electronic signature "
            "service."
        )
        routing = (
            "- Confirm the signed engagement letter is filed before the "
            "first time entry.\n"
            "- Route signature packets through the records clerk.\n"
            "- Calendar the first status update within thirty days of "
            "opening."
        )
        prebill = (
            "Prebills circulate on the second Thursday of the month; "
            "edits are due back by Friday noon; invoices go out the "
            "following Tuesday."
        )
        meet_confer = (
            "Schedule the meet and confer within ten days of receiving "
            "requests; confirm agreements in a letter the same week."
        )

        # ref, title, [(day, clock, revision author, comment, sections)]
        plans: tuple[
            tuple[str, str, tuple[tuple[str, int, str, str, tuple], ...]], ...
        ] = (
            (
                "fabric.engagement",
                "Engagement Letter (Standard Form)",
                (
                    (
                        "2026-03-19",
                        _at(10, 30),
                        _DO,
                        "Refreshed the fee and billing practices section "
                        "for the new rate schedule.",
                        (
                            (
                                "Fees and billing practices",
                                texts["fabric.engagement.fees"],
                            ),
                        ),
                    ),
                    (
                        "2026-05-22",
                        _at(14, 40),
                        _NF,
                        "Added the client portal and electronic signature "
                        "consent language.",
                        (
                            (
                                "Fees and billing practices",
                                texts["fabric.engagement.fees"],
                            ),
                            ("Electronic communications", ecomm),
                        ),
                    ),
                ),
            ),
            (
                "fabric.intake",
                "Matter Intake Checklist",
                (
                    (
                        "2026-04-08",
                        _at(11, 45),
                        _GA,
                        "Expanded the conflicts screening steps after the "
                        "quarterly review.",
                        (("Conflicts screening", texts["fabric.intake.conflicts"]),),
                    ),
                    (
                        "2026-06-17",
                        _at(15, 20),
                        _GA,
                        "Aligned signature routing with the current records workflow.",
                        (
                            ("Conflicts screening", texts["fabric.intake.conflicts"]),
                            ("Engagement letter routing", routing),
                        ),
                    ),
                ),
            ),
            (
                "fabric.billing",
                "Billing & Time Entry Guidelines",
                (
                    (
                        "2026-04-29",
                        _at(9, 55),
                        _CJ,
                        "Clarified the narrative standards ahead of the May prebills.",
                        (("Narrative standards", texts["fabric.billing.narratives"]),),
                    ),
                    (
                        "2026-06-23",
                        _at(16, 10),
                        _CJ,
                        "Updated the prebill calendar for the third quarter.",
                        (
                            ("Narrative standards", texts["fabric.billing.narratives"]),
                            ("Prebill calendar", prebill),
                        ),
                    ),
                ),
            ),
            (
                "fabric.hold",
                "Litigation Hold Notice (Template)",
                (
                    (
                        "2026-05-06",
                        _at(13, 35),
                        _SR,
                        "Broadened the preservation scope list for "
                        "messaging applications.",
                        (("Preservation scope", texts["fabric.hold.scope"]),),
                    ),
                ),
            ),
            (
                "fabric.discovery",
                "Discovery Response Playbook",
                (
                    (
                        "2026-04-22",
                        _at(10, 15),
                        _SR,
                        "Added the ESI protocol checklist.",
                        (("ESI protocol checklist", texts["fabric.discovery.esi"]),),
                    ),
                    (
                        "2026-06-19",
                        _at(11, 50),
                        _SM,
                        "Recorded the meet and confer timing guidance.",
                        (
                            ("ESI protocol checklist", texts["fabric.discovery.esi"]),
                            ("Meet and confer", meet_confer),
                        ),
                    ),
                ),
            ),
        )
        for ref, title, revisions in plans:
            document_id, base = genesis_doc(title)
            self._refs[f"d:{ref}"] = document_id
            for number, (day, clock, author, summary, sections) in enumerate(
                revisions, start=2
            ):
                revise_on(
                    day,
                    clock,
                    ref=ref,
                    revision=number,
                    author=author,
                    content=extended(base, sections),
                    summary=summary,
                )

    def _register_mention_fabric(self) -> None:
        # Same-day document mentions for most version saves; the revision
        # days deliberately left out are the unreviewed-revisions set.
        for day, hour, minute, sender, channel, body in MENTION_FABRIC:
            conversation = (
                self._billing_channel if channel == "billing" else self._matters_channel
            )

            def mention_beat(
                minter: IdMinter,
                drafts: list[TimedDraft],
                clock: int = _at(hour, minute),
                sender: str = sender,
                body: str = body,
                conversation: str = conversation,
            ) -> None:
                self._chat(
                    minter,
                    drafts,
                    at=clock,
                    sender=sender,
                    body=body,
                    conversation=conversation,
                )

            self._on(day, _at(hour, minute), mention_beat)

    def _register_april_dm_lanes(self) -> None:
        lanes: tuple[tuple[str, str, str, tuple, tuple[str, ...]], ...] = (
            (
                self._anita_carl_dm,
                _AB,
                _CJ,
                APRIL_BILLING_DM_CLOCKS,
                APRIL_BILLING_DM_LINES,
            ),
            (
                self._grace_peter_dm,
                _GA,
                _PN,
                APRIL_RECORDS_DM_CLOCKS,
                APRIL_RECORDS_DM_LINES,
            ),
        )
        for conversation, first, second, clocks, lines in lanes:
            for day_index, day in enumerate(APRIL_WORKDAYS):
                for slot, (hour, minute) in enumerate(clocks):
                    body = lines[(day_index * len(clocks) + slot) % len(lines)]
                    sender = first if slot % 2 == 0 else second

                    def lane_beat(
                        minter: IdMinter,
                        drafts: list[TimedDraft],
                        clock: int = _at(hour, minute),
                        sender: str = sender,
                        body: str = body,
                        conversation: str = conversation,
                    ) -> None:
                        self._chat(
                            minter,
                            drafts,
                            at=clock,
                            sender=sender,
                            body=body,
                            conversation=conversation,
                        )

                    self._on(day, _at(hour, minute), lane_beat)
