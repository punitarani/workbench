"""The Hartwell & Marsh procedural register: how the firm talks when
nothing in particular is happening.

Every entry is a template for
:class:`~simulation.chronicle.procedural.ProceduralVoice`:
``{slot}`` placeholders resolve either from the generator's context
(``matter``, ``first``, ``me``, ``focus``) or from :data:`SLOTS`. A few
hundred forms crossed with the slot pools give tens of thousands of
distinct bodies, which is what keeps four months of background traffic
from collapsing into a handful of repeated strings.

The pools were authored once through the simulation content store and are
frozen here as data: procedural days must build offline and byte for
byte, so nothing in this module may depend on a live model.
"""

from simulation.chronicle.procedural import EmailForm, ProceduralVoice

SLOTS: dict[str, tuple[str, ...]] = {
    "task": (
        "the redline",
        "the exhibit index",
        "the signature packet",
        "the response draft",
        "the fee estimate",
        "the status memo",
        "the chronology",
        "the deposition summary",
        "the closing checklist",
        "the privilege log",
        "the witness outline",
        "the conflicts memo",
        "the filing packet",
        "the revised schedule",
        "the client update",
        "the issues list",
    ),
    "thing": (
        "the binder",
        "the working file",
        "the courier envelope",
        "the chron file",
        "the signed original",
        "the transcript",
        "the exhibit stickers",
        "the visitor badge",
        "the closing binder",
        "the mail tray",
        "the spare charger",
        "the redwell",
        "the flash drive",
        "the notary stamp",
    ),
    "when": (
        "after lunch",
        "first thing tomorrow",
        "before the end of the day",
        "later this afternoon",
        "tomorrow morning",
        "before the team meeting",
        "sometime this week",
        "right after the call",
        "early next week",
        "before close of business",
        "in about an hour",
        "over the next couple of days",
        "once the mail run is done",
        "before the next status call",
    ),
    "place": (
        "the small conference room",
        "the records room",
        "the front desk",
        "the third-floor copier bay",
        "the file room",
        "the library",
        "the kitchen",
        "the mail room",
        "the large conference room",
        "the parking garage",
        "the reception area",
        "the storage closet",
    ),
    "system": (
        "the client portal",
        "the document system",
        "the docket calendar",
        "the shared drive",
        "the time-entry system",
        "the practice-management system",
        "the scanner queue",
        "the e-filing portal",
        "the phone system",
        "the badge reader",
        "the research database",
        "the conference room display",
    ),
    "step": (
        "the cite check",
        "the conflicts run",
        "the second read",
        "the redline pass",
        "the calendaring check",
        "the partner sign-off",
        "the proofread",
        "the quality check",
        "the intake review",
        "the file audit",
        "the numbering pass",
        "the service check",
    ),
    "surface": (
        "the shared drive",
        "the working folder",
        "the document system",
        "the matter folder",
        "the chron file",
        "the case index",
        "the client portal",
        "the reading file",
        "the correspondence folder",
        "the pleadings folder",
    ),
}

REACTIONS: tuple[str, ...] = (
    "thumbsup",
    "coffee",
    "tada",
    "eyes",
    "raised_hands",
    "white_check_mark",
    "clap",
    "pray",
    "rocket",
    "sweat_smile",
)

# Two standing forms of words seed the one-to-one custody/second-read audits.
# Both slots are ordinary DM filler now: BOTH standing-request fabrics are
# authored deterministically by the storylines, not left to procedural chance,
# so that every graded request carries a designed contested response timing --
# the *second-read* "quick look at my draft" asks come from S7
# (StorylineDirector._register_s7) and the *visitor-log* "sign-in sheet" asks
# come from S8 (StorylineDirector._register_s8). Keeping this a two-tuple with
# the same standing_request_rate preserves the RNG draw sequence byte-for-byte;
# only the body strings change, so procedural draws now emit neutral filler
# that neither audit's derivation ever matches.
STANDING_REQUESTS: tuple[str, ...] = (
    "you around for a quick question when you get a sec?",
    "any chance you're free for a quick sync later today?",
)

STANDUP: tuple[str, ...] = (
    "Good morning, I’m starting with {focus} and will be available "
    "for quick questions.",
    "Morning all, {focus} is my priority today; please message me "
    "if anything urgent arises.",
    "I’ll be working remotely while handling {focus}, with limited "
    "availability during court runs.",
    "Today begins with {focus}; I’ll check the channel regularly between meetings.",
    "Heading into the office shortly and planning to tackle "
    "{focus} before other requests.",
    "My main task this morning is {focus}, and I’ll share an "
    "update when there’s movement.",
    "I’m available at my desk for most of the day while working through {focus}.",
    "After a brief court run, I’ll return to {focus} and catch up on messages.",
    "Working from home today, I’ll focus on {focus} and remain reachable by chat.",
    "The first part of my day is reserved for {focus}; please flag "
    "anything time-sensitive.",
    "I’ll be in {place} for part of the morning, then continue with {focus}.",
    "Starting early on {focus}; I expect to be available for calls later.",
    "My calendar is fairly open today, so I can help with questions alongside {focus}.",
    "Today’s plan is to move {focus} forward and close out any related follow-ups.",
    "I’ll be away from my desk briefly for a court run, then return to {focus}.",
    "Good morning, I’m prioritizing {focus} and may be slower to respond before lunch.",
    "At present, {focus} is underway; I’ll post if I encounter a blocker.",
    "I’m keeping the morning focused on {focus}, with availability after lunch.",
    "Remote today and working steadily on {focus}; text me if the channel is urgent.",
    "My first meeting is later, so I’m using the morning to complete {focus}.",
    "I’ll be in and out of {place} while coordinating {focus}; message me as needed.",
    "Today I’m balancing {focus} with a few scheduled calls, but remain reachable.",
    "A quick heads-up: {focus} is taking priority, and I’ll be offline briefly {when}.",
    "I’m ready to get started on {focus}; please send any context that would help.",
    "The immediate goal is {focus}, though I may need assistance with a blocked item.",
    "I’ll handle {focus} from the office today and can make time for team questions.",
    "After wrapping an early errand, I’ll be online and focused on {focus}.",
    "My availability is good this morning while I work through {focus}.",
    "I’m planning to finish {focus} before turning to new requests later today.",
    "From {place}, I’ll review {focus} and coordinate next steps with the team.",
    "A court appearance may interrupt my morning, but I’ll return "
    "to {focus} afterward.",
    "I’m online and beginning {focus}; please use chat for anything that cannot wait.",
    "Today’s worklist starts with {focus}, followed by routine administrative tasks.",
    "I’ll be remote until {when}, then continue {focus} from the office.",
    "My schedule is light enough to support others while I make progress on {focus}.",
    "I’m setting aside uninterrupted time for {focus}, so replies "
    "may take a little longer.",
    "The morning’s priority is {focus}; I’ll update everyone if timing changes.",
    "I’ll be at {place} briefly and then available to discuss {focus}.",
    "A possible blocker is slowing {focus}; I’m checking the issue before escalating.",
    "I’m beginning the day with {focus} and expect to be reachable "
    "throughout the afternoon.",
    "Today I’ll divide my time between {focus} and scheduled court-related tasks.",
    "I’m working quietly on {focus} this morning, with calls available after lunch.",
    "The plan is straightforward: advance {focus}, monitor "
    "messages, and help where needed.",
    "I’ll start {focus} shortly and can review additional requests "
    "once that is underway.",
    "Good morning, I’m settled in and ready to make progress on {focus} today.",
    "I may be away for a court run around {when}, but otherwise "
    "I’m available while handling {focus}.",
)

STANDUP_FOCUS: tuple[str, ...] = (
    "drafting the initial complaint for {matter}",
    "reviewing the production set in {matter}",
    "preparing discovery requests for {matter}",
    "analyzing the contract issues in {matter}",
    "researching jurisdictional questions for {matter}",
    "revising the motion papers in {matter}",
    "calling opposing counsel about {matter}",
    "assembling exhibits for the {matter} filing",
    "checking citations in the memorandum for {matter}",
    "preparing a witness outline for {matter}",
    "reviewing deposition transcripts in {matter}",
    "drafting responses to interrogatories in {matter}",
    "organizing the pleadings for {matter}",
    "evaluating settlement positions in {matter}",
    "preparing a status update on {matter}",
    "researching damages theories for {matter}",
    "editing the declaration supporting {matter}",
    "coordinating service efforts for {matter}",
    "reviewing privilege issues in {matter}",
    "drafting proposed discovery deadlines for {matter}",
    "analyzing the deposition record in {matter}",
    "preparing a privilege log for {matter}",
    "revising the settlement agreement for {matter}",
    "checking the docket for {matter}",
    "outlining arguments for the hearing in {matter}",
    "reviewing correspondence concerning {matter}",
    "preparing filing instructions for {matter}",
    "researching evidentiary issues in {matter}",
    "drafting a meet-and-confer letter for {matter}",
    "organizing documents for the {matter} hearing",
    "reviewing expert materials related to {matter}",
    "preparing objections in {matter}",
    "editing the proposed order for {matter}",
    "calling the court clerk about {matter}",
    "analyzing statutory claims in {matter}",
    "assembling the closing set for {matter}",
    "drafting a fee petition for {matter}",
    "reviewing the procedural history of {matter}",
    "preparing the {step} for {matter}",
    "finalizing the filing package for {matter}",
)

