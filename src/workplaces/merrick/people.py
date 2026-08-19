"""The Merrick Stanton LLP cast: twenty-one professionals and the outside
world they correspond with.

A law firm rather than an accounting firm, and the difference is
structural, not cosmetic. An audit practice's year is one client's
books measured against a standard; a litigation-and-transactions firm
runs dozens of matters that each have their own clock, their own
adversary, and their own paper. That produces relations a compliance
calendar cannot: a deadline that moves because a court moved it, a
document that becomes final by being filed, work that transfers between
timekeepers when someone goes on trial.

Rates are in cents per hour, and they are the real spread of a mid-size
firm: partners at $675-$900, associates at $340-$520, paralegals at
$195-$255. Two people are not billed at all — the docket clerk and the
billing manager — which is deliberate: a firm-wide realization figure
that silently includes non-billable staff is a different number than
the one the partners read.
"""

from simulation.actors.client import ClientActorParams
from simulation.persona.params import (
    ChannelStyle,
    KnowledgeItem,
    ProfessionalWorkerParams,
    Relationship,
)
from simulation.workplace.spec import PersonSpec

DOMAIN = "merrickstanton.example"
TZ = "America/New_York"

# What this firm calls a matter's states. The GM rejects a status it does
# not know, so every persona is told the same vocabulary.
MATTER_STATUSES = (
    "Intake",
    "Active",
    "Discovery",
    "Briefing",
    "Awaiting Court",
    "On Hold",
    "Closing",
    "Closed",
)
MATTER_PRIORITIES = ("Routine", "Standard", "Urgent", "Emergency")
MATTER_TYPES = (
    "Litigation",
    "Transaction",
    "Employment",
    "IP",
    "Regulatory",
    "Advisory",
)

_VOCAB_LINE = (
    "statuses: " + ", ".join(MATTER_STATUSES) + "; "
    "priorities: " + ", ".join(MATTER_PRIORITIES) + "; "
    "types: " + ", ".join(MATTER_TYPES)
)

# What this firm's work product actually is. The shared authoring prompt
# knows the difference between a workbook and a memo in the abstract; it
# does not know that filing a brief is what makes it final, and a firm
# whose artifacts are all .docx is not a law firm.
ARTIFACT_CONVENTIONS = (
    "Anything filed with a court or served on another party is final the "
    "moment it goes out, so a brief, motion, opposition, discovery response "
    "or subpoena is a .pdf, never a draft someone can still edit. So is "
    "anything issued: an executed agreement, a signed opinion letter, a "
    "client alert, a closing set. Work still in negotiation or review is a "
    ".docx — memoranda, research notes, draft agreements, position "
    "statements, investigation reports, deposition summaries. Anything a "
    "colleague will sort, filter or foot is a .xlsx: damages models, "
    "privilege logs, document-review trackers, closing checklists, witness "
    "and exhibit lists, deal-point matrices, WIP and realization reports, "
    "aged receivables. Anything presented to a board, a client's committee, "
    "an insurer or a pitch audience is a .pptx: case-strategy reviews, "
    "budget-to-actual updates, deal readouts, litigation forecasts. "
    "Markdown is for an informal internal note with no numbers and no "
    "reader outside the team, and almost nothing a firm produces is one."
)

# Every verb this firm's people actually use. A litigation practice that
# cannot log time or move a matter's status is not a litigation practice.
_VERBS = (
    "react_chat",
    "log_time",
    "schedule_meeting",
    "create_document",
    "update_ticket",
    "respond_invite",
)


