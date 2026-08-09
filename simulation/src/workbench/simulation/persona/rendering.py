"""Deterministic rendering of typed state into prompt-ready text.

Rendering produces data blocks only. Behavioral instructions live in DSPy
signature docstrings, where GEPA can evolve them.
"""

from collections.abc import Iterable

from workbench.core.events import Event
from workbench.core.worldlog.views import conversation, directory, email_thread
from workbench.simulation.persona.params import ProfessionalWorkerParams

_SHARE_POLICY_GUIDANCE = {
    "freely": "You share this openly when relevant.",
    "if_asked": (
        "You share this when asked directly, but you do not volunteer it "
        "unprompted, and never in writing to outsiders."
    ),
    "reluctant": (
        "You share this only under pressure from someone senior, and you "
        "hedge when you do."
    ),
}


def render_identity(params: ProfessionalWorkerParams) -> str:
    lines = [
        f"You are {params.name}, {params.title} ({params.seniority}).",
        params.role_description,
        f"Personality: {params.personality}",
        f"Email register: {params.channel_style.email_register}",
        f"Chat register: {params.channel_style.chat_register}",
    ]
    if params.channel_style.quirks:
        lines.append(f"Quirks: {params.channel_style.quirks}")
    lines.append(f"Working hours: {params.working_hours}")
    return "\n".join(lines)


def render_relationships(
    params: ProfessionalWorkerParams, names: dict[str, str]
) -> str:
    return "\n".join(
        f"- {names.get(r.person, r.person)}: {r.stance}. {r.notes}"
        for r in params.relationships
    )


def render_knowledge(params: ProfessionalWorkerParams) -> str:
    sections = []
    for item in params.knowledge:
        sections.append(
            f"[{item.topic}] {item.content}\n"
            f"Sharing: {_SHARE_POLICY_GUIDANCE[item.share_policy]}"
        )
    return "\n\n".join(sections)


def person_names(events: Iterable[Event]) -> dict[str, str]:
    return {record.person_id: record.name for record in directory(events)}


def render_thread(events: Iterable[Event], thread_id: str) -> str:
    events = list(events)
    names = person_names(events)
    messages = email_thread(events, thread_id)
    parts = []
    for message in messages:
        sender = names.get(message.sender, message.sender)
        recipients = ", ".join(names.get(p, p) for p in message.to)
        parts.append(
            f"From: {sender}\nTo: {recipients}\n"
            f"Subject: {message.subject}\n\n{message.body}"
        )
    return "\n\n---\n\n".join(parts)


def render_conversation(events: Iterable[Event], conversation_id: str) -> str:
    events = list(events)
    names = person_names(events)
    messages = conversation(events, conversation_id)
    return "\n".join(
        f"{names.get(m.sender, m.sender)}: {m.body}" for m in messages
    )