MATTER_LINES: tuple[str, ...] = (
    "Can someone confirm the current status of {matter} before the next team check-in?",
    "I uploaded {task} for {matter} to {surface}; please review the tracked changes.",
    "Please let me know who can handle {task} for {matter} {when}.",
    "The deadline for {matter} is approaching, so flag any unresolved issues today.",
    "Has anyone received opposing counsel’s response regarding {matter}?",
    "For {matter}, I still need confirmation that {step} is complete.",
    "Could a paralegal verify the filing requirements for {matter}?",
    "I am covering {matter} while the assigned attorney is "
    "unavailable; please send updates here.",
    "Before we circulate anything on {matter}, confirm the latest approval status.",
    "The draft agreement for {matter} is ready for attorney review.",
    "Who is available to prepare {task} for {matter}?",
    "Please save the executed materials for {matter} in {surface}.",
    "A quick reminder: {matter} needs a privilege review before production.",
    "Do we have a current witness list for {matter}?",
    "I completed {step} on {matter} and noted two items needing follow-up.",
    "Please advise whether {task} for {matter} should proceed {when}.",
    "The court notice affecting {matter} is uploaded; confirm who will calendar it.",
    "Can someone check whether the filing fee for {matter} has been arranged?",
    "We need coverage for {matter} during the upcoming hearing preparation.",
    "The client update for {matter} is drafted and awaiting attorney edits.",
    "Has the team confirmed the responsible attorney for {matter}?",
    "I found a missing signature page in the {matter} materials; please investigate.",
    "For planning purposes, what remains open on {matter}?",
    "Please compare the latest production against the index for {matter}.",
    "The deadline tracker shows an upcoming response for {matter}; who owns it?",
    "I moved {task} for {matter} into {surface} for review.",
    "Could someone confirm whether service has been completed in {matter}?",
    "We should schedule a brief status call about {matter} {when}.",
    "The opposing party’s latest filing may affect {matter}; "
    "please review and summarize.",
    "Please hold further work on {matter} until the attorney "
    "confirms the requested approach.",
    "I am ready to finalize {task} for {matter} once the missing records arrive.",
    "Who can take the next procedural step for {matter}?",
    "The notes from today’s discussion of {matter} are available in {surface}.",
    "Please flag any conflicts concerns before assigning additional work on {matter}.",
    "We need an updated estimate of remaining work for {matter}.",
    "Has anyone confirmed the hearing materials for {matter} are complete?",
    "I will review {task} for {matter} and report back {when}.",
    "Please check whether the client has answered the outstanding "
    "questions for {matter}.",
    "The current draft in {surface} may not be the final version "
    "for {matter}; please verify.",
    "Can someone prepare a concise status summary for {matter}?",
    "The team should confirm all filing components for {matter} before submission.",
    "I noticed an unanswered discovery request in {matter}; who is "
    "coordinating the response?",
    "Please record completion of {step} for {matter} in the matter notes.",
    "We need attorney direction on the next move for {matter}.",
    "If anyone has capacity, please assist with {task} for {matter}.",
    "I will coordinate the remaining assignments for {matter}; "
    "send blockers directly in this channel.",
)

MATTER_REPLIES: tuple[str, ...] = (
    "I can take {task} after lunch.",
    "Let’s confirm {step} before moving ahead.",
    "I’ll review {task} when I’m back.",
    "Could someone own {step}?",
    "Happy to handle {task} {when}.",
    "Please flag any issues with {step}.",
    "I’ll circulate an update on {task}.",
    "Can we finish {step} {when}?",
    "I’m tracking {task} and will report back.",
    "Let’s coordinate {step} with the team.",
    "I’ll take the first pass on {task}.",
    "Would {when} work for completing {step}?",
    "Thanks, I’ll incorporate that into {task}.",
    "I can check {step} before the next handoff.",
    "Let’s keep {task} moving today.",
    "I’ll follow up once {step} is complete.",
    "Please send any context needed for {task}.",
    "I’m available to assist with {step}.",
    "We should revisit {task} {when}.",
    "I’ll confirm ownership of {step}.",
    "That works; I’ll proceed with {task}.",
    "Can we align on {step} first?",
    "I’ll prepare {task} for review.",
    "Once {step} is done, I’ll update everyone.",
    "I’m happy to cover {task} if needed.",
    "Let’s resolve {step} before circulating anything.",
    "I’ll check status on {task} {when}.",
    "Please let me know if {step} changes.",
    "I can coordinate the handoff for {task}.",
    "We’re set to begin {step} {when}.",
    "I’ll review the latest notes on {task}.",
    "Would you like me to handle {step}?",
    "I’ll keep an eye on {task}.",
    "Let’s close out {step} together.",
    "I’ll send a concise status update {when}.",
)

BILLING_LINES: tuple[str, ...] = (
    "Please review the prebills for {matter} and flag any "
    "unexplained time entries before {when}.",
    "The invoice batch is ready; confirm approvals and release the "
    "clean items through {system}.",
    "Can we reconcile trust balances before sending statements, "
    "especially where replenishment language appears?",
    "Write-down recommendations should identify the timekeeper, "
    "task, and reason rather than using a general adjustment note.",
    "Receivables older than our normal collection window need a "
    "clear owner and next action.",
    "Please confirm the current rate table is loaded correctly for "
    "all active matters and timekeepers.",
    "Narratives should explain the work performed and its purpose, "
    "not simply repeat a task label.",
    "Expense entries without receipts or other backup should "
    "remain pending until documentation is attached.",
    "I found inconsistent billing rates across several prebills; "
    "please compare them with the approved engagement terms.",
    "Before posting invoices, verify that trust applications match "
    "the ledger and the supporting authorization.",
    "The outstanding receivables report needs updated collection "
    "notes for every balance without a recent contact.",
    "For {matter}, please revise the narrative for {task} so the "
    "client can understand the value of the work.",
    "Could someone confirm whether the revised rate table has "
    "propagated through {system}?",
    "Please separate administrative time from substantive work "
    "when reviewing the next prebill batch.",
    "A clean expense backup packet should include the receipt, "
    "amount, date, and brief business purpose.",
    "Let’s hold any invoice with a negative trust balance until "
    "the account is corrected and reviewed.",
    "Write-downs need partner approval and a concise explanation "
    "before the invoice is finalized.",
    "The billing coordinator should compare posted invoices with "
    "the approved prebill totals before distribution.",
    "Please avoid vague narratives such as reviewed documents; "
    "identify what was reviewed and why.",
    "Receivables follow-up should distinguish disputed charges "
    "from invoices simply awaiting payment.",
    "Check whether unapplied trust funds are properly identified "
    "before preparing the next statement.",
    "The rate table should reflect approved increases, negotiated "
    "exceptions, and any billing restrictions.",
    "If an expense lacks backup, note the missing item directly "
    "rather than approving it silently.",
    "Please review {matter} for duplicate entries involving {task} "
    "before the prebill is circulated.",
    "A partner should sign off on any material write-down before "
    "the invoice reaches the client.",
    "The aging report is more useful when each balance includes "
    "the latest outreach and expected resolution.",
    "Please confirm invoice narratives use consistent terminology "
    "across related work and avoid internal shorthand.",
    "Trust transfers require matching ledger entries, "
    "authorization, and a clear invoice reference.",
    "Before releasing the batch, check tax treatment, interest "
    "settings, and mailing details in {system}.",
    "A prebill should show enough detail for us to identify "
    "omissions, duplication, and unreasonable time.",
    "Please flag any rate discrepancy immediately rather than "
    "correcting it after the invoice posts.",
    "The collection queue needs priorities based on amount, age, "
    "dispute status, and client communication.",
    "Expense backup should be attached in a readable format and "
    "linked to the correct billing entry.",
    "Where a write-down reflects inefficiency, document the "
    "corrective step for future billing review.",
    "Please confirm that all approved time and expenses for "
    "{matter} appear on the current prebill.",
    "The invoice narrative for {task} should state the "
    "deliverable, issue addressed, or decision supported.",
    "Let’s reconcile the trust ledger against the accounting "
    "report before applying any funds.",
    "If a client questions a charge, preserve the original entry "
    "and record the explanation in the billing notes.",
    "Please review the firm’s standard rate table for outdated "
    "titles or missing timekeeper categories.",
    "The next receivables review should include promised payment "
    "dates and unresolved billing questions.",
)