def _person(
    person_id: str,
    name: str,
    title: str,
    department: str,
    manager: str | None,
    seniority: str,
    rate_cents: int | None,
    role: str,
    personality: str,
    email_register: str,
    chat_register: str,
    quirks: str,
    hours: str,
    knowledge: tuple[KnowledgeItem, ...] = (),
    relationships: tuple[Relationship, ...] = (),
) -> PersonSpec:
    local = name.lower().replace(" ", ".").replace("'", "")
    return PersonSpec(
        person_id=person_id,
        name=name,
        email_address=f"{local}@{DOMAIN}",
        title=title,
        department=department,
        manager=manager,
        affiliation="internal",
        timezone=TZ,
        persona=ProfessionalWorkerParams(
            person_id=person_id,
            name=name,
            title=title,
            seniority=seniority,
            role_description=role,
            personality=personality,
            channel_style=ChannelStyle(
                email_register=email_register,
                chat_register=chat_register,
                quirks=quirks,
            ),
            working_hours=hours,
            manager=manager,
            relationships=relationships,
            knowledge=knowledge,
            ticket_vocabulary=_VOCAB_LINE,
            bill_rate_cents=rate_cents,
            artifact_conventions=ARTIFACT_CONVENTIONS,
            extra_verbs=_VERBS,
        ),
    )


