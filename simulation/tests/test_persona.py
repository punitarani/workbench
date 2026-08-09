from persona_fixtures import DANIEL, observed_events

from workbench.core.actions import IntentAction, IntentActionSpec
from workbench.core.intents import EmailDraft, EmailIntent
from workbench.core.worldlog.views import inbox
from workbench.simulation.persona.rendering import render_identity, render_thread
from workbench.simulation.persona.working_memory import WorkingMemoryComponent


def spec() -> IntentActionSpec:
    return IntentActionSpec(call_to_action="Decide your next action.")


def test_identity_block_is_byte_stable_and_complete() -> None:
    first = render_identity(DANIEL)
    second = render_identity(DANIEL)
    assert first == second
    for fragment in ("Daniel Reyes", "Senior Counsel", "lowercase", "flagging"):
        assert fragment in first


async def make_memory() -> WorkingMemoryComponent:
    memory = WorkingMemoryComponent(person_id="per-daniel-reyes")
    for event in observed_events():
        await memory.pre_observe(event)
    return memory


async def test_working_memory_matches_core_views() -> None:
    memory = await make_memory()
    from_view = inbox(observed_events(), "per-daniel-reyes")
    from_memory = inbox(memory.events(), "per-daniel-reyes")
    assert from_memory == from_view
    assert len(from_memory) == 1


async def test_pending_items_cover_unanswered_email_and_chat() -> None:
    memory = await make_memory()
    pending = memory.pending_items()
    refs = {item.ref for item in pending}
    assert "msg-000001" in refs
    assert any(item.channel == "chat" for item in pending)


async def test_thread_rendering_names_people() -> None:
    memory = await make_memory()
    rendered = render_thread(memory.events(), "thr-000001")
    assert "Jess Alvarez" in rendered
    assert "Vendor NDA - need your eyes" in rendered
    assert "review the attached NDA" in rendered


async def test_established_facts_grow_on_sent_intents() -> None:
    memory = await make_memory()
    intent = EmailIntent(
        thread_ref="thr-000001",
        reply_to_ref="msg-000001",
        draft=EmailDraft(
            to=("Jess Alvarez",),
            subject="Re: Vendor NDA - need your eyes",
            body="On it; expect redlines by Thursday.",
            summary="Told Jess redlines arrive by Thursday.",
        ),
    )
    await memory.post_act(IntentAction(intent=intent))
    assert "Told Jess redlines arrive by Thursday." in memory.get_state().facts


async def test_state_round_trips() -> None:
    memory = await make_memory()
    state = memory.get_state()
    fresh = WorkingMemoryComponent(person_id="per-daniel-reyes")
    fresh.set_state(state)
    assert fresh.pending_items() == memory.pending_items()