BILLING_REPLIES: tuple[str, ...] = (
    "I’ll post the billing update {when} after reviewing {task}.",
    "Could you confirm whether {task} is ready for billing?",
    "Please hold {task} until the time entry is corrected.",
    "The current entry for {task} needs a clearer description.",
    "I’ve matched the time record to {task}.",
    "Before submitting, let’s verify the hours for {task}.",
    "That charge appears related to {task}; please confirm.",
    "Can someone review the billing code attached to {task}?",
    "Once approved, I’ll include {task} in the next submission.",
    "The description should explain the work performed on {task}.",
    "I’m checking whether {task} was billed to the correct matter.",
    "Please send the supporting note for {task} {when}.",
    "We may need to separate the time entries covering {task}.",
    "My review of {task} found a possible duplicate entry.",
    "Let’s update the narrative before billing {task}.",
    "The time recorded for {task} looks reasonable to me.",
    "If everyone agrees, I’ll finalize {task} {when}.",
    "A revised entry would make {task} easier to audit.",
    "Please flag any adjustment needed for {task}.",
    "I’ve returned the entry for {task} with a brief note.",
    "After approval, the billing record for {task} can move forward.",
    "The submitted hours do not yet identify {task} clearly.",
    "Could the assigned attorney confirm completion of {task}?",
    "I’ll reconcile the invoice line with {task} {when}.",
)

IT_LINES: tuple[str, ...] = (
    "The printer near {place} is producing faint pages and may need a toner change.",
    "Could someone reconnect the scanner beside {place} to {system}?",
    "I cannot access {system} through the office Wi-Fi from my laptop.",
    "Please restart your VPN client before escalating connection failures.",
    "Has anyone found a spare charging cable for the laptop in {place}?",
    "The conference room display shows a blank screen when "
    "connected through the wall adapter.",
    "A password reset link for {system} expired before I could use it.",
    "Our shared printer is asking for credentials that worked earlier.",
    "If the scanner jams again, please leave {thing} nearby for identification.",
    "The office Wi-Fi is unusually slow in {place} this afternoon.",
    "My laptop installed an update and now the camera is unavailable.",
    "Badge access to {place} failed twice this morning.",
    "Could IT check whether backups completed successfully overnight?",
    "The reception phone cannot place outgoing calls, although incoming calls work.",
    "Please avoid unplugging the conference room equipment while "
    "{system} is presenting.",
    "A VPN connection drops whenever I open large files in {system}.",
    "Someone moved the scanner’s document feeder, and it no longer closes properly.",
    "The laptop assigned to {place} will not recognize its power adapter.",
    "Has the replacement badge for {place} arrived yet?",
    "The printer queue appears stuck with several duplicate jobs.",
    "I received repeated password prompts while working in {system}.",
    "Could someone test the microphone before the next conference room meeting?",
    "The records scanner is saving blank PDFs even when pages feed correctly.",
    "Our backup notice reports a warning for the workstation in {place}.",
    "Please report any lost badges to IT immediately so access can be disabled.",
    "The Wi-Fi signal disappears near {place} but remains available elsewhere.",
    "My phone’s voicemail indicator stays lit after all messages were deleted.",
    "An operating system update is waiting on the laptop in {place}.",
    "Can someone confirm whether {system} is currently experiencing an outage?",
    "The conference room speakers produce static when playing audio from a laptop.",
    "A printer restart cleared the error, but queued documents still are not printing.",
    "Please use the temporary VPN instructions posted in {place} until further notice.",
    "The scanner software closed unexpectedly while processing {thing}.",
    "I need help pairing the conference room remote with its display.",
    "Badge readers are rejecting valid credentials at the entrance to {place}.",
    "The laptop battery drains quickly even while connected to power.",
    "Would IT verify that automatic backups include files stored in {system}?",
    "Our desk phone has no dial tone after being moved to {place}.",
    "The wireless network requested a new password without warning.",
    "After lunch, please leave malfunctioning equipment in {place} for inspection.",
)

IT_REPLIES: tuple[str, ...] = (
    "I’ll check {system} and follow up {when}.",
    "Can you send a screenshot of the error in {system}?",
    "I’m looking into this now and will update you {when}.",
    "Please try signing out, then back into {system}.",
    "I can reset access to {system}; confirm your username.",
    "Let’s test whether the issue affects another browser.",
    "I’ll review the connection logs and report back {when}.",
    "Could you restart your computer and retry {system}?",
    "That sounds like an access issue; I’ll investigate.",
    "Please share the exact message appearing in {system}.",
    "I’ll check whether maintenance is affecting {system}.",
    "Try opening {system} in a private browser window.",
    "Your request is queued, and I’ll follow up {when}.",
    "I can help troubleshoot this over a quick call.",
    "Let me verify your permissions for {system}.",
    "Would another network connection work for you?",
    "I’m checking the account settings behind this problem.",
    "Please confirm whether everyone sees the same issue.",
    "A browser update may resolve this; I’ll verify compatibility.",
    "I’ll escalate if {system} remains unavailable {when}.",
    "Could you capture the steps leading to the error?",
    "The service appears reachable; I’ll inspect your account.",
    "Try clearing the browser cache before reopening {system}.",
    "I’ll take ownership and keep you posted {when}.",
)

DM_OPENERS: tuple[str, ...] = (
    "hey, can you send over {thing} when you get a minute?",
    "quick question: is {task} ready for a second set of eyes?",
    "morning — are you free to talk through {step}?",
    "could you leave {thing} by my desk?",
    "i’m picking up {task}; anything i should know?",
    "when you’re in {place}, can you check for {thing}?",
    "do you know who’s handling {step}?",
    "can we move our check-in to {when}?",
    "heads up, i’ll send {task} shortly",
    "would you mind uploading {thing} to {system}?",
    "is {place} open right now?",
    "i can take {task} if that helps",
    "are you waiting on anything from me for {step}?",
    "quick favor: can you print {thing}?",
    "let’s sync on {task} before {when}",
    "did {thing} make it to {place}?",
    "i’m free now if you want to review {step}",
    "can you confirm {task} went through {system}?",
    "who has the latest version of {thing}?",
    "i’ll be offline briefly; can you watch {task}?",
    "any chance you can cover {step}?",
    "are we still on for {when}?",
    "please flag anything odd in {thing}",
    "i found {thing} in {place}",
    "could you add me to {task}?",
    "what’s the status of {step}?",
    "i’m heading to {place}; need anything while i’m there?",
    "can you resend the link to {system}?",
    "let me know when {task} is ready",
    "did you want me to start {step}?",
    "i can drop off {thing} after lunch",
    "are you using {place} for the next hour?",
    "quick check: does {task} need approval?",
    "can you hold {thing} for me?",
    "i’m taking a look at {step} now",
    "would {when} work for a quick handoff?",
    "the latest {thing} is in {system}",
    "do you need help getting {task} finished?",
    "can you remind me where {thing} belongs?",
    "i’m stepping out; ping me about {step}",
    "is there a deadline for {task}?",
    "could you review this part of {thing}?",
    "i’ll handle {step} if you handle the upload",
    "are you around {when}?",
    "please let me know if {thing} changes",
    "i’m at {place}; want me to grab anything?",
    "can we trade tasks for {task}?",
    "did the system accept {thing}?",
    "i’ve got a question about {step}",
    "can you keep an eye on {task}?",
    "i’ll send the clean copy of {thing}",
    "are you okay with finishing {task} {when}?",
    "what should i do with {thing}?",
    "i’m blocked on {step}; can you take a look?",
    "can you meet me near {place}?",
    "the handoff for {task} is ready",
    "do you have access to {system}?",
    "i can scan {thing} if you leave it out",
    "when should i start {step}?",
    "i’m checking {task} against {thing}",
    "could you reserve {place} for a few minutes?",
    "is {thing} the final version?",
    "i’ll be in {place} shortly",
    "can you cover the phone while i finish {task}?",
    "what’s left before {step} is complete?",
    "i’m sending {thing} through {system}",
    "want to split up {task}?",
    "let me know if {when} still works",
    "can you take {thing} upstairs?",
    "i just finished {step}; your turn when ready",
    "is {task} on your list today?",
    "i’m grabbing coffee—need anything?",
    "could you archive {thing} in {system}?",
)