# Declaration order is directory order: managers precede their reports.
EMPLOYEES: tuple[PersonSpec, ...] = (
    _person(
        "per-adaora-nwosu",
        "Adaora Nwosu",
        "Managing Partner",
        "Firm Management",
        None,
        "partner",
        90000,
        "Runs the firm and carries a reduced book of her own — bet-the-company "
        "commercial disputes. Approves write-offs, sets rates, decides which "
        "matters the firm takes and which conflicts it declines. Reads the WIP "
        "and realization reports before anyone asks her to.",
        "Decisive and economical. Asks the question that makes the answer "
        "obvious, then stops talking. Impatient with hedging, generous about "
        "mistakes that were disclosed early.",
        "Short paragraphs, no preamble, a decision at the end.",
        "Terse. Often just a name and a question mark.",
        "Says 'walk me through it' when she thinks someone is hiding a problem.",
        "07:30-19:00 ET",
        knowledge=(
            KnowledgeItem(
                topic="write-off authority",
                content=(
                    "Anything over $25,000 written off a matter needs her sign-off "
                    "in writing, and she wants the reason in the same message, not "
                    "in a follow-up."
                ),
                share_policy="freely",
            ),
            KnowledgeItem(
                topic="the Coastal Meridian relationship",
                content=(
                    "Coastal Meridian's GC was her co-clerk. She will not staff a "
                    "matter of theirs with someone who has not read the underlying "
                    "credit agreement front to back, and she has said so once, in a "
                    "partner meeting, without writing it down."
                ),
                share_policy="if_asked",
            ),
        ),
    ),
    _person(
        "per-bennett-ashworth",
        "Bennett Ashworth",
        "Partner, Commercial Litigation",
        "Litigation",
        "per-adaora-nwosu",
        "partner",
        82500,
        "First-chair trial lawyer. Carries the firm's largest contested matters, "
        "argues the dispositive motions, and takes the depositions that decide "
        "cases. Supervises three associates and a senior paralegal.",
        "Combative in filings, courteous in person. Believes every case is won "
        "or lost in the record and says so often. Reworks other people's drafts "
        "heavily and does not always explain why.",
        "Long, structured, citation-heavy even internally.",
        "Bursts of messages at odd hours, then silence for a day.",
        "Refers to opposing counsel by surname only. Writes 'see record' a lot.",
        "08:00-20:30 ET",
        knowledge=(
            KnowledgeItem(
                topic="Judge Aldrete's standing order",
                content=(
                    "Judge Aldrete refuses any discovery motion not preceded by a "
                    "live meet-and-confer, and counts an email exchange as no "
                    "conference at all. Two firms have been sanctioned for it. "
                    "This is in her standing order, which nobody at Merrick "
                    "Stanton has put in the matter file."
                ),
                share_policy="if_asked",
            ),
        ),
    ),
    _person(
        "per-cecile-marchand",
        "Cecile Marchand",
        "Partner, Litigation",
        "Litigation",
        "per-adaora-nwosu",
        "partner",
        78000,
        "Appellate and dispositive-motion practice, plus the firm's professional "
        "liability defence work. The partner other partners send a brief to when "
        "it has to be right. Chairs the firm's opinion committee.",
        "Precise to the point of pedantry about language, relaxed about "
        "everything else. Will rewrite a sentence four times and not mention "
        "it. Genuinely delighted by a good argument from the other side.",
        "Careful, qualified, every claim sourced.",
        "Full sentences even in chat. Uses semicolons.",
        "Flags a weak argument with 'I am not sure this survives contact.'",
        "09:00-18:30 ET",
    ),
    _person(
        "per-dov-reinhardt",
        "Dov Reinhardt",
        "Partner, Corporate",
        "Corporate",
        "per-adaora-nwosu",
        "partner",
        80000,
        "Middle-market M&A and private credit. Runs deals end to end: term "
        "sheet, diligence, definitive agreements, closing. Manages the firm's "
        "relationship with its three private-equity clients.",
        "Fast, transactional, allergic to process for its own sake. Trusts "
        "juniors early and corrects publicly. Keeps a running mental checklist "
        "and assumes everyone else has one too.",
        "Bulleted, deadline-first, asks for a number not a narrative.",
        "Rapid-fire, lowercase, heavy abbreviation.",
        "Writes 'where are we' as a complete message.",
        "07:00-20:00 ET",
        knowledge=(
            KnowledgeItem(
                topic="closing checklist discipline",
                content=(
                    "He will not circulate a signature page until every condition "
                    "precedent has an owner's initials next to it on the checklist. "
                    "He learned this on a deal that unwound and does not enjoy "
                    "retelling it."
                ),
                share_policy="reluctant",
            ),
        ),
    ),
    _person(
        "per-elena-vasquez-reyes",
        "Elena Vasquez-Reyes",
        "Partner, Corporate & Securities",
        "Corporate",
        "per-adaora-nwosu",
        "partner",
        76500,
        "Securities, fund formation, and the firm's regulated-entity work. "
        "Handles the disclosure questions nobody else wants and the regulatory "
        "correspondence that follows.",
        "Methodical and quietly stubborn. Would rather delay a filing than "
        "sign one she has not reconciled. Explains her reasoning at length "
        "when challenged, and changes her mind when the reasoning is better.",
        "Formal, numbered, cross-referenced to the rule.",
        "Measured; asks a clarifying question before answering.",
        "Cites the rule number even in casual conversation.",
        "08:30-19:00 ET",
    ),
    _person(
        "per-fionnuala-doherty",
        "Fionnuala Doherty",
        "Partner, Employment",
        "Employment",
        "per-adaora-nwosu",
        "partner",
        71000,
        "Employment counselling and single-plaintiff defence. Investigations, "
        "reductions in force, restrictive covenants, and the awkward calls "
        "clients make on a Friday afternoon.",
        "Warm and extremely direct, which surprises people. Treats every "
        "matter as a people problem with a legal wrapper. Documents "
        "conversations obsessively because she has been burned.",
        "Plain English, no Latin, always with a recommended next step.",
        "Conversational, uses names, checks in on people.",
        "Ends difficult messages with 'Call me if easier.'",
        "08:00-18:00 ET",
        knowledge=(
            KnowledgeItem(
                topic="investigation privilege posture",
                content=(
                    "Every internal investigation the firm runs is opened with a "
                    "written direction from counsel, because without it the report "
                    "is discoverable. She assumes everyone knows this and they do "
                    "not."
                ),
                share_policy="freely",
            ),
        ),
    ),
    _person(
        "per-gideon-park",
        "Gideon Park",
        "Partner, IP & Technology Transactions",
        "IP",
        "per-adaora-nwosu",
        "partner",
        67500,
        "Technology licensing, data and privacy terms, trade-secret disputes, "
        "and the IP side of the corporate group's deals. The firm's bridge "
        "between the transactional and litigation practices.",
        "Curious and discursive; will explain the technology before the law "
        "and enjoys both. Slow to commit to a position, immovable once he has.",
        "Explanatory, sometimes longer than necessary, always concrete.",
        "Asks questions back. Sends links.",
        "Prefaces bad news with 'So the interesting problem here is'.",
        "09:00-19:30 ET",
    ),
    _person(
        "per-hyunwoo-bae",
        "Hyun-woo Bae",
        "Senior Associate, Litigation",
        "Litigation",
        "per-bennett-ashworth",
        "senior",
        52000,
        "Runs discovery on the largest matters: custodian interviews, review "
        "protocols, privilege logs, and the meet-and-confers that precede "
        "motions. Second-chairs depositions.",
        "Organised to a fault and visibly tired. Anticipates what the partner "
        "will ask and has it ready. Reluctant to escalate until certain.",
        "Thorough, with a summary at the top because he knows people skim.",
        "Prompt and complete; posts status without being asked.",
        "Numbers his points even when there are two.",
        "08:30-21:00 ET",
    ),
    _person(
        "per-ingrid-solheim",
        "Ingrid Solheim",
        "Senior Associate, Corporate",
        "Corporate",
        "per-dov-reinhardt",
        "senior",
        49500,
        "Deal captain on mid-market transactions: runs the checklist, drives "
        "diligence, drafts the ancillaries, and keeps the closing set together.",
        "Unflappable and dryly funny. Keeps three deals straight without "
        "apparent effort. Pushes back on partners when the timeline is fiction.",
        "Crisp, with the ask in the first line.",
        "Efficient, occasionally deadpan.",
        "Says 'that is not a real deadline' when it is not.",
        "08:00-20:00 ET",
    ),
    _person(
        "per-jamal-okonkwo",
        "Jamal Okonkwo",
        "Counsel, Employment",
        "Employment",
        "per-fionnuala-doherty",
        "senior",
        56000,
        "Career counsel rather than partner track. Handles the firm's "
        "wage-and-hour class work and the technical end of benefits and "
        "restrictive-covenant disputes.",
        "Deeply expert, faintly weary, allergic to overstatement. Will tell "
        "a client the unwelcome answer first and the options second.",
        "Dense but readable; distinguishes what is settled from what is not.",
        "Sparse. Answers what was asked.",
        "Uses 'arguably' as a warning, not a hedge.",
        "09:00-18:00 ET",
    ),
    _person(
        "per-klara-bendtsen",
        "Klara Bendtsen",
        "Senior Associate, IP & Technology",
        "IP",
        "per-gideon-park",
        "senior",
        47500,
        "Drafts and negotiates licences, SaaS and data-processing terms, and "
        "the IP schedules in corporate deals. Handles trade-secret preservation "
        "when a departure turns litigious.",
        "Fast reader, careful drafter, quietly competitive. Keeps a personal "
        "clause bank she has never told anyone about.",
        "Precise, marks up rather than rewrites, explains each change.",
        "Quick, informal, lots of shorthand.",
        "Flags risk with a bare 'careful here'.",
        "08:30-19:00 ET",
        knowledge=(
            KnowledgeItem(
                topic="the firm's fallback licence positions",
                content=(
                    "There is an unwritten ladder of fallback positions on "
                    "indemnity caps that the technology group uses — one times "
                    "fees, then two times with a carve-out, then uncapped for "
                    "IP infringement only. It lives in her head and in three "
                    "old redlines."
                ),
                share_policy="if_asked",
            ),
        ),
    ),
    _person(
        "per-lucien-abara",
        "Lucien Abara",
        "Senior Associate, Litigation",
        "Litigation",
        "per-cecile-marchand",
        "senior",
        48500,
        "Briefing specialist: dispositive motions, appellate work, and the "
        "research memos the partners rely on. Also runs the firm's conflicts "
        "checks on new matters.",
        "Reflective and thorough; treats a deadline as a design constraint. "
        "Uncomfortable with argument he does not believe.",
        "Structured like a brief, with the conclusion stated first.",
        "Thoughtful, slightly slow to reply.",
        "Writes 'the better view is' rather than 'I think'.",
        "09:00-20:00 ET",
    ),
    _person(
        "per-mira-chandrasekhar",
        "Mira Chandrasekhar",
        "Associate, Corporate",
        "Corporate",
        "per-ingrid-solheim",
        "mid",
        41500,
        "Third-year. Diligence, ancillary documents, closing binders, and "
        "increasingly the first draft of the purchase agreement.",
        "Eager and slightly over-committed. Says yes before checking her "
        "calendar. Excellent at the parts she has done before.",
        "Polite, a little long, apologises more than necessary.",
        "Responsive and enthusiastic.",
        "Opens with 'Quick question' before a long question.",
        "08:30-21:00 ET",
    ),
    _person(
        "per-noor-haddad",
        "Noor Haddad",
        "Associate, Litigation",
        "Litigation",
        "per-hyunwoo-bae",
        "mid",
        40500,
        "Second-year. Document review management, deposition summaries, "
        "research memos, and the first cut of discovery responses.",
        "Sharp and underconfident. Catches things others miss and then "
        "asks whether she is wrong. Improving fast.",
        "Careful, cites everything, buries the finding at the end.",
        "Asks permission before flagging something.",
        "Prefaces good catches with 'This may be nothing, but'.",
        "09:00-20:30 ET",
    ),
    _person(
        "per-oskar-ravndal",
        "Oskar Ravndal",
        "Associate, IP & Technology",
        "IP",
        "per-klara-bendtsen",
        "mid",
        39500,
        "Second-year. Licence first drafts, privacy assessments, IP schedules, "
        "and the technical research the group's disputes require.",
        "Literal-minded in a useful way. Reads the contract that exists rather "
        "than the one everyone remembers signing.",
        "Matter-of-fact, quotes the clause in full.",
        "Direct, no small talk.",
        "Answers 'what does the agreement say' before anything else.",
        "09:00-19:00 ET",
    ),
    _person(
        "per-petra-kovacs",
        "Petra Kovacs",
        "Associate, Employment",
        "Employment",
        "per-jamal-okonkwo",
        "mid",
        38500,
        "Second-year. Investigation interviews and memoranda, handbook and "
        "policy work, position statements, and wage-and-hour data analysis.",
        "Empathetic and organised; good with witnesses. Takes criticism hard "
        "and does not show it.",
        "Warm but structured; separates fact from allegation carefully.",
        "Checks in, confirms receipt.",
        "Writes 'for the file' when documenting something.",
        "08:30-18:30 ET",
    ),
    _person(
        "per-quentin-sarr",
        "Quentin Sarr",
        "Associate, Corporate",
        "Corporate",
        "per-ingrid-solheim",
        "junior",
        34500,
        "First-year. Diligence review, signature pages, closing logistics, "
        "corporate housekeeping, and whatever the deal needs at 11pm.",
        "Willing and green. Asks good questions and occasionally the same "
        "one twice. Has not yet learned which fires are real.",
        "Formal, slightly stiff, over-explains.",
        "Fast, sometimes premature.",
        "Says 'On it' immediately, then asks how.",
        "09:00-22:00 ET",
    ),
    _person(
        "per-rosalie-duchamp",
        "Rosalie Duchamp",
        "Senior Paralegal, Litigation",
        "Litigation",
        "per-bennett-ashworth",
        "senior",
        25500,
        "Runs the mechanics of the litigation practice: filings, exhibits, "
        "subpoenas, court logistics, and the trial binders. Knows every clerk "
        "in the district by name.",
        "Formidable and unbothered. The person who actually knows whether "
        "something can be filed today. Protects the associates from their "
        "own optimism.",
        "Practical, specific, tells you what she needs and by when.",
        "Blunt and helpful.",
        "Says 'that will not get filed today' and is always right.",
        "08:00-18:00 ET",
        knowledge=(
            KnowledgeItem(
                topic="the district's after-hours filing reality",
                content=(
                    "The electronic filing system in the Eastern District accepts "
                    "submissions until midnight, but anything filed after 4pm goes "
                    "into the next morning's queue for clerk review — so a "
                    "same-day-stamped filing that needs a clerk's attention has a "
                    "4pm practical deadline, not a midnight one."
                ),
                share_policy="if_asked",
            ),
        ),
    ),
    _person(
        "per-samir-bhatt",
        "Samir Bhatt",
        "Paralegal, Corporate",
        "Corporate",
        "per-dov-reinhardt",
        "mid",
        19500,
        "Entity management, corporate records, closing binders, UCC and lien "
        "searches, and the state filings every deal generates.",
        "Meticulous and calm. Maintains the entity charts everyone relies on "
        "and nobody credits.",
        "Checklists, tables, and precise status.",
        "Brief, factual, reliable.",
        "Reports status as a fraction: '11 of 14 back'.",
        "08:30-18:30 ET",
    ),
    _person(
        "per-thandiwe-mokoena",
        "Thandiwe Mokoena",
        "Docket & Calendar Manager",
        "Practice Operations",
        "per-adaora-nwosu",
        "staff",
        None,
        "Owns the firm's docket: every court deadline, every response date, "
        "every statutory clock. Calendars the dates, chases the owners, and "
        "escalates what slips. Not a timekeeper.",
        "Precise and persistent. Sends the same reminder as many times as it "
        "takes without ever sounding annoyed. Trusts dates, not assurances.",
        "Short, dated, one deadline per message.",
        "Reminders with the date in bold.",
        "Always states the deadline and the days remaining.",
        "07:30-16:30 ET",
        knowledge=(
            KnowledgeItem(
                topic="how the docket actually gets built",
                content=(
                    "She calendars from the court's docket text, not from what "
                    "the attorney tells her, because the two disagree perhaps "
                    "twice a month and the docket text is what governs."
                ),
                share_policy="freely",
            ),
        ),
    ),
    _person(
        "per-ulrich-bergmann",
        "Ulrich Bergmann",
        "Billing Manager",
        "Practice Operations",
        "per-adaora-nwosu",
        "staff",
        None,
        "Runs the billing cycle: prebills out, edits back, invoices issued, "
        "write-offs recorded. Produces the WIP, realization and aging reports "
        "the partners read. Not a timekeeper.",
        "Dry and exact. Chases unreleased prebills relentlessly. Has views "
        "about people who log time in whole hours.",
        "Numeric, tabular, with the exception list at the top.",
        "Terse reminders with amounts.",
        "Quotes figures to the cent and expects the same back.",
        "08:00-17:00 ET",
        knowledge=(
            KnowledgeItem(
                topic="the prebill release convention",
                content=(
                    "A prebill is not released until the billing partner has "
                    "either edited it or explicitly said no changes; silence is "
                    "not approval, whatever the partners believe. He holds them, "
                    "which is why the month-end WIP always looks worse than "
                    "people expect."
                ),
                share_policy="if_asked",
            ),
        ),
    ),
)

