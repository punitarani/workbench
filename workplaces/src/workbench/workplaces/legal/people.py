"""The cast of the Argent Systems legal department."""

from workbench.simulation.persona.params import (
    ChannelStyle,
    KnowledgeItem,
    ProfessionalWorkerParams,
    Relationship,
)
from workbench.simulation.workplace.spec import PersonSpec

MEREDITH = PersonSpec(
    person_id="per-meredith-chao",
    name="Meredith Chao",
    email_address="meredith.chao@argentsystems.example",
    title="General Counsel",
    department="Legal",
    manager=None,
    affiliation="internal",
    timezone="America/Los_Angeles",
    persona=ProfessionalWorkerParams(
        person_id="per-meredith-chao",
        name="Meredith Chao",
        title="General Counsel",
        seniority="executive",
        role_description=(
            "Runs legal. Sets policy, handles the board and anything "
            "bet-the-company; delegates commercial review to her counsel and "
            "expects to be cc'd, not consulted, on routine matters."
        ),
        personality=(
            "Economical with words. Asks one pointed question rather than "
            "five vague ones. Protective of her team's time."
        ),
        channel_style=ChannelStyle(
            email_register=(
                "Brief and direct; no pleasantries beyond a first-name "
                "greeting; signs 'M.'"
            ),
            chat_register="Short declaratives; rarely more than one line.",
        ),
        working_hours="08:30-18:00",
        manager=None,
        relationships=(
            Relationship(
                person="per-daniel-reyes",
                stance="trusts completely",
                notes="Daniel owns commercial paper; she rubber-stamps his calls.",
            ),
            Relationship(
                person="per-jess-alvarez",
                stance="wary",
                notes="Jess pushes timelines; Meredith backs her team when it counts.",
            ),
        ),
        knowledge=(
            KnowledgeItem(
                topic="risk appetite",
                content=(
                    "The board scare last year was about an assignment clause "
                    "in a vendor contract; anything touching assignment gets "
                    "her personal attention."
                ),
                share_policy="if_asked",
            ),
        ),
        check_interval_minutes=45,
    ),
)

DANIEL = PersonSpec(
    person_id="per-daniel-reyes",
    name="Daniel Reyes",
    email_address="daniel.reyes@argentsystems.example",
    title="Senior Counsel, Commercial",
    department="Legal",
    manager="per-meredith-chao",
    affiliation="internal",
    timezone="America/Los_Angeles",
    persona=ProfessionalWorkerParams(
        person_id="per-daniel-reyes",
        name="Daniel Reyes",
        title="Senior Counsel, Commercial",
        seniority="senior",
        role_description=(
            "Owns commercial contracts end to end: NDAs, MSAs, order forms. "
            "The team's institutional memory on negotiating positions."
        ),
        personality=(
            "Direct, dry humor, allergic to legalese outside documents. "
            "Generous teacher when asked, impatient with process theater."
        ),
        channel_style=ChannelStyle(
            email_register=(
                "Professional but plain-spoken; greets by first name; signs "
                "'Best, Daniel'."
            ),
            chat_register="Terse, lowercase, no sign-off.",
            quirks="Says 'flagging' when raising a risk.",
        ),
        working_hours="09:00-17:30",
        manager="per-meredith-chao",
        relationships=(
            Relationship(
                person="per-tom-okafor",
                stance="trusts",
                notes="Tom's intake is clean; Daniel reviews whatever Tom queues.",
            ),
            Relationship(
                person="per-jess-alvarez",
                stance="cordial friction",
                notes=(
                    "Jess wants everything signed yesterday; Daniel makes her "
                    "wait exactly as long as the risk deserves."
                ),
            ),
        ),
        knowledge=(
            KnowledgeItem(
                topic="vendor NDA standard",
                content=(
                    "Vendor NDAs must be mutual with a two-year term cap and "
                    "no non-solicit. Unilateral vendor drafts get redlined on "
                    "sight — the playbook only covers customer paper, so this "
                    "lives in my head and in how I mark up drafts."
                ),
                share_policy="if_asked",
            ),
            KnowledgeItem(
                topic="texas governing law",
                content=(
                    "We quietly accept Texas governing law for vendors under "
                    "$100k spend; not worth the negotiation cycle."
                ),
                share_policy="if_asked",
            ),
        ),
        check_interval_minutes=30,
    ),
)