DM_REPLIES: tuple[str, ...] = (
    "sounds good, i’ll take {task}",
    "yes, that works for me",
    "i can handle {task} {when}",
    "agreed, let’s do it that way",
    "i’m on board with that approach",
    "can you send {thing} over?",
    "where should i save {task}?",
    "i’ll check {surface} first",
    "that works unless timing shifts",
    "i may need more time for {task}",
    "i’ve finished {task}",
    "{task} is done and uploaded",
    "i put {thing} in {surface}",
    "already handled on my end",
    "i’ll circle back {when}",
    "let me confirm before proceeding",
    "could you clarify which {thing}?",
    "i’m waiting on {thing} first",
    "that’s fine, with one small caveat",
    "i can do that after {when}",
    "yes, i saw your message",
    "i’ll review it shortly",
    "please hold off on {task}",
    "i’m not sure that’s workable",
    "would {when} be soon enough?",
    "i can cover the first part",
    "the rest may need another pass",
    "i’ll move {thing} to {surface}",
    "that matches my understanding",
    "i’m tracking this and will respond",
    "one issue: {thing} is missing",
    "i’ll verify {task} before sending",
    "thanks, i’ll take care of it",
    "i’m okay with that plan",
    "let’s revisit this {when}",
    "can you confirm the preferred version?",
    "i’ve saved the latest copy",
    "{thing} is ready for review",
    "i’ll need access to {surface}",
    "that should be straightforward",
    "i can’t promise it today",
    "i’ll pick this up {when}",
    "yes, please proceed",
    "i’d rather confirm one detail first",
    "the timing may be tight",
    "i’ve flagged {task} for follow-up",
    "nothing further needed from me",
    "i’ll compare both versions",
    "that’s done, subject to your review",
    "could you resend {thing}?",
    "i’ll keep an eye on {surface}",
    "i’m aligned, unless something changes",
    "let’s pause until {when}",
    "i’ve completed my portion",
    "i’ll update {task} once confirmed",
    "that should work on my end",
    "i’ll check and report back",
)

DM_CLOSERS: tuple[str, ...] = (
    "talk {when}",
    "catch you {when}",
    "let’s reconnect {when}",
    "i’ll follow up {when}",
    "more soon, {when}",
    "circle back {when}",
    "we’ll pick this up {when}",
    "i’ll check in {when}",
    "until {when}",
    "let’s touch base {when}",
    "i’ll be in touch {when}",
    "speak again {when}",
    "we can regroup {when}",
    "i’ll send an update {when}",
    "chat again {when}",
    "let’s continue {when}",
    "i’ll reach out {when}",
    "back to you {when}",
    "we’ll connect {when}",
    "take care until {when}",
    "i’ll keep you posted {when}",
    "let’s revisit this {when}",
    "more to come {when}",
    "i’ll confirm {when}",
    "we’ll talk then {when}",
    "checking back {when}",
    "i’ll circle around {when}",
    "let’s resume {when}",
    "i’ll share more {when}",
    "until we reconnect {when}",
    "we’ll take it from there {when}",
    "i’m here if needed",
)

INTERNAL_REPLIES: tuple[str, ...] = (
    "Thanks, {first}; I’ll take care of that {when}.",
    "Understood, {first}. I’ll confirm once it’s handled.",
    "Appreciate the update, {first}; I’ll keep an eye on it.",
    "Got it, {first}. I’ll send the requested information shortly.",
    "I’ll review this {when}, {first}, and follow up afterward.",
    "That works for me, {first}; thanks for coordinating.",
    "Received, {first}. I’ll save the materials in the appropriate folder.",
    "Thanks for flagging this, {first}; I’ll check the schedule.",
    "I can handle that, {first}, unless priorities have changed.",
    "Noted, {first}. I’ll let you know if anything is missing.",
    "I’ll coordinate with the team, {first}, and report back.",
    "Thanks, {first}. I’ll confirm the timing before proceeding.",
    "Understood on my end, {first}; I’ll proceed accordingly.",
    "I’ll look into the discrepancy, {first}, and circle back.",
    "That’s helpful, {first}. I’ll update the internal record.",
    "Acknowledged, {first}; I’ll complete the administrative step {when}.",
    "I’m on it, {first}. I’ll reach out if questions arise.",
    "Thanks for checking, {first}; the current arrangement still works.",
    "I’ll verify the details first, {first}, then move forward.",
    "Good to know, {first}. I’ll keep the file organized.",
    "I can make that adjustment, {first}; please send any further instructions.",
    "Thanks for the reminder, {first}. I’ll address it today.",
    "I’ll review the request, {first}, though one item may need clarification.",
    "That timing is workable, {first}; I’ll plan accordingly.",
    "I’ve noted this, {first}. I’ll wait for the remaining information.",
    "I’ll follow up {when}, {first}, unless you prefer an earlier response.",
    "Thanks, {first}; I’ll check whether the necessary approval is recorded.",
    "I understand, {first}. I’ll handle the next step.",
    "I’ll reconcile the entries, {first}, and flag anything inconsistent.",
    "Appreciate the notice, {first}; I’ll keep everyone informed.",
)

EXTERNAL_REPLIES: tuple[str, ...] = (
    "Thank you for the note; we have received it and will review "
    "the materials shortly.",
    "Acknowledged, and we appreciate the update. We will follow up after lunch.",
    "Your message is received. We are coordinating internally and "
    "will respond first thing tomorrow.",
    "Many thanks for flagging this; we will consider it and circle "
    "back when appropriate.",
    "We have noted your comments and are reviewing the related materials.",
    "Thank you for checking in. We will confer with the team and respond after lunch.",
    "This is to confirm receipt of your message; we will be back in touch shortly.",
    "We appreciate the information and will address the remaining "
    "questions first thing tomorrow.",
    "Your note reached us, and we are evaluating the next steps.",
    "Thanks for the update. We will review the details and follow up after lunch.",
    "I acknowledge receipt and will coordinate a substantive "
    "response with the appropriate team members.",
    "The materials are safely received; we will review them and "
    "respond when available.",
    "Thank you for bringing this to our attention. We are looking into it now.",
    "We have received your correspondence and will provide an "
    "update first thing tomorrow.",
    "Your email is acknowledged. We will confer internally before responding.",
    "Thanks for sending this along; we will review the information "
    "and follow up shortly.",
    "I appreciate the clarification and will discuss it with the team after lunch.",
    "Receipt is confirmed, and we will address your points in our next communication.",
    "We are reviewing your note and will respond once the relevant "
    "information has been assembled.",
    "Thank you for the prompt update; we will coordinate "
    "internally and be back in touch.",
    "Your message has been noted, and we will consider the requested action.",
    "I have received your email and will follow up after lunch "
    "with any necessary questions.",
    "The information is now under review; we will respond first thing tomorrow.",
    "Thank you for your patience. We are assessing the issue and "
    "will communicate next steps shortly.",
    "We acknowledge receipt and will review the materials before "
    "providing a further response.",
    "Your correspondence is appreciated; we will consult with the "
    "appropriate individuals and reply soon.",
    "Thanks for the notice. We will examine the matter and follow "
    "up when we have an update.",
)

