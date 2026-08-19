"""Does the record contradict itself, and where does it merely repeat itself?

Two different questions, deliberately answered by one pass, because the
evidence is the same and the verdict on it is what differs.

**Contradictions are defects.** A world where a ticket's history says it
moved out of `review` when the record already had it in `in-progress` is a
world no agent can be graded against: the answer depends on which of two
irreconcilable statements it happened to read. The materializer already
refuses a log like that, and it refused one — four such events in 6,544 —
after two people edited a ticket in the same tick and the second grounded
against a world its own event would land behind. This finds the same class
in the *served* surfaces, where the agent actually meets it.

**Ambiguities are material.** Two documents titled "Single Audit Playbook"
is not a broken world; firms really do that, and it is exactly the kind of
near-miss that separates an agent matching on a name from one matching on
an identity. It capped a reference solver at 0.976 before the key became
composite. So these are counted and reported, never failed — they are what
the entity-ambiguity tasks are built out of.

The distinction is the whole point. A task graded on a contradiction the
instruction does not resolve is a defect wearing a model's clothes; a task
graded on an ambiguity the instruction *does* resolve is just a hard task.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from workbench.analysis.world_facts import WorldFacts

# A firm really does mis-book time, so a few entries whose note names one
# client while the engagement belongs to another are realism, not damage.
# A seventh of the firm's day is something else. The ten-day world booked
# 164 of one engagement's 200 entries to Kestrel work on a Northwind
# software-diligence matter; the next recording, on the fixed engine, ran
# 7 in 1,408. The threshold sits between those two facts.
MISBOOKED_LIMIT = 0.05


@dataclass
class Coherence:
    """What the pass found, split by what it means."""

    # Irreconcilable statements. Any of these blocks a build.
    contradictions: list[str] = field(default_factory=list)
    # References to things that are not in the record at all.
    dangling: list[str] = field(default_factory=list)
    # Two things an agent could reasonably confuse. Reported, never failed.
    ambiguities: list[str] = field(default_factory=list)
    # Time whose note names a client other than the engagement's own.
    misbooked: int = 0
    time_entries: int = 0

    @property
    def misbooked_share(self) -> float:
        return self.misbooked / self.time_entries if self.time_entries else 0.0

    @property
    def ok(self) -> bool:
        return (
            not self.contradictions
            and not self.dangling
            and self.misbooked_share <= MISBOOKED_LIMIT
        )

    def report(self) -> str:
        lines = []
        if self.time_entries:
            verdict = "MISBOOKED" if self.misbooked_share > MISBOOKED_LIMIT else "time"
            lines.append(
                f"  {verdict}: {self.misbooked} of {self.time_entries} entries "
                f"({self.misbooked_share:.1%}) name a client the engagement "
                "they are booked to does not belong to"
            )
        for label, items in (
            ("CONTRADICTION", self.contradictions),
            ("DANGLING", self.dangling),
            ("ambiguity", self.ambiguities),
        ):
            for item in items[:25]:
                lines.append(f"  {label}: {item}")
            if len(items) > 25:
                lines.append(f"  {label}: ... and {len(items) - 25} more")
        return "\n".join(lines) or "  nothing to report"


def _field_chains(facts: WorldFacts, found: Coherence) -> None:
    """Every field change must claim the value the record actually held.

    This is what the agent reads as ``matter_history``, and a chain that
    does not join is a chain no reader can follow: the ticket is in two
    states at once and the task's answer depends on which row was seen.
    """

    for ticket in facts.tickets.values():
        held: dict[str, str] = {"status": ticket.status}
        for when, actor, name, old, new in ticket.changes:
            actual = held.get(name)
            if actual is not None and old and old.casefold() != actual.casefold():
                found.contradictions.append(
                    f"{ticket.ticket_id}.{name} at t={when} by {actor}: "
                    f"claims it was {old!r}, the record had {actual!r}"
                )
            held[name] = new


def _dangling_references(facts: WorldFacts, found: Coherence) -> None:
    for index, activity in enumerate(facts.activities):
        if activity.ticket_id not in facts.tickets:
            found.dangling.append(
                f"time entry {index} logs to {activity.ticket_id}, which no ticket is"
            )
        if activity.person_id not in facts.people:
            found.dangling.append(
                f"time entry {index} is logged by {activity.person_id}, who is nobody"
            )
    for email in facts.emails.values():
        for person in (email.sender, *email.to, *email.cc):
            if person not in facts.people:
                found.dangling.append(
                    f"{email.message_id} names {person}, who is nobody"
                )
        for document_id in email.attachments:
            if document_id not in facts.documents:
                found.dangling.append(
                    f"{email.message_id} attaches {document_id}, which no document is"
                )
        if email.in_reply_to and email.in_reply_to not in facts.emails:
            found.dangling.append(
                f"{email.message_id} replies to {email.in_reply_to}, "
                "which was never sent"
            )


def _revision_chains(facts: WorldFacts, found: Coherence) -> None:
    """Revisions must be 1..n with no gap and no repeat.

    A document whose versions run 1, 2, 2 cannot answer "how many versions"
    consistently, and that count is a graded field.
    """

    for document in facts.documents.values():
        numbers = [revision for revision, _author in document.chain]
        if numbers != list(range(1, len(numbers) + 1)):
            found.contradictions.append(
                f"{document.document_id} ({document.title!r}) has revisions {numbers}"
            )


def _ambiguities(facts: WorldFacts, found: Coherence) -> None:
    titles = Counter(document.title for document in facts.documents.values())
    for title, count in sorted(titles.items()):
        if count > 1:
            places = sorted(
                d.workspace for d in facts.documents.values() if d.title == title
            )
            found.ambiguities.append(
                f"{count} documents titled {title!r}, in {places} — a title-only "
                "key cannot tell them apart"
            )

    names = defaultdict(list)
    for person in facts.people.values():
        names[person.name].append(person.person_id)
    for name, ids in sorted(names.items()):
        if len(ids) > 1:
            found.ambiguities.append(f"{len(ids)} people named {name!r}: {sorted(ids)}")

    surnames = defaultdict(set)
    for person in facts.people.values():
        if person.name.split():
            surnames[person.name.split()[-1]].add(person.name)
    for surname, full in sorted(surnames.items()):
        if len(full) > 1:
            found.ambiguities.append(f"surname {surname!r} is shared by {sorted(full)}")

    # A ticket's display number is built from the client's name with spaces
    # removed, so two clients can collide there while their records do not.
    displays = Counter(facts.display_number(ticket_id) for ticket_id in facts.tickets)
    for display, count in sorted(displays.items()):
        if count > 1:
            found.ambiguities.append(f"{count} engagements display as {display!r}")


def _misbooked_time(facts: WorldFacts, found: Coherence) -> None:
    """Time whose note describes one client and whose engagement is another's.

    A rough measure on purpose — it asks only whether some organisation's
    first word appears in the note — but rough was enough. It reads 14% on
    the ten-day world and 0.5% on the next one, and the gap between those
    is a whole engagement's time being logged against the wrong client:
    164 of the 200 entries on a Northwind software-diligence matter
    describing a Kestrel 401(k) audit.

    That is not a fussy point about tidiness. Three tasks report time by
    engagement, and on a world like that the honest answer and the graded
    answer are different answers.
    """

    if not facts.orgs:
        return
    leading = {name.split()[0].casefold(): name for name in facts.orgs.values()}
    for activity in facts.activities:
        ticket = facts.tickets.get(activity.ticket_id)
        if ticket is None or ticket.client_ref is None:
            # The firm's own projects have no client to contradict.
            continue
        found.time_entries += 1
        note = (activity.note or "").casefold()
        named = {name for word, name in leading.items() if word in note}
        if named and facts.orgs.get(ticket.client_ref) not in named:
            found.misbooked += 1


def check(facts: WorldFacts) -> Coherence:
    """Read the world once and sort what it says into defect and material."""

    found = Coherence()
    _field_chains(facts, found)
    _dangling_references(facts, found)
    _revision_chains(facts, found)
    _misbooked_time(facts, found)
    _ambiguities(facts, found)
    return found
