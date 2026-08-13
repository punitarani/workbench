"""The Calder & Finch procedural register: how the firm talks when
nothing in particular is happening.

Every entry is a template for
:class:`~workbench.simulation.chronicle.procedural.ProceduralVoice`:
``{slot}`` placeholders resolve either from the generator's context
(``matter``, ``first``, ``me``, ``focus``) or from :data:`SLOTS`. A few
hundred forms crossed with the slot pools give tens of thousands of
distinct bodies, which is what keeps six months of background traffic
from collapsing into a handful of repeated strings.

The prose is deliberately date-free: a template that named a month or a
deadline would eventually contradict the calendar it lands on. Season
lives in the directed arcs, not here.
"""

from workbench.simulation.chronicle.procedural import EmailForm, ProceduralVoice

SLOTS: dict[str, tuple[str, ...]] = {
    "task": (
        "the bank rec",
        "the trial balance",
        "the depreciation schedule",
        "the prepaid rollforward",
        "the accrual workpaper",
        "the sales tax file",
        "the payroll journal",
        "the AR aging",
        "the AP run",
        "the fixed-asset register",
        "the adjusting entries",
        "the review notes",
        "the K-1 packet",
        "the extension list",
        "the engagement letter",
        "the tie-out",
        "the variance memo",
        "the 1099 file",
        "the loan covenant calc",
        "the cash-flow summary",
    ),
    "doc": (
        "the checklist",
        "the PBC list",
        "the prior-year file",
        "the workpaper index",
        "the signed 8879",
        "the org chart",
        "the closing binder",
        "the support schedule",
        "the bank statements",
        "the payroll reports",
        "the board minutes",
        "the lease agreement",
        "the depreciation detail",
        "the grant letter",
    ),
    "sys": (
        "QuickBooks",
        "the GL",
        "the bank feed",
        "the tax software",
        "the document portal",
        "the time entry screen",
        "the scanner",
        "the payroll platform",
        "the e-file dashboard",
        "the shared drive",
    ),
    "when": (
        "after lunch",
        "first thing tomorrow",
        "before the end of the day",
        "later this afternoon",
        "tomorrow morning",
        "before the staff meeting",
        "by close of business",
        "when you get a minute",
        "before you leave",
        "early next week",
    ),
    "softener": (
        "No rush",
        "Whenever works",
        "Low priority",
        "Not urgent",
        "When you surface",
        "No panic",
    ),
    "closer": (
        "Thanks!",
        "Appreciate it.",
        "You're the best.",
        "Owe you one.",
        "Thanks much.",
        "Perfect, thanks.",
    ),
    "greeting": (
        "Hey",
        "Morning",
        "Quick one",
        "Hi there",
        "Ping",
        "Hey hey",
    ),
    "verb": (
        "reconcile",
        "tie out",
        "roll forward",
        "post",
        "review",
        "clear",
        "rebook",
        "trace",
        "recompute",
        "flag",
    ),
    "figure": (
        "the cash balance",
        "the retained earnings rollforward",
        "the officer comp number",
        "the depreciation add-back",
        "the meals adjustment",
        "the shareholder basis",
        "the estimated payment",
        "the accrued PTO balance",
        "the deferred revenue split",
        "the mileage total",
    ),
    "hiccup": (
        "the portal is timing out",
        "the bank feed dropped a week",
        "the scanner is jamming again",
        "my second monitor died",
        "the VPN keeps disconnecting",
        "the e-file ack never landed",
        "the printer is out of toner",
        "my calendar invites are duplicating",
    ),
}

STANDUP: tuple[str, ...] = (
    "Today: {focus}. Otherwise heads-down.",
    "Plan for the day is {focus}, then inbox triage.",
    "Mostly {focus} today; free after 3 for review questions.",
    "{focus} this morning, catch-up calls after lunch.",
    "Working through {focus}. Flag anything urgent in the thread.",
    "On {focus} until it's done. DM me if something breaks.",
    "Today is {focus} plus whatever the inbox brings.",
    "Splitting the day between {focus} and review notes.",
    "Back on {focus}; yesterday's carryover first.",
    "{focus}, then clearing my review queue.",
    "Short day for me — front-loading {focus}.",
    "Picking {focus} back up where I left off.",
)

STANDUP_FOCUS: tuple[str, ...] = (
    "clearing diagnostics on {matter}",
    "workpapers for {matter}",
    "the open items list on {matter}",
    "tying out {matter}",
    "review notes on {matter}",
    "client follow-ups for {matter}",
    "posting adjustments on {matter}",
    "the reconciliation backlog on {matter}",
    "prepping deliverables for {matter}",
    "cleanup on {matter}",
)