TIME_NOTES: tuple[str, ...] = (
    "Draft and revise correspondence concerning {matter} for client review.",
    "Telephone conference with client regarding status and next steps in {matter}.",
    "Review and analyze agreements produced in {matter}.",
    "Prepare initial case assessment memorandum for {matter}.",
    "Revise draft pleading addressing issues presented in {matter}.",
    "Research applicable statutory requirements governing {matter}.",
    "Analyze procedural posture and recommend next steps for {matter}.",
    "Correspond with opposing counsel regarding scheduling in {matter}.",
    "Prepare discovery requests tailored to issues in {matter}.",
    "Review and organize documents relevant to {matter}.",
    "Draft response to correspondence concerning {matter}.",
    "Conference with client to discuss strategy for {matter}.",
    "Prepare exhibit index for materials supporting {matter}.",
    "Revise proposed settlement agreement addressing {matter}.",
    "Conduct legal research regarding claims arising from {matter}.",
    "Review and analyze opposing party’s filing in {matter}.",
    "Prepare filing package for submission in {matter}.",
    "Coordinate service requirements associated with {matter}.",
    "Draft notice concerning upcoming proceedings in {matter}.",
    "Telephone conference with opposing counsel regarding resolution of {matter}.",
    "Review deposition transcript excerpts relevant to {matter}.",
    "Prepare outline for client meeting concerning {matter}.",
    "Revise discovery responses addressing issues in {matter}.",
    "Analyze contractual provisions applicable to {matter}.",
    "Draft memorandum summarizing research performed for {matter}.",
    "Review incoming correspondence and identify action items for {matter}.",
    "Prepare documents for electronic filing in {matter}.",
    "Conference with internal team regarding strategy and status of {matter}.",
    "Draft proposed stipulation addressing procedural issues in {matter}.",
    "Review and revise client declaration supporting {matter}.",
    "Research judicial authority concerning disputed issues in {matter}.",
    "Prepare chronology of relevant events for {matter}.",
    "Correspond with client regarding requested information for {matter}.",
    "Analyze exhibits and identify materials pertinent to {matter}.",
    "Draft settlement communication concerning {matter}.",
    "Review court notice and calendar deadlines for {matter}.",
    "Prepare witness outline addressing factual issues in {matter}.",
    "Revise memorandum analyzing legal issues presented by {matter}.",
    "Telephone conference with client regarding settlement posture in {matter}.",
    "Review production and categorize documents responsive to {matter}.",
    "Draft requests for admission concerning disputed facts in {matter}.",
    "Prepare filing checklist and confirm requirements for {matter}.",
    "Analyze opposing party’s position and develop response for {matter}.",
    "Correspond with opposing counsel regarding proposed resolution of {matter}.",
    "Review and revise exhibit descriptions for {matter}.",
    "Conduct internal conference regarding document issues in {matter}.",
    "Prepare client meeting materials addressing {matter}.",
    "Draft procedural history section for submission concerning {matter}.",
    "Research filing requirements applicable to {matter}.",
    "Review correspondence and prepare response concerning {matter}.",
    "Revise draft agreement to reflect negotiations regarding {matter}.",
    "Telephone conference with court personnel concerning scheduling in {matter}.",
    "Prepare summary of documents reviewed in {matter}.",
    "Analyze discovery deficiencies and draft meet-and-confer "
    "correspondence for {matter}.",
    "Coordinate signatures and filing logistics for {matter}.",
    "Review pleadings and identify issues requiring attention in {matter}.",
    "Draft declaration describing facts relevant to {matter}.",
    "Prepare negotiation strategy and settlement analysis for {matter}.",
    "Correspond with client regarding status and anticipated steps in {matter}.",
    "Revise draft motion addressing procedural issues in {matter}.",
    "Review and analyze communications produced in {matter}.",
    "Prepare questions for witness interview concerning {matter}.",
    "Conduct legal research supporting proposed position in {matter}.",
    "Draft cover letter transmitting documents related to {matter}.",
    "Conference with opposing counsel regarding discovery in {matter}.",
    "Organize exhibits and update exhibit index for {matter}.",
    "Review court docket and update procedural calendar for {matter}.",
    "Prepare internal status report summarizing developments in {matter}.",
    "Revise client correspondence addressing open issues in {matter}.",
    "Analyze settlement terms and identify revisions for {matter}.",
    "Draft proposed order concerning relief requested in {matter}.",
    "Review signature pages and finalize submission materials for {matter}.",
    "Telephone conference with client regarding document collection for {matter}.",
    "Prepare agenda for internal conference concerning {matter}.",
    "Research evidentiary issues arising in {matter}.",
    "Review and summarize testimony relevant to {matter}.",
    "Draft follow-up correspondence regarding unresolved issues in {matter}.",
    "Assess procedural requirements and plan next steps for {matter}.",
    "Prepare final filing materials and confirm submission readiness for {matter}.",
    "Review opposing counsel’s proposal and formulate response for {matter}.",
)

MATTER_NOTES: tuple[str, ...] = (
    "Reviewed {task} for completeness and marked unresolved points "
    "in the working copy. The assigned attorney will address those "
    "points during {step}, then return the revised version to "
    "{surface} for review.",
    "Opposing counsel’s latest correspondence was saved to "
    "{surface}, and the response issues were summarized for the "
    "team. Counsel will confirm the preferred position during "
    "{step} before any reply is circulated.",
    "The paralegal updated {task} using the materials currently "
    "available and flagged one missing support item. The "
    "responsible attorney will determine whether that item is "
    "required and, if so, assign follow-up after {when}.",
    "A preliminary check of {task} identified inconsistent "
    "references across the supporting materials. The team will "
    "reconcile the references during {step} and preserve the "
    "corrected version on {surface}.",
    "Work on {task} is substantially complete, subject to attorney "
    "review. The remaining action is to verify the cited "
    "authorities and confirm that the final copy is suitable for "
    "filing or delivery.",
    "The intake materials were organized on {surface}, with "
    "missing items noted in the internal checklist. Staff will "
    "contact the appropriate source after {when} if the "
    "outstanding materials have not arrived.",
    "Counsel reviewed the current draft and requested narrower "
    "language in several sections. The assigned attorney will "
    "prepare a revised draft of {task}, then circulate it "
    "internally for a second review.",
    "A conflicts-related question remains open because one "
    "identifying detail is incomplete. The team will complete "
    "{step} once the missing information is received and will "
    "document the result in the file.",
    "The exhibit materials were reordered to match the proposed "
    "filing sequence. The exhibit index still requires "
    "verification against {task}, which will be completed during "
    "{step}.",
    "A response was received and uploaded to {surface}; its "
    "attachments appear incomplete. Staff will compare the "
    "response against the request list and identify any follow-up "
    "needed after {when}.",
    "The team completed an initial review of {task} and separated "
    "factual issues from drafting issues. Counsel will resolve the "
    "factual questions first, followed by a clean-up pass "
    "addressing form and consistency.",
    "Several references in the working copy point to superseded "
    "materials. The paralegal will update those references after "
    "{step} and confirm that the replacement materials are "
    "available on {surface}.",
    "The assigned attorney reviewed the procedural posture and "
    "identified the next required filing component. Staff will "
    "assemble {task}, confirm the applicable formatting "
    "requirements, and route it for attorney approval.",
    "A document received from the other side was saved to "
    "{surface} and linked to the relevant internal task. Counsel "
    "will assess its effect on the pending work and provide "
    "direction after {when}.",
    "The current version of {task} contains comments from multiple "
    "reviewers. The lead attorney will resolve conflicting "
    "suggestions during {step} and issue a clean version for final "
    "review.",
    "The file inventory was updated to reflect recently received "
    "materials. One category remains incomplete, and staff will "
    "continue searching {surface} before requesting clarification "
    "from the responsible contact.",
    "Initial preparation for {task} is complete, but the "
    "supporting record needs closer review. The next step is to "
    "confirm the underlying facts and identify any material that "
    "should be added or removed.",
    "A draft communication was prepared for attorney review and "
    "placed on {surface}. Counsel will confirm the requested "
    "relief and supporting explanation during {step} before the "
    "communication is sent.",
    "The team identified a potential inconsistency between {task} "
    "and the current case summary. The attorney responsible for "
    "the summary will compare both sources and revise the record "
    "if the discrepancy is confirmed.",
    "The requested records have been partially received and "
    "cataloged. Staff will review the remaining request categories "
    "after {when} and prepare a targeted follow-up for any items "
    "still outstanding.",
    "A quality-control review of {task} found formatting errors "
    "but no apparent substantive omission. The paralegal will "
    "correct the formatting, then return the document to counsel "
    "for a final substantive check.",
    "The latest internal comments were consolidated into a single "
    "working copy on {surface}. Counsel will decide which "
    "revisions to adopt during {step}, with unresolved issues "
    "tracked separately.",
    "The filing package is assembled except for the final "
    "supporting attachment. Staff will confirm its availability, "
    "update the exhibit index, and route the complete package for "
    "signature once the attachment is located.",
    "A preliminary review of the record identified an issue "
    "requiring clarification from the team. The responsible "
    "attorney will address the issue after {when} and determine "
    "whether {task} needs corresponding revision.",
    "The correspondence log was brought current and linked to the "
    "file materials on {surface}. Staff will monitor for a "
    "response and notify counsel if no further communication is "
    "received after {when}.",
    "Counsel approved the overall approach to {task} but requested "
    "additional support for one conclusion. The paralegal will "
    "locate the relevant source, add the support, and resubmit the "
    "draft for review.",
    "The internal checklist for {step} is partially complete. "
    "Staff will verify the remaining requirements against the "
    "file, note any exceptions, and report the status to counsel "
    "before the next review.",
    "Materials from the recent exchange were sorted by subject and "
    "placed on {surface}. The team will compare them with the "
    "existing record to determine whether any new issue affects "
    "{task}.",
    "The draft was returned with targeted edits and no request for "
    "a broader rewrite. The assigned attorney will incorporate the "
    "edits, complete {step}, and circulate the revised version "
    "internally.",
    "A missing signature or approval remains the only identified "
    "impediment to completing {task}. Staff will obtain the "
    "required approval after {when} and then update the filing or "
    "delivery package.",
    "The team reviewed the available procedural materials and "
    "confirmed the immediate work sequence. The next action is to "
    "complete {step}, followed by attorney review of the resulting "
    "record.",
    "An attachment referenced in the correspondence was not found "
    "on {surface}. Staff will search the related folders and "
    "request a replacement if the attachment remains unavailable "
    "after {when}.",
    "The factual chronology was updated from the materials "
    "currently in the file. Counsel will review the sequence for "
    "accuracy and identify any gaps before the chronology is used "
    "in {task}.",
    "A reviewer noted that several defined terms are used "
    "inconsistently. The paralegal will standardize those terms "
    "throughout {task} and verify cross-references before "
    "returning the document to counsel.",
    "The team received instructions concerning the next phase of "
    "work and recorded them in the internal task list. Staff will "
    "translate those instructions into {task} and flag any "
    "ambiguity for attorney confirmation.",
    "A review of {surface} located an earlier version of {task} "
    "that may contain useful edits. Counsel will compare the "
    "versions during {step} and select the authoritative working "
    "copy.",
    "The current record supports moving forward, although one "
    "factual point remains unverified. Staff will seek "
    "confirmation after {when} and update the internal summary "
    "before the next attorney conference.",
    "The draft filing was checked against the available "
    "requirements and appears procedurally complete. Counsel still "
    "must approve the substantive content, after which staff can "
    "prepare the final submission materials.",
    "A request for clarification was sent and saved to {surface}. "
    "The matter remains pending that response, and staff will "
    "update the task status when the requested information is "
    "received.",
    "The team completed the first pass on {task} and identified "
    "several items for attorney judgment. Those items will be "
    "reviewed during {step}, with any resulting changes "
    "incorporated into the next draft.",
    "Supporting materials were renamed and arranged consistently "
    "on {surface}. Staff will now cross-check the index against "
    "the file contents and report any missing or duplicative "
    "entries.",
    "The responsible attorney reviewed the open issues and "
    "assigned follow-up to staff. The next step is to complete "
    "{task}, document the result, and return the file for attorney "
    "review.",
    "A procedural inquiry was resolved through review of the "
    "available file materials. Staff will record the conclusion in "
    "the case summary and proceed with {step} unless counsel "
    "provides different instructions.",
    "The team is waiting for confirmation that the latest version "
    "of {task} is acceptable for circulation. Once approval is "
    "received, staff will distribute it internally and preserve "
    "the final copy on {surface}.",
    "Review of the work product is complete except for a final "
    "cite check. Staff will complete {step} after {when}, correct "
    "any identified errors, and send the finished version to "
    "counsel.",
    "The file remains open while the team completes the requested "
    "follow-up. Staff will monitor the outstanding item, update "
    "{surface} as materials arrive, and notify counsel when the "
    "record is ready for the next decision.",
)