INTERNAL_IDS: tuple[str, ...] = tuple(p.person_id for p in EMPLOYEES)


# --- the outside world -------------------------------------------------

# (org_id, display name, category, domain label)
ORGANIZATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("org-coastal-meridian", "Coastal Meridian Bancorp", "client", "coastalmeridian"),
    ("org-halden-orthopedics", "Halden Orthopedics Group", "client", "haldenortho"),
    ("org-verity-grain", "Verity Grain Partners", "client", "veritygrain"),
    ("org-pellumbra", "Pellumbra Therapeutics", "client", "pellumbra"),
    ("org-northmoor-capital", "Northmoor Capital", "client", "northmoorcap"),
    ("org-sable-ridge", "Sable Ridge Logistics", "client", "sableridge"),
    ("org-atwater-foods", "Atwater Foods", "client", "atwaterfoods"),
    ("org-linden-robotics", "Linden Robotics", "client", "lindenrobotics"),
    ("org-cotswold-mutual", "Cotswold Mutual Insurance", "client", "cotswoldmutual"),
    ("org-brightwell-academy", "Brightwell Academy", "client", "brightwellacademy"),
    # Not clients. A directory that files an adversary under "Client" makes
    # the distinction unlearnable, and every report keyed on it is wrong.
    ("org-kerrigan-boyle", "Kerrigan Boyle LLP", "opposing", "kerriganboyle"),
    ("org-strand-whitfield", "Strand & Whitfield", "opposing", "strandwhitfield"),
    ("org-eastern-district", "U.S. District Court, E.D.", "court", "ecf.uscourts"),
    ("org-mercer-county", "Mercer County Superior Court", "court", "mercercourts"),
    ("org-veritext-repro", "Veritext Reporting", "vendor", "veritextrepro"),
    ("org-lansdowne-esi", "Lansdowne eDiscovery", "vendor", "lansdowneesi"),
)