REACTIONS: tuple[str, ...] = ("👍", "✅", "🎉", "💯", "🙏", "😅", "☕")

MATTER_LINES: tuple[str, ...] = (
    "Status check on {matter} — where are we on {task}?",
    "Anyone have {doc} for {matter}? Can't find it on {sys}.",
    "{matter}: client sent partial support, still missing {doc}.",
    "Heads up, {matter} has open review notes aging past a week.",
    "Moving {matter} to review — {task} is tied out.",
    "Who has the pen on {task} for {matter}?",
    "{matter} support landed in the portal. Filing to the engagement folder.",
    "Can someone {verb} {figure} on {matter}? Getting a variance.",
    "{matter}: {figure} moved after the late entries. Recomputing.",
    "Parking {matter} until the client answers on {doc}.",
    "{matter} is clean through {task}. Next up: {figure}.",
    "Flagging {matter} — {figure} doesn't tie to {sys}.",
    "Client call on {matter} went fine; notes in the folder.",
    "Rebooked the opening balances on {matter}; diffs cleared.",
    "{matter}: draft is out for partner review.",
)

MATTER_REPLIES: tuple[str, ...] = (
    "On it — will {verb} it {when}.",
    "That one's mine. Update by end of day.",
    "Just posted it to {sys}, refresh and it should be there.",
    "Client promised {doc} this week, chasing again now.",
    "Same variance I saw — it's the late bank entries. Fixing.",
    "Cleared. Review notes closed out on my side.",
    "Grabbing it after my current tie-out.",
    "Ask whoever has the lead sheet — I think it's in their queue.",
    "It ties now; the difference was {figure}.",
    "Will look {when}, currently mid-rec.",
)

BILLING_LINES: tuple[str, ...] = (
    "WIP on {matter} is creeping — worth a prebill this cycle?",
    "Realization on {matter} looks soft; entries heavier than quote.",
    "Anyone know if the retainer for {matter} was applied?",
    "Time on {matter} needs narratives before I can bill it.",
    "Sending the invoice draft for {matter} to partner review.",
    "Client asked for a fee breakdown on {matter} — assembling from the time detail.",
    "{matter} hit its cap; the rest bleeds to next cycle unless we talk scope.",
    "Two unbilled months on {matter}. Flagging before it gets awkward.",
    "Write-off request on {matter} is in the queue for approval.",
    "Progress bill went out on {matter} yesterday.",
)

BILLING_REPLIES: tuple[str, ...] = (
    "Prebill it — I'll review tonight.",
    "Applied last week, check the ledger again.",
    "Hold until the deliverable goes out, then bill in full.",
    "I'll clean up my narratives {when}.",
    "Scope talk is scheduled; park it until then.",
    "Approved on my end, note it in the file.",
    "Cap was for prep only — review time bills separately.",
)

IT_LINES: tuple[str, ...] = (
    "{hiccup} — anyone else?",
    "Ticket in: {hiccup}. Working around it for now.",
    "Is {sys} down for anyone else or just me?",
    "New starter setup: which license pool do we pull from?",
    "Reminder: reboot before the backup window tonight.",
    "Password reset on {sys} took three tries; whatever, I'm in.",
    "Can someone bump my access on {sys}? Read-only right now.",
    "The conference room screen won't mirror again.",
)

IT_REPLIES: tuple[str, ...] = (
    "Known issue — vendor says a fix lands tonight.",
    "Rebooted the box, try again in five.",
    "Just you, sadly. Clearing your cache usually does it.",
    "Access bumped, log out and back in.",
    "I'll swing by with a cable that works.",
    "Filed with the vendor, reference in the ticket.",
    "Try the guest network as a stopgap.",
)

DM_OPENERS: tuple[str, ...] = (
    "{greeting} — do you have {doc} for me?",
    "{greeting}, got two minutes on {task}?",
    "Can you {verb} {figure} when you're free? {softener}.",
    "Did {doc} ever land? Not seeing it in {sys}.",
    "{greeting} — sanity check: does {figure} look right to you?",
    "Leaving early {when} — can you cover the client call?",
    "Coffee run in ten, want anything?",
    "Where do we keep {doc} now? The folder moved.",
    "{greeting}, the client replied — short version: they found {doc}.",
    "Can I hand you {task}? My plate just filled.",
    "You free {when}? Want to walk through {task}.",
    "Reminder before I forget: {doc} needs your initials.",
    "{softener}, but {task} is waiting on you.",
    "Client asked for you by name on {task}. All yours.",
)

