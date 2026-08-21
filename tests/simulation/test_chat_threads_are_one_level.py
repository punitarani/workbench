"""A chat thread is one level deep, as in the product these surfaces mirror.

Every reply in a real workspace carries the *root's* timestamp. There is
no reply-to-a-reply: open a thread and you see one parent and a flat list
under it.

The persona replies to whatever it was shown, which is the newest message
in the conversation, so replies chained. Measured on four recorded days:
**44 of 84 replies had a parent that was itself a reply**, with chains
nine deep.

Two things were wrong with that, and the second is why it was invisible.
The served surface sets `thread_ts` to the immediate parent, so a message
three deep named another reply as its thread root — a shape no real
workspace can represent, and a tool-parity break that an agent trained
against it would carry into the real product. And a chain gives every
root exactly one direct reply, so a four-message exchange reads as no
thread at all: `threaded_reply_share` measured 0.089 against a floor of
0.30, on a world whose replies were 65% of all messages.

Flattened at the referee, so the log is right and every surface derived
from it agrees. The tool's own write path already states the rule — "a
reply addressed at a reply belongs to that thread's parent, as in Slack"
— and its single level of resolution is sufficient once nothing nests
deeper.
"""

from core.events import Event
from core.events.chat import ChatConversationCreatedPayload
from core.events.control import SimDeliverablePayload
from core.events.people import PersonRecordPayload
from core.intents import ChatDraft, ChatIntent
from simulation.gm.grounded import GroundedGm, TicketVocabulary

# Three, not two. A two-member conversation takes the DM branch, which
# has always had a brake — so a fixture with two people exercises the path
# that was already correct and passes whatever the channel path does. The
# first version of the cascade test did exactly that.
PEOPLE = (
    ("per-ana", "Ana Reyes"),
    ("per-cecile", "Cecile Marchand"),
    ("per-noor", "Noor Haddad"),
)
CONVERSATION = "cnv-000001"


def _gm() -> GroundedGm:
    gm = GroundedGm(
        entity_for_person={pid: pid.removeprefix("per-") for pid, _ in PEOPLE},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )
    seq = 0
    for person_id, name in PEOPLE:
        seq += 1
        gm.world.apply(
            Event(
                seq=seq,
                event_id=f"evt-{seq:06d}",
                time=0,
                tag="person.record",
                source="gm",
                payload=PersonRecordPayload(
                    kind="person.record",
                    person_id=person_id,
                    name=name,
                    email_address=f"{name.split()[0].lower()}@example.test",
                    title="Associate",
                    department="Litigation",
                    manager=None,
                    affiliation="internal",
                    timezone="UTC",
                ),
            )
        )
    gm.world.apply(
        Event(
            seq=50,
            event_id="evt-000050",
            time=0,
            tag="chat.conversation.created",
            source="gm",
            payload=ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id=CONVERSATION,
                conversation_type="channel",
                name="litigation-group",
                members=tuple(pid for pid, _ in PEOPLE),
            ),
        )
    )
    return gm


def _event(seq: int) -> Event:
    return Event(
        seq=seq,
        event_id=f"evt-{seq:06d}",
        time=0,
        tag="sim.deliverable",
        source="gm",
        payload=SimDeliverablePayload(
            kind="sim.deliverable", entity="ana", day="2026-01-05"
        ),
    )


def _post(
    gm: GroundedGm, who: str, body: str, reply_to: str | None, seq: int
) -> tuple[str, str | None]:
    """Post and apply, returning (this message's id, the reply_to stored)."""

    drafts = gm._ground_chat(
        who.removeprefix("per-"),
        who,
        ChatIntent(
            conversation_ref=CONVERSATION,
            reply_to_ref=reply_to,
            draft=ChatDraft(body=body, summary="s"),
        ),
        _event(seq),
        0,
    )
    draft = drafts[0]
    gm.world.apply(
        Event(
            seq=seq + 1,
            event_id=f"evt-{seq + 1:06d}",
            time=0,
            tag=draft.tag,
            source="gm",
            payload=draft.payload,
        )
    )
    return draft.payload.chat_message_id, draft.payload.reply_to


def _reply_to_of(gm: GroundedGm, who: str, body: str, parent: str, seq: int):
    drafts = gm._ground_chat(
        who.removeprefix("per-"),
        who,
        ChatIntent(
            conversation_ref=CONVERSATION,
            reply_to_ref=parent,
            draft=ChatDraft(body=body, summary="s"),
        ),
        _event(seq),
        0,
    )
    return drafts[0].payload.reply_to


def test_a_reply_to_a_reply_names_the_root() -> None:
    gm = _gm()
    root, _ = _post(gm, "per-ana", "opening question", None, 100)
    first, _ = _post(gm, "per-cecile", "an answer", root, 200)
    assert _reply_to_of(gm, "per-ana", "following up", first, 300) == root


def test_a_nine_deep_chain_cannot_form() -> None:
    """The recorded shape, reproduced. Every message in the exchange must
    hang off the one message that started it."""

    gm = _gm()
    root, _ = _post(gm, "per-ana", "opening question", None, 100)
    latest = root
    seq = 200
    for turn in range(9):
        who = "per-cecile" if turn % 2 == 0 else "per-ana"
        latest, stored = _post(gm, who, f"turn {turn}", latest, seq)
        seq += 10
        # The stored parent, not just the derived root: a chain that is
        # nine deep in the log still reports the right root here, which is
        # how the first version of this test passed against the defect.
        assert stored == root, f"turn {turn} nested under {stored} rather than the root"
        assert gm.world.chat_thread_roots[latest] == root