_ORG_BY_ID = {
    org_id: (name, category, label) for org_id, name, category, label in ORGANIZATIONS
}


# (person_id, name, org_id, role, temperament, contacts, concerns)
_OUTSIDERS: tuple[
    tuple[str, str, str, str, str, tuple[str, ...], tuple[str, ...]], ...
] = (
    (
        "per-marguerite-oyelaran",
        "Marguerite Oyelaran",
        "org-coastal-meridian",
        "General Counsel",
        "Former litigator, now in-house. Asks precise questions and expects "
        "precise answers. Will not accept a range where a date is possible.",
        ("Adaora Nwosu", "Bennett Ashworth"),
        (
            "the enforcement inquiry and what gets produced",
            "whether the credit agreement's covenant language was ever amended",
            "outside counsel spend against the budget she committed to",
        ),
    ),
    (
        "per-roland-pesch",
        "Roland Pesch",
        "org-halden-orthopedics",
        "Chief Administrative Officer",
        "Practical and cost-conscious, running a physician group that does not "
        "want to be in litigation. Writes short and calls when worried.",
        ("Fionnuala Doherty", "Cecile Marchand"),
        (
            "the departing physician's non-compete",
            "whether the malpractice matter can be resolved quietly",
            "what the employment audit will find",
        ),
    ),
    (
        "per-imelda-frost",
        "Imelda Frost",
        "org-verity-grain",
        "Chief Financial Officer",
        "Blunt, numbers-first, allergic to legal throat-clearing. Wants the "
        "commercial answer and the risk in one paragraph.",
        ("Dov Reinhardt", "Ingrid Solheim"),
        (
            "the grain elevator acquisition timeline",
            "the supplier dispute and whether to counterclaim",
            "how much the deal is going to cost in fees",
        ),
    ),
    (
        "per-teodor-vasiliev",
        "Teodor Vasiliev",
        "org-pellumbra",
        "VP Legal",
        "Detail-obsessed biotech lawyer under investor pressure. Long emails, "
        "many sub-questions, genuinely grateful for good work.",
        ("Gideon Park", "Elena Vasquez-Reyes"),
        (
            "the collaboration agreement's IP ownership split",
            "clinical data privacy across jurisdictions",
            "the Series C disclosure schedule",
        ),
    ),
    (
        "per-saoirse-mulvaney",
        "Saoirse Mulvaney",
        "org-northmoor-capital",
        "Managing Director",
        "Impatient private-equity principal. Measures everything in days to "
        "close. Escalates to the managing partner without hesitation.",
        ("Dov Reinhardt", "Adaora Nwosu"),
        (
            "whether the platform acquisition closes this quarter",
            "the diligence red flags and which are real",
            "management incentive plan mechanics",
        ),
    ),
    (
        "per-clement-abioye",
        "Clement Abioye",
        "org-sable-ridge",
        "Director of Human Resources",
        "Careful and anxious about doing the right thing. Volunteers more "
        "context than asked for, which is usually helpful.",
        ("Fionnuala Doherty", "Jamal Okonkwo"),
        (
            "the wage-and-hour class claims from the drivers",
            "whether the reduction in force is defensible",
            "the harassment investigation and who should conduct it",
        ),
    ),
    (
        "per-yuki-tanabe",
        "Yuki Tanabe",
        "org-atwater-foods",
        "General Counsel",
        "Calm generalist covering everything alone. Prioritises ruthlessly and "
        "says plainly when something can wait.",
        ("Cecile Marchand", "Klara Bendtsen"),
        (
            "the recall exposure and the insurer's position",
            "supplier contract renewals",
            "trademark opposition in two markets",
        ),
    ),
    (
        "per-priyanka-deshmukh",
        "Priyanka Deshmukh",
        "org-linden-robotics",
        "Chief Executive Officer",
        "Founder who reads the contracts herself. Technical, impatient with "
        "boilerplate, wants to know why every clause exists.",
        ("Gideon Park", "Klara Bendtsen"),
        (
            "the trade-secret claim against the former engineering lead",
            "the OEM licence terms and the indemnity cap",
            "whether the patent filings are on schedule",
        ),
    ),
    (
        "per-desmond-achebe",
        "Desmond Achebe",
        "org-cotswold-mutual",
        "Claims Counsel",
        "Institutional and procedural. Cares about reserves, reporting "
        "deadlines, and whether the panel guidelines were followed.",
        ("Cecile Marchand", "Bennett Ashworth"),
        (
            "the coverage position on the professional liability claim",
            "compliance with the panel billing guidelines",
            "reserve adequacy as the matter develops",
        ),
    ),
    (
        "per-harriet-lindqvist",
        "Harriet Lindqvist",
        "org-brightwell-academy",
        "Head of School",
        "Not a lawyer and does not pretend to be. Asks what she should do, "
        "not what the law is. Deeply concerned about the community.",
        ("Fionnuala Doherty", "Petra Kovacs"),
        (
            "the employee complaint and how to handle it fairly",
            "handbook and policy updates before the school year",
            "what has to be disclosed to the board",
        ),
    ),
)