DM_REPLIES: tuple[str, ...] = (
    "Yep — sending {when}.",
    "Give me an hour, mid-rec right now.",
    "It's on {sys}, look under the engagement folder.",
    "Looks right to me. One decimal thing, noted in the file.",
    "Can do. Anything else while I'm in there?",
    "Ha, sure — the usual.",
    "Covered. Go.",
    "It landed, I filed it this morning.",
    "Handing it back with comments {when}.",
    "Yes but only after my tie-out, fair warning.",
)

DM_CLOSERS: tuple[str, ...] = (
    "{closer}",
    "{closer} {softener}.",
    "Perfect. {closer}",
    "That works. {closer}",
    "Noted — {closer}",
)

INTERNAL_EMAIL: tuple[EmailForm, ...] = (
    EmailForm(
        subject="Review notes — ready for your pass",
        body=(
            "{first},\n\nMy self-review is done and the file is in {sys}. "
            "Open items are tagged; {figure} is the one worth your "
            "attention.\n\n{me}"
        ),
    ),
    EmailForm(
        subject="Coverage {when}",
        body=(
            "{first},\n\nI'm out {when} — can you keep an eye on my "
            "inbox? Only thing live is {task}; everything else can "
            "wait.\n\nThanks,\n{me}"
        ),
    ),
    EmailForm(
        subject="Workpaper question",
        body=(
            "{first},\n\nBefore I {verb} {figure}: is the treatment the "
            "same as prior year, or did we change it? The file reads "
            "both ways.\n\n{me}"
        ),
    ),
    EmailForm(
        subject="Client docs came in",
        body=(
            "{first},\n\n{doc} finally landed. I filed it to the "
            "engagement folder and updated the open items list. "
            "Remaining asks are in the tracker.\n\n{me}"
        ),
    ),
    EmailForm(
        subject="Handing off {task}",
        body=(
            "{first},\n\nPer our chat, {task} is yours from here. My "
            "notes are in the lead sheet; the only loose end is "
            "{figure}.\n\nAppreciated,\n{me}"
        ),
    ),
    EmailForm(
        subject="Time entry cleanup",
        body=(
            "{first},\n\nA few of your entries this week are missing "
            "narratives — can you fill them in {when}? Billing wants a "
            "clean run.\n\n{me}"
        ),
    ),
    EmailForm(
        subject="Staff meeting follow-up",
        body=(
            "{first},\n\nAction item from the meeting: you have {task}, "
            "I have the client side. Let's compare notes {when}.\n\n{me}"
        ),
    ),
    EmailForm(
        subject="Template updated",
        body=(
            "{first},\n\nI refreshed {doc} on {sys} — old copies will "
            "drift, so pull the new one before your next engagement.\n\n"
            "{me}"
        ),
    ),
)

INTERNAL_REPLIES: tuple[str, ...] = (
    "{first},\n\nDone — see my notes in the file.\n\n{me}",
    "{first},\n\nWorks for me. I'll take it from here.\n\n{me}",
    "{first},\n\nSame as prior year; memo is in the permanent file.\n\n{me}",
    "{first},\n\nGot it, thanks for the heads up.\n\n{me}",
    "{first},\n\nWill do before I leave today.\n\n{me}",
    "{first},\n\nCovered. Enjoy the time off.\n\n{me}",
)

EXTERNAL_EMAIL: tuple[EmailForm, ...] = (
    EmailForm(
        subject="Question on the latest statement",
        body=(
            "Hi {first},\n\nLooking at the statements you sent — one "
            "line item doesn't match our records and I want to make "
            "sure we book it right. Could you or your bookkeeper "
            "confirm the detail behind it?\n\nBest,\n{me}"
        ),
    ),
    EmailForm(
        subject="Documents uploaded to the portal",
        body=(
            "Hi {first},\n\nJust uploaded the items your office asked "
            "for to the portal. Let me know if anything is missing or "
            "won't open.\n\nThanks,\n{me}"
        ),
    ),
    EmailForm(
        subject="Can we move our call?",
        body=(
            "Hi {first},\n\nSomething came up on my end — could we "
            "shift our call by a day or two? Same agenda, just a "
            "scheduling crunch here.\n\nSorry for the shuffle,\n{me}"
        ),
    ),
    EmailForm(
        subject="New hire paperwork",
        body=(
            "Hi {first},\n\nWe brought on two new employees this "
            "month. What do you need from us so payroll and "
            "withholding are set up correctly?\n\nThanks,\n{me}"
        ),
    ),
    EmailForm(
        subject="Quick question before I sign",
        body=(
            "Hi {first},\n\nBefore I sign what you sent over — can you "
            "explain the number on the second page in plain English? "
            "Want to make sure I understand what changed.\n\n{me}"
        ),
    ),
    EmailForm(
        subject="Bank asked for financials",
        body=(
            "Hi {first},\n\nOur bank is asking for updated financials "
            "for the line renewal. What's the fastest version we can "
            "give them that you're comfortable with?\n\nThanks,\n{me}"
        ),
    ),
)