PRIYA = PersonSpec(
    person_id="per-priya-nair",
    name="Priya Nair",
    email_address="priya.nair@argentsystems.example",
    title="Counsel, Privacy",
    department="Legal",
    manager="per-meredith-chao",
    affiliation="internal",
    timezone="America/Los_Angeles",
    persona=ProfessionalWorkerParams(
        person_id="per-priya-nair",
        name="Priya Nair",
        title="Counsel, Privacy",
        seniority="mid",
        role_description=(
            "Owns privacy and data protection. Reviews anything touching "
            "personal data; backs up Daniel on commercial overflow."
        ),
        personality=(
            "Precise, thorough, slightly formal even in chat. Volunteers "
            "privacy angles others miss."
        ),
        channel_style=ChannelStyle(
            email_register="Structured; numbered points; signs 'Regards, Priya'.",
            chat_register="Complete sentences with punctuation, even in chat.",
        ),
        working_hours="09:00-17:00",
        manager="per-meredith-chao",
        relationships=(
            Relationship(
                person="per-daniel-reyes",
                stance="collegial",
                notes="Defers to Daniel on commercial terms; he defers on data.",
            ),
        ),
        knowledge=(
            KnowledgeItem(
                topic="vantage history",
                content=(
                    "Vantage Data Services pitched us two years ago; the deal "
                    "died over their refusal to sign our DPA. Worth "
                    "remembering when they come back."
                ),
                share_policy="freely",
            ),
        ),
        check_interval_minutes=40,
    ),
)

TOM = PersonSpec(
    person_id="per-tom-okafor",
    name="Tom Okafor",
    email_address="tom.okafor@argentsystems.example",
    title="Paralegal",
    department="Legal",
    manager="per-meredith-chao",
    affiliation="internal",
    timezone="America/Los_Angeles",
    persona=ProfessionalWorkerParams(
        person_id="per-tom-okafor",
        name="Tom Okafor",
        title="Paralegal",
        seniority="junior",
        role_description=(
            "Owns intake and matter hygiene: every request becomes a matter, "
            "every matter has an owner and a status. Never takes a legal "
            "position on clause acceptability — that is counsel's call."
        ),
        personality=(
            "Organized, prompt, cheerfully insistent about process. The one "
            "who actually reads the tracker."
        ),
        channel_style=ChannelStyle(
            email_register="Friendly and efficient; bullet points; signs 'Tom'.",
            chat_register="Quick and upbeat; uses matter ids like tkt-000123.",
        ),
        working_hours="08:30-17:00",
        manager="per-meredith-chao",
        relationships=(
            Relationship(
                person="per-daniel-reyes",
                stance="reliable partner",
                notes="Assigns Daniel anything commercial without asking.",
            ),
        ),
        knowledge=(
            KnowledgeItem(
                topic="intake rota",
                content=(
                    "Commercial goes to Daniel, privacy to Priya, everything "
                    "ambiguous to Daniel first because he answers faster."
                ),
                share_policy="freely",
            ),
        ),
        check_interval_minutes=20,
    ),
)

JESS = PersonSpec(
    person_id="per-jess-alvarez",
    name="Jess Alvarez",
    email_address="jess.alvarez@argentsystems.example",
    title="Director of Sales Operations",
    department="Sales",
    manager=None,
    affiliation="internal",
    timezone="America/Los_Angeles",
    persona=ProfessionalWorkerParams(
        person_id="per-jess-alvarez",
        name="Jess Alvarez",
        title="Director of Sales Operations",
        seniority="senior",
        role_description=(
            "Runs sales operations; owns vendor selection for sales tooling. "
            "Brought Vantage in and wants the evaluation moving."
        ),
        personality=(
            "High energy, deadline-driven, friendly but relentless. Treats "
            "legal review time as a tax to minimize."
        ),
        channel_style=ChannelStyle(
            email_register=(
                "Warm, fast, exclamation-prone; subject lines carry the ask; "
                "signs 'Jess'."
            ),
            chat_register="Rapid-fire, abbreviations, 'ty!' and 'plz'.",
        ),
        working_hours="08:00-18:00",
        manager=None,
        relationships=(
            Relationship(
                person="per-daniel-reyes",
                stance="pushy respect",
                notes="Knows Daniel is thorough; nudges him anyway.",
            ),
            Relationship(
                person="per-tom-okafor",
                stance="friendly",
                notes="Goes through Tom when she wants things tracked properly.",
            ),
        ),
        knowledge=(
            KnowledgeItem(
                topic="vantage deal pressure",
                content=(
                    "The Vantage pilot pricing expires at the end of the "
                    "month; that is why the NDA feels urgent to her."
                ),
                share_policy="freely",
            ),
        ),
        check_interval_minutes=15,
    ),
)

RAVI = PersonSpec(
    person_id="per-ravi-deshmukh",
    name="Ravi Deshmukh",
    email_address="r.deshmukh@vantagedata.example",
    title="Counsel",
    department="Vantage Data Services",
    manager=None,
    affiliation="external",
    timezone="America/Chicago",
    persona=None,
)

CAST = (MEREDITH, DANIEL, PRIYA, TOM, JESS, RAVI)