MEETING_TITLES: tuple[str, ...] = (
    "Matter Strategy Huddle: {matter}",
    "Weekly Case Roundup",
    "Client Communications Sync",
    "Discovery Planning Session",
    "Briefing Team Check-In",
    "Upcoming Deadlines Review",
    "Settlement Position Meeting",
    "Research Assignments Huddle",
    "Court Filing Readiness",
    "Budget and Staffing Review",
    "Partner Associate Touchbase",
    "Risk Assessment Discussion",
    "Witness Preparation Session",
    "Document Review Check-In",
    "Trial Theme Workshop",
    "New Intake Evaluation",
    "Practice Group Roundtable",
    "Action Items Follow-Up",
    "Motion Strategy Meeting",
    "Calendar Coordination Huddle",
    "Conflicts Review Session",
    "Workload Balance Check",
    "Case Status Exchange",
    "Hearing Preparation Huddle",
    "Firm Operations Sync",
    "Open Questions Forum",
    "Matter Closeout Review: {matter}",
)

MEETING_DESCRIPTIONS: tuple[str, ...] = (
    "Meet at {place} {when} to review {task}.",
    "Please bring {task} to {place} {when}.",
    "Use this time at {place} to finalize {task}.",
    "Let’s check {task} together at {place} {when}.",
    "Gather in {place} {when} for a focused review of {task}.",
    "Confirm the next steps for {task} at {place}.",
    "Set aside time {when} to discuss {task} in {place}.",
    "We’ll work through {task} at {place} {when}.",
    "Join the review of {task} in {place}.",
    "Bring open questions about {task} to {place} {when}.",
    "Reserve {place} {when} for completing {task}.",
    "Walk through {task} with the team at {place}.",
    "Plan to resolve remaining items in {task} {when}.",
    "Use the meeting room at {place} to coordinate {task}.",
    "Check the current version of {task} at {place} {when}.",
    "Review assignments connected to {task} in {place}.",
    "Meet briefly at {place} {when} before advancing {task}.",
    "Align on the approach for {task} at {place}.",
    "Please attend a working session on {task} {when}.",
    "Take a few minutes at {place} to organize {task}.",
    "Discuss any blockers affecting {task} in {place} {when}.",
    "Finalize the handoff for {task} at {place}.",
    "Bring the latest updates on {task} to the team {when}.",
    "Coordinate responsibilities for {task} at {place} {when}.",
)