EXTERNAL_REPLIES: tuple[str, ...] = (
    (
        "Hi {first},\n\nGood catch — send me the detail and we'll "
        "correct it on our side.\n\nBest,\n{me}"
    ),
    ("Hi {first},\n\nEverything opened fine; you're all set for now.\n\nThanks,\n{me}"),
    ("Hi {first},\n\nNo problem at all — I'll send new times shortly.\n\nBest,\n{me}"),
    (
        "Hi {first},\n\nI'll send the onboarding checklist today; it "
        "covers everything we need.\n\nBest,\n{me}"
    ),
    (
        "Hi {first},\n\nHappy to walk you through it — short version "
        "coming by email, and we can talk if it helps.\n\nBest,\n{me}"
    ),
)

TIME_NOTES: tuple[str, ...] = (
    "Bank reconciliation and follow-up on outstanding items — {matter}",
    "Prepare adjusting journal entries; update lead sheets — {matter}",
    "Review client-provided support; note open items — {matter}",
    "Draft deliverable and self-review — {matter}",
    "Client correspondence re: missing documentation — {matter}",
    "Tie out schedules to general ledger — {matter}",
    "Update depreciation and fixed-asset detail — {matter}",
    "Payroll reconciliation and quarterly report prep — {matter}",
    "Research treatment question; memo to file — {matter}",
    "Respond to review notes; clear diagnostics — {matter}",
    "Rollforward workpapers; update PBC tracker — {matter}",
    "Prepare management letter points — {matter}",
    "Sales tax compilation and filing prep — {matter}",
    "Meeting with engagement team; update planning notes — {matter}",
    "Analytical review of monthly results — {matter}",
    "Reconcile intercompany balances — {matter}",
)

MATTER_NOTES: tuple[str, ...] = (
    "Support received through the portal; tracker updated — {matter}.",
    "Left voicemail with the client contact; second follow-up logged.",
    "Open items down to three; oldest is the bank confirmation.",
    "Draft moved to partner review; no unresolved diagnostics.",
    "Client confirmed the variance explanation in writing; filed.",
    "Scope note: added the new entity to the engagement per client email.",
    "Reviewed and cleared staff workpapers; two notes returned.",
    "Deliverable sent; awaiting signature packet.",
    "Rescheduled fieldwork day at client request; calendar updated.",
    "Fee discussion noted; see billing thread for disposition.",
)

MEETING_TITLES: tuple[str, ...] = (
    "Engagement check-in: {matter}",
    "Workpaper review — {matter}",
    "Planning touchpoint: {matter}",
    "Open items scrub: {matter}",
    "Wrap-up call: {matter}",
    "Staff scheduling huddle",
    "Pipeline and workload review",
)

MEETING_DESCRIPTIONS: tuple[str, ...] = (
    "Walk the open items list and reassign anything stuck.",
    "Thirty minutes, bring your lead sheets.",
    "Status, blockers, and who needs client responses chased.",
    "Quick sync before the deliverable goes out.",
    "Review notes discussion; close what we can live.",
    "Standing check-in; cancel if nothing is blocking.",
)

VOICE = ProceduralVoice(
    standup=STANDUP,
    standup_focus=STANDUP_FOCUS,
    reactions=REACTIONS,
    matter_lines=MATTER_LINES,
    matter_replies=MATTER_REPLIES,
    billing_lines=BILLING_LINES,
    billing_replies=BILLING_REPLIES,
    it_lines=IT_LINES,
    it_replies=IT_REPLIES,
    dm_openers=DM_OPENERS,
    dm_replies=DM_REPLIES,
    dm_closers=DM_CLOSERS,
    internal_email=INTERNAL_EMAIL,
    internal_replies=INTERNAL_REPLIES,
    external_email=EXTERNAL_EMAIL,
    external_replies=EXTERNAL_REPLIES,
    time_notes=TIME_NOTES,
    matter_notes=MATTER_NOTES,
    meeting_titles=MEETING_TITLES,
    meeting_descriptions=MEETING_DESCRIPTIONS,
    slots=SLOTS,
)