def test_the_root_is_its_own_root() -> None:
    """So `chat_thread_roots.get(ref, ref)` is right for a first reply as
    well as a later one — without this the first reply would resolve to
    None and start a second thread."""

    gm = _gm()
    root, _ = _post(gm, "per-ana", "opening question", None, 100)
    assert gm.world.chat_thread_roots[root] == root


def test_a_fresh_post_is_not_a_reply() -> None:
    gm = _gm()
    _post(gm, "per-ana", "first", None, 100)
    drafts = gm._ground_chat(
        "cecile",
        "per-cecile",
        ChatIntent(
            conversation_ref=CONVERSATION,
            reply_to_ref=None,
            draft=ChatDraft(body="a new topic", summary="s"),
        ),
        _event(300),
        0,
    )
    assert drafts[0].payload.reply_to is None


def test_the_thread_survives_a_snapshot() -> None:
    """The roots live in world state, which is serialised at every
    checkpoint. A long recording resumes from one, and a resume that lost
    them would start chaining again from that point on — a world that is
    flat for 40 days and nested afterwards."""

    gm = _gm()
    root, _ = _post(gm, "per-ana", "opening question", None, 100)
    first, _ = _post(gm, "per-cecile", "an answer", root, 200)

    restored = _gm()
    restored.set_state(gm.get_state())
    assert restored.world.chat_thread_roots[first] == root
    assert _reply_to_of(restored, "per-ana", "later", first, 300) == root


# --- the cascade brake -------------------------------------------------
#
# Two personas in a channel had nothing to stop them replying to each
# other. The email branch caps chains at depth 3 — "without this cap,
# courteous personas acknowledge each other forever" — and the DM branch
# caps a burst at six, but the channel reply path had neither. That cost
# nothing while replying to a channel message was effectively impossible
# (3 replies in 3,177 messages) and became a runaway the moment pending
# items started naming a message to reply to. A chat delay of 30s plus
# body/30 admits hundreds of exchanges in one simulated day.


async def _grant(gm: GroundedGm, *, message_id: str, sender: str, reply_to: str):
    """Who the referee gives the next turn to, for a landed channel reply.

    `reply_to` is required rather than optional: the channel branch only
    grants a turn to the author of a message that was *replied to*, so a
    payload with `reply_to=None` returns no entities whatever the brake
    does — and an assertion built on one passes against any change. The
    first version of these three tests did that.
    """

    from core.events.chat import ChatMessagePayload

    return await gm.next_acting(
        Event(
            seq=900,
            event_id="evt-000900",
            time=0,
            tag="chat.message",
            source=sender.removeprefix("per-"),
            payload=ChatMessagePayload(
                kind="chat.message",
                chat_message_id=message_id,
                conversation_id=CONVERSATION,
                reply_to=reply_to,
                sender=sender,
                body="anything",
            ),
        )
    )


async def test_a_channel_volley_stops_being_granted_turns() -> None:
    gm = _gm()
    root, _ = _post(gm, "per-ana", "opening question", None, 100)
    latest, seq = root, 200
    for turn in range(6):
        who = "per-cecile" if turn % 2 == 0 else "per-ana"
        latest, _ = _post(gm, who, f"turn {turn}", latest, seq)
        seq += 10
    decision = await _grant(gm, message_id=latest, sender="per-cecile", reply_to=root)
    assert decision.entities == (), (
        "a channel exchange kept granting turns with no cap; the email and "
        "DM paths both stop here"
    )


async def test_a_quiet_channel_still_grants_the_first_turn() -> None:
    """The brake must not switch replying off — the runaway is what is
    wrong, not the reply."""

    gm = _gm()
    root, _ = _post(gm, "per-ana", "opening question", None, 100)
    first, _ = _post(gm, "per-cecile", "an answer", root, 200)
    decision = await _grant(gm, message_id=first, sender="per-cecile", reply_to=root)
    assert decision.entities == ("ana",), decision


async def test_a_wake_clears_the_streak() -> None:
    """The cap is 'until the day moves', not 'forever'. Without the reset a
    channel goes silent for the rest of the recording."""

    from core.events.control import SimWakePayload

    gm = _gm()
    root, _ = _post(gm, "per-ana", "opening", None, 100)
    latest, seq = root, 200
    for turn in range(6):
        who = "per-cecile" if turn % 2 == 0 else "per-ana"
        latest, _ = _post(gm, who, f"turn {turn}", latest, seq)
        seq += 10
    assert (
        await _grant(gm, message_id=latest, sender="per-cecile", reply_to=root)
    ).entities == ()
    gm.world.apply(
        Event(
            seq=800,
            event_id="evt-000800",
            time=3600,
            tag="sim.wake",
            source="gm",
            payload=SimWakePayload(kind="sim.wake", entity="ana"),
        )
    )
    assert (
        await _grant(gm, message_id=latest, sender="per-cecile", reply_to=root)
    ).entities != ()