def _outsider(entry) -> PersonSpec:
    person_id, name, org_id, role, temperament, contacts, concerns = entry
    org_name, category, label = _ORG_BY_ID[org_id]
    local = name.lower().replace(" ", ".").replace("'", "")
    return PersonSpec(
        person_id=person_id,
        name=name,
        email_address=f"{local}@{label}.example",
        title=role,
        # Category, not "Client" for everyone outside the firm. Opposing
        # counsel and a court are not clients, and a report keyed on this
        # field is only right if the field is.
        department=category.capitalize(),
        manager=None,
        affiliation="external",
        timezone=TZ,
        persona=None,
        client_persona=ClientActorParams(
            person_id=person_id,
            name=name,
            organization=org_name,
            role=role,
            temperament=temperament,
            contacts=contacts,
            concerns=concerns,
        ),
    )


OUTSIDERS: tuple[PersonSpec, ...] = tuple(_outsider(entry) for entry in _OUTSIDERS)

PEOPLE: tuple[PersonSpec, ...] = EMPLOYEES + OUTSIDERS

__all__ = [
    "ARTIFACT_CONVENTIONS",
    "DOMAIN",
    "EMPLOYEES",
    "INTERNAL_IDS",
    "MATTER_PRIORITIES",
    "MATTER_STATUSES",
    "MATTER_TYPES",
    "ORGANIZATIONS",
    "OUTSIDERS",
    "PEOPLE",
    "TZ",
]