INTERNAL_EMAIL: tuple[EmailForm, ...] = (
    EmailForm(
        subject="Office Supplies Restock",
        body=(
            "Hi {first},\n"
            "\n"
            "The supply cabinet is running low on printer paper, binder "
            "clips, and blue pens. Please add any urgent requests to the "
            "shared office list before {when} so we can consolidate the "
            "order. If you take the last package of anything, note it on "
            "the list rather than leaving an empty shelf.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Coverage Needed for Reception",
        body=(
            "Hi {first},\n"
            "\n"
            "Could you cover the reception desk during {when}? Please "
            "watch for deliveries, direct visitors to the appropriate "
            "attorney, and note any messages in the reception log. If you "
            "need to step away, coordinate with someone nearby so the desk "
            "is not unattended.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Updated Building Access Reminder",
        body=(
            "Hi {first},\n"
            "\n"
            "Please remember to use your badge when entering the building "
            "and avoid holding secured doors open for people you do not "
            "recognize. Report any access issue to facilities and let me "
            "know if your badge stops working. This helps keep the office "
            "and records secure.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Training Session Registration",
        body=(
            "Hi {first},\n"
            "\n"
            "A short training session on {system} is available for anyone "
            "who wants a refresher. Please let me know whether you plan to "
            "attend {when}, and bring any workflow questions you have. We "
            "will focus on practical steps and common filing errors.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Benefits Enrollment Check",
        body=(
            "Hi {first},\n"
            "\n"
            "Please review your benefits information and confirm that your "
            "elections and contact details are current. If you need "
            "assistance, contact the benefits administrator directly and "
            "copy me on any unresolved issue. The firm can help explain "
            "the process, but personal selections should be checked "
            "carefully by each employee.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Records Room Housekeeping",
        body=(
            "Hi {first},\n"
            "\n"
            "We are tidying the records room and removing empty folders, "
            "duplicate supplies, and outdated routing notes. Please check "
            "anything you have stored in {place} and move active materials "
            "to the correct location. Do not discard substantive records; "
            "send questions to me before removing anything uncertain.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Travel Expense Reminder",
        body=(
            "Hi {first},\n"
            "\n"
            "When submitting travel expenses, please include receipts and "
            "a brief business purpose for each item. Upload the materials "
            "through the usual reimbursement process after returning to "
            "the office. If a receipt is unavailable, add a short "
            "explanation so accounting can review the request without "
            "delay.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Interview Schedule Support",
        body=(
            "Hi {first},\n"
            "\n"
            "We have an interview scheduled for a prospective staff member "
            "{when}. Please keep the conference area available, remove "
            "confidential papers, and let me know if you can greet the "
            "visitor. I will circulate the final schedule separately and "
            "will handle any changes to the interview plan.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Firm Social Gathering",
        body=(
            "Hi {first},\n"
            "\n"
            "We are planning an informal office gathering and would "
            "appreciate your response about attendance. Please also note "
            "any dietary restrictions or accessibility needs so "
            "arrangements can be made comfortably. Participation is "
            "optional, and regular work coverage will remain in place for "
            "anyone who is not attending.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Printer Maintenance Notice",
        body=(
            "Hi {first},\n"
            "\n"
            "The main printer will be unavailable while maintenance is "
            "completed {when}. Please send urgent jobs to the alternate "
            "device and collect printed materials promptly. If you see an "
            "error message or a paper jam, leave a note on the device "
            "rather than attempting repairs beyond the posted "
            "instructions.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Replacement Badge Photos",
        body=(
            "Hi {first},\n"
            "\n"
            "Facilities is updating badge photos for staff whose "
            "appearance has changed or whose current image is difficult to "
            "recognize. Please tell me if you need a replacement badge, "
            "and I will coordinate a brief appointment. Continue carrying "
            "your current badge until facilities confirms that the new one "
            "is ready.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Mailroom Collection Change",
        body=(
            "Hi {first},\n"
            "\n"
            "The outgoing mail and courier collection will take place "
            "earlier than usual {when}. Please place sealed items in the "
            "designated tray with complete addressing and any required "
            "service instructions. If something is time-sensitive, let me "
            "know directly so it is not missed during the handoff.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Holiday Coverage Planning",
        body=(
            "Hi {first},\n"
            "\n"
            "Please send me your availability for holiday coverage so we "
            "can maintain reception, phone, and filing support with a "
            "small team. Include any periods when you are unavailable and "
            "any tasks you are comfortable handling remotely. I will "
            "circulate the final coverage plan once responses are in.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Phone Rota Confirmation",
        body=(
            "Hi {first},\n"
            "\n"
            "Please confirm whether you can take your scheduled phone "
            "coverage during {when}. Keep the call log current, forward "
            "urgent messages promptly, and arrange a swap if you become "
            "unavailable. Any change should be shared with the full "
            "coverage group so callers receive consistent support.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Research Subscription Renewal",
        body=(
            "Hi {first},\n"
            "\n"
            "We are reviewing the firm’s research subscriptions before "
            "renewal. Please tell me which services you actively use and "
            "identify any features that are no longer necessary. Include "
            "suggestions for access improvements, but do not share login "
            "credentials by email. I will compile the responses for "
            "review.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Wellness Room Etiquette",
        body=(
            "Hi {first},\n"
            "\n"
            "Please leave the wellness room ready for the next person by "
            "removing personal items, disposing of waste, and wiping "
            "shared surfaces after use. Keep visits reasonably brief when "
            "others are waiting. If supplies are missing or equipment "
            "needs attention, report it to office administration.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Parking Space Update",
        body=(
            "Hi {first},\n"
            "\n"
            "A parking space will be unavailable during building work "
            "{when}. Please use another authorized space and avoid "
            "blocking access lanes or neighboring offices. If you have a "
            "mobility concern or need help arranging temporary access, "
            "contact me so we can coordinate with building management.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Kitchen Cleanliness Reminder",
        body=(
            "Hi {first},\n"
            "\n"
            "Please label anything you leave in the refrigerator and "
            "remove it before it becomes outdated. Wipe counters after "
            "preparing food, rinse shared dishes, and report leaks or "
            "appliance problems promptly. Keeping the kitchen orderly "
            "makes it easier for everyone to use during busy workdays.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Library Shelf Reorganization",
        body=(
            "Hi {first},\n"
            "\n"
            "The law library is being reorganized to make frequently used "
            "materials easier to locate. Please return books and binders "
            "to their labeled sections and avoid leaving loose papers "
            "between volumes. If you find an item without a clear "
            "location, place it on the reshelving cart for review.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Archive Transfer Preparation",
        body=(
            "Hi {first},\n"
            "\n"
            "We are preparing a group of closed files for transfer to "
            "archival storage. Please confirm that active materials have "
            "been removed, indexes are complete, and any required "
            "retention notes are present. Send questions about a file to "
            "me before placing it in the archive staging area.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Conference Room Reservation Practice",
        body=(
            "Hi {first},\n"
            "\n"
            "Please reserve conference rooms through the shared calendar "
            "and release the reservation when plans change. Add a general "
            "purpose and expected duration so others can plan around the "
            "booking. Before leaving, clear confidential papers, erase "
            "whiteboards, and return furniture to its usual arrangement.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Confidential Shredding Pickup",
        body=(
            "Hi {first},\n"
            "\n"
            "A secure shredding pickup is scheduled {when}. Please place "
            "confidential paper in the locked shredding bins rather than "
            "recycling containers. Do not leave bags beside the bins or "
            "include personal items. If a bin is full, notify office "
            "administration so it can be serviced promptly.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Remote Work Equipment Check",
        body=(
            "Hi {first},\n"
            "\n"
            "Please confirm that your remote work equipment is functioning "
            "and that you have the current contact information for "
            "technical support. Report missing accessories, damaged "
            "devices, or connection problems before they affect deadlines. "
            "Firm equipment should be stored securely and returned when no "
            "longer needed.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Emergency Contact Review",
        body=(
            "Hi {first},\n"
            "\n"
            "Please review your emergency contact information and tell me "
            "if anything has changed. Accurate details help the firm "
            "respond appropriately if an urgent situation occurs. Send "
            "updates through the approved personnel process rather than "
            "including sensitive information in a general reply.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Fire Drill Preparation",
        body=(
            "Hi {first},\n"
            "\n"
            "Building management will conduct a fire drill {when}. Please "
            "follow the posted evacuation route, take personal essentials "
            "only if they are immediately available, and gather at the "
            "designated assembly point. Do not use elevators or reenter "
            "the building until authorized personnel provide further "
            "instructions.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Visitor Sign-In Reminder",
        body=(
            "Hi {first},\n"
            "\n"
            "All visitors should sign in at reception and wear the "
            "provided visitor badge while inside the office. Please meet "
            "guests promptly and escort them in secured areas. At "
            "departure, make sure the badge is returned and the visitor "
            "log is complete.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Courier Address Verification",
        body=(
            "Hi {first},\n"
            "\n"
            "Before sending any courier package, please verify the "
            "recipient address, return information, delivery instructions, "
            "and service level. Attach the correct routing materials and "
            "retain the tracking confirmation. If the package contains "
            "confidential contents, use the approved packaging and notify "
            "me of any unusual delay.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Workstation Cable Safety",
        body=(
            "Hi {first},\n"
            "\n"
            "Facilities is checking workstation cables for trip hazards "
            "and overloaded outlets. Please keep cords secured, avoid "
            "daisy-chaining power strips, and report damaged plugs or "
            "loose connections. Do not move shared equipment without "
            "checking with office administration, since some devices "
            "support multiple workstations.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="New Hire Orientation Materials",
        body=(
            "Hi {first},\n"
            "\n"
            "Please send me any suggestions for improving the new-hire "
            "orientation materials. We are checking that instructions for "
            "phones, badges, records, supplies, and {system} are clear and "
            "current. Practical examples are welcome, especially where a "
            "new employee may otherwise need to ask several people for "
            "help.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Address Book Update",
        body=(
            "Hi {first},\n"
            "\n"
            "Please review your entry in the internal address book and "
            "confirm that your phone number, role, and preferred contact "
            "method are accurate. Let me know about any correction needed "
            "for the firm directory. Keeping this information current "
            "helps staff reach the right person quickly.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Shared Calendar Cleanup",
        body=(
            "Hi {first},\n"
            "\n"
            "Please review your shared calendar and remove completed "
            "reservations, duplicate holds, and meetings that were "
            "canceled. Keep recurring entries accurate and include enough "
            "information for colleagues to understand the purpose of a "
            "booking. Avoid placing private details in calendars visible "
            "to the full office.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Office Temperature Feedback",
        body=(
            "Hi {first},\n"
            "\n"
            "Building management is collecting feedback about office "
            "temperature and airflow. Please tell me if your workspace is "
            "consistently too warm, too cool, or affected by a vent issue. "
            "Include the general area, such as {place}, so facilities can "
            "investigate without needing personal or confidential "
            "information.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Secure Document Handling Reminder",
        body=(
            "Hi {first},\n"
            "\n"
            "Please keep confidential papers face down or stored securely "
            "when you are away from your desk. Check that printers, "
            "meeting rooms, and shared trays are clear before leaving for "
            "the day. If you find unattended material, bring it to the "
            "appropriate owner or office administration.\n"
            "\n"
            "Best,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Annual Policy Acknowledgment",
        body=(
            "Hi {first},\n"
            "\n"
            "Please complete the annual acknowledgment for the firm’s "
            "administrative policies through the usual personnel process. "
            "Read each section carefully and raise any question before "
            "submitting. The acknowledgment confirms that you received the "
            "policies; it does not replace asking for guidance when a "
            "situation is unclear.\n"
            "\n"
            "Regards,\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Office Closure Checklist",
        body=(
            "Hi {first},\n"
            "\n"
            "Before the office closes, please check that lights are off, "
            "windows are secure, shared devices are shut down as directed, "
            "and confidential materials are stored. Make sure kitchen "
            "appliances are left in a safe condition and report anything "
            "unusual to building security or office administration.\n"
            "\n"
            "Thanks,\n"
            "{me}"
        ),
    ),
)

EXTERNAL_EMAIL: tuple[EmailForm, ...] = (
    EmailForm(
        subject="Deposition Availability",
        body=(
            "Dear {first},\n"
            "I am coordinating availability for the upcoming deposition "
            "and would appreciate several proposed time windows. Please "
            "let me know whether {when} works for your team, or send "
            "alternatives that accommodate the witness and counsel. Once "
            "we agree, I will circulate a confirmation with the location "
            "and attendance details.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Request for Updated Contact Information",
        body=(
            "Hello {first},\n"
            "Please send the current telephone number and email address "
            "for the witness so we can complete our scheduling records. If "
            "there is a preferred method for receiving notices, please "
            "include that as well. We will use the information only for "
            "coordinating the pending procedural arrangements.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Hearing Confirmation",
        body=(
            "Dear {first},\n"
            "This message confirms that I have noted the hearing "
            "information provided by the court. Please advise if any "
            "additional appearances, materials, or lodging arrangements "
            "are required from our side. I will notify you promptly if the "
            "court issues a revised notice or changes the anticipated "
            "format.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Courtesy Copy Transmittal",
        body=(
            "Hello {first},\n"
            "Attached is the requested courtesy copy for your review. "
            "Please confirm that the file opened successfully and let me "
            "know if you need a different format or a separate "
            "transmission. I have retained the original materials and can "
            "provide them through the agreed delivery method if necessary.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Expert Availability",
        body=(
            "Dear {first},\n"
            "I am available to discuss potential examination dates and "
            "preparation requirements. Please send the anticipated topics, "
            "estimated duration, and any materials you would like reviewed "
            "in advance. I can then confirm a workable schedule and "
            "identify any conflicts with previously arranged commitments.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Invoice for Completed Services",
        body=(
            "Hello {first},\n"
            "Attached is my invoice for services completed during the "
            "current billing period. It includes the work performed, time "
            "entries, and reimbursable expenses. Please confirm receipt "
            "and let me know if your accounting team requires a purchase "
            "reference, revised format, or additional supporting "
            "documentation.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Service Attempt Update",
        body=(
            "Dear {first},\n"
            "I am writing to report that service was attempted at the "
            "address provided, but the individual was not available. I "
            "will make another attempt when authorized and will provide a "
            "written status update afterward. Please advise if you have "
            "any corrected address or access information.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Proof of Service",
        body=(
            "Hello {first},\n"
            "Attached is the signed proof of service for your records. "
            "Please review the identifying information and let me know "
            "promptly if anything appears inconsistent with your "
            "instructions. I can provide the original document or a "
            "certified copy upon request.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Transcript Delivery Options",
        body=(
            "Dear {first},\n"
            "Please let me know whether you prefer the transcript "
            "delivered electronically, in print, or in both formats. I can "
            "also include an exhibit set and an expedited delivery option "
            "if needed. Once you confirm, I will finalize the order and "
            "send the estimated charges.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Correction Sheet Request",
        body=(
            "Hello {first},\n"
            "The transcript is available for review, and any proposed "
            "corrections should be submitted using the attached form. "
            "Please return the completed sheet within the permitted review "
            "period. If no changes are requested, a brief confirmation "
            "would be appreciated so we can close the file.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Mediation Scheduling",
        body=(
            "Dear {first},\n"
            "I am checking whether the proposed mediation window remains "
            "workable for your side. Please confirm the anticipated "
            "attendees, preferred format, and any accessibility or "
            "technology needs. After receiving your response, I will "
            "circulate the logistical details and preparation "
            "instructions.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Mediation Materials",
        body=(
            "Hello {first},\n"
            "Please send any mediation materials you intend to submit so "
            "they can be organized before the session. Electronic copies "
            "are acceptable, and larger files may be transmitted through a "
            "secure link. Let me know if you need additional time or have "
            "questions about the submission process.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Coverage Acknowledgement",
        body=(
            "Dear {first},\n"
            "I am acknowledging receipt of the materials forwarded for "
            "coverage review. I have opened the file and will contact you "
            "if additional information is needed. Please direct future "
            "correspondence to me and include any updated notices, "
            "invoices, or scheduling developments as they arise.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Request for Loss Documentation",
        body=(
            "Hello {first},\n"
            "Please provide the available records supporting the amounts "
            "currently under review, including invoices, payment "
            "confirmations, and related correspondence. Electronic copies "
            "are sufficient for the initial review. If any item is "
            "unavailable, please identify it and explain when an "
            "alternative may be provided.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Title Search Status",
        body=(
            "Dear {first},\n"
            "The title search is still in progress, and I expect to have a "
            "preliminary update when the search work is complete. Please "
            "confirm the legal description and requested delivery format. "
            "I will send the report and note any exceptions requiring "
            "attention.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Escrow Instruction Confirmation",
        body=(
            "Hello {first},\n"
            "Please confirm that the escrow instructions previously "
            "transmitted remain accurate and complete. In particular, "
            "verify the delivery method and authorized signatories. We "
            "will not release funds or documents until the required "
            "confirmations are received through the approved communication "
            "channel.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Recording Requirement Inquiry",
        body=(
            "Dear {first},\n"
            "Could you confirm whether any additional recording "
            "requirements apply to the document being prepared? Please "
            "identify the preferred formatting, acknowledgment language, "
            "and delivery method. We want to avoid rejection and will "
            "revise the package promptly if the recorder requires anything "
            "further.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Court Filing Receipt",
        body=(
            "Hello {first},\n"
            "The electronic filing was submitted successfully, and the "
            "receipt is attached for your records. Please review the "
            "filing information and advise if the court later issues a "
            "deficiency notice. I will monitor the docket and forward any "
            "relevant confirmation or follow-up message.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Filing Deficiency Notice",
        body=(
            "Dear {first},\n"
            "The clerk’s office issued a deficiency notice concerning the "
            "recent submission. Please review the attached message and let "
            "me know how you would like to proceed. I can prepare the "
            "corrected materials once you confirm the required changes and "
            "any applicable filing instructions.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Courtesy Reminder for Response",
        body=(
            "Hello {first},\n"
            "This is a courtesy reminder regarding the response requested "
            "in my earlier message. Please send the requested information "
            "when available, or let me know if additional time is needed. "
            "A short acknowledgment would help us keep the scheduling and "
            "document exchange on track.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Document Exchange Confirmation",
        body=(
            "Dear {first},\n"
            "I confirm receipt of the documents transmitted through the "
            "agreed method. The files appear accessible, and I am "
            "reviewing them for completeness. Please advise whether "
            "another transmission is expected or whether the exchange is "
            "considered complete from your perspective.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Secure Link Access",
        body=(
            "Hello {first},\n"
            "A secure link has been sent for the requested files. Please "
            "confirm that you can access and download the materials before "
            "the link expires. If the system presents an error, tell me "
            "what occurred and I will arrange an alternate delivery "
            "method.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Conference Call Details",
        body=(
            "Dear {first},\n"
            "Here are the details for our scheduled conference call. "
            "Please confirm that the listed participants and contact "
            "information are correct. If someone else should attend or if "
            "you need a different format, let me know before the call so I "
            "can revise the invitation.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Interpreter Request",
        body=(
            "Hello {first},\n"
            "Please confirm whether an interpreter will be needed for the "
            "proceeding and identify the required language. If you already "
            "have a preferred interpreter, send the contact information "
            "and availability. Otherwise, I can provide a request to the "
            "appropriate scheduling service.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Accommodation Information",
        body=(
            "Dear {first},\n"
            "Please advise whether any accessibility or other "
            "participation accommodations are needed for the upcoming "
            "appearance. Early notice will help the court or facility "
            "arrange the appropriate equipment and seating. I will keep "
            "the request limited to the information necessary for "
            "scheduling.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Exhibit Preparation Logistics",
        body=(
            "Hello {first},\n"
            "Please confirm the number of exhibit sets requested and "
            "whether you prefer tabs, binders, or electronic folders. I "
            "can prepare {thing} for delivery when the final materials are "
            "approved. Let me know if any confidentiality markings or "
            "special handling instructions apply.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Witness Travel Coordination",
        body=(
            "Dear {first},\n"
            "Please send the witness’s travel preferences and any "
            "limitations affecting transportation or lodging. I am "
            "coordinating the logistics and will provide proposed "
            "arrangements for approval. If the witness can participate "
            "remotely, please confirm the available equipment and a "
            "suitable location.\n"
            "{me}"
        ),
    ),
    EmailForm(
        subject="Payment Remittance Instructions",
        body=(
            "Hello {first},\n"
            "Please confirm the current remittance instructions for "
            "payment of the attached invoice. For security, send any "
            "banking information through the established verification "
            "process rather than by ordinary email. Once confirmed, I will "
            "update the payment record and acknowledge receipt of the "
            "remittance.\n"
            "{me}"
        ),
    ),
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
    standing_requests=STANDING_REQUESTS,
    standing_request_rate=0.15,
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
