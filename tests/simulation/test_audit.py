from workbench.core.events import Event
from workbench.core.events.chat import ChatMessagePayload
from workbench.core.events.documents import DocumentRevisedPayload
from workbench.core.events.email import EmailMessagePayload
from workbench.simulation.audit.heuristics import (
    register_matches_channel,
    replies_address_their_threads,
    unwritten_standard_litmus,
)
from workbench.simulation.registry import programs


def _event(seq: int, payload) -> Event:
    return Event(seq=seq, time=seq * 100, tag=payload.kind, source="x", payload=payload)


def _chat(seq: int, sender: str, body: str) -> Event:
    return _event(
        seq,
        ChatMessagePayload(
            kind="chat.message",
            chat_message_id=f"chm-{seq:06d}",
            conversation_id="cnv-000001",
            reply_to=None,
            sender=sender,
            body=body,
        ),
    )


def _email(
    seq: int, sender: str, body: str, *, message_id=None, in_reply_to=None, subject="s"
) -> Event:
    return _event(
        seq,
        EmailMessagePayload(
            kind="email.message",
            message_id=message_id or f"msg-{seq:06d}",
            thread_id="thr-000001",
            in_reply_to=in_reply_to,
            sender=sender,
            to=("per-b",),
            cc=(),
            subject=subject,
            body=body,
        ),
    )


def _revision(seq: int, content: str) -> Event:
    return _event(
        seq,
        DocumentRevisedPayload(
            kind="document.revised",
            document_id="doc-000001",
            revision=2,
            author="per-b",
            content=content,
            change_summary="s",
        ),
    )


def test_litmus_passes_when_holder_states_then_artifact_reflects() -> None:
    events = [
        _chat(0, "per-a", "checking in"),
        _chat(1, "per-daniel", "flagging: vendor NDAs get a two-year term cap"),
        _revision(2, "Applied the two-year term cap per Daniel."),
    ]
    result = unwritten_standard_litmus(
        events, phrase="two-year term cap", holder="per-daniel"
    )
    assert result.passed
    assert result.statement_seq == 1
    assert result.artifact_seq == 2


def test_litmus_fails_when_phrase_leaks_before_statement() -> None:
    events = [
        _revision(0, "The two-year term cap is standard."),
        _chat(1, "per-daniel", "two-year term cap, as I always say"),
    ]
    result = unwritten_standard_litmus(
        events, phrase="two-year term cap", holder="per-daniel"
    )
    assert not result.passed


def test_litmus_fails_when_never_reaches_artifact() -> None:
    events = [_chat(0, "per-daniel", "two-year term cap please")]
    result = unwritten_standard_litmus(
        events, phrase="two-year term cap", holder="per-daniel"
    )
    assert result.stated_by_holder
    assert not result.reached_artifact


def test_reply_overlap_check() -> None:
    good_parent = _email(0, "per-a", "Please review the Vantage NDA today.")
    good_reply = _email(
        1, "per-b", "Reviewing the Vantage NDA now.", in_reply_to="msg-000000"
    )
    assert replies_address_their_threads([good_parent, good_reply]) == ()

    bad_reply = _email(
        2,
        "per-b",
        "Lunch tomorrow?",
        subject="unrelated",
        in_reply_to="msg-000000",
    )
    findings = replies_address_their_threads([good_parent, bad_reply])
    assert len(findings) == 1
    assert findings[0].check == "reply_addresses_thread"


def test_register_check_flags_verbose_chat() -> None:
    events = [
        _email(0, "per-a", "A long and thorough email body " * 5),
        _chat(1, "per-a", "ok"),
        _email(2, "per-b", "short"),
        _chat(3, "per-b", "an extremely long chat message that rambles " * 6),
    ]
    findings = register_matches_channel(events)
    assert [f.detail.split(":")[0] for f in findings] == ["per-b"]


def test_registry_enumerates_named_predictors() -> None:
    actor = programs()["professional_actor"]
    names = {name for name, _ in actor.named_predictors()}
    assert names == {
        "decide",
        "decide_extended",
        "draft_email",
        "draft_chat",
        "draft_ticket",
        "draft_document",
        "draft_meeting",
        "reflect",
    }


def test_litmus_accepts_artifact_before_statement_when_holder_authored() -> None:
    from workbench.simulation.audit.heuristics import knowledge_flow_litmus

    events = [
        _revision(0, "Capped the confidentiality term at two years."),
        _chat(1, "per-daniel", "flagging: vendor NDAs get a two-year term cap"),
    ]
    # _revision author is per-b; holder-authored artifact required
    result = knowledge_flow_litmus(
        events,
        statement_phrase="two-year term cap",
        artifact_markers=("two year", "two-year"),
        holder="per-daniel",
    )
    assert not result.passed, "artifact by a non-holder before the statement is a leak"

    own_revision = _event(
        0,
        DocumentRevisedPayload(
            kind="document.revised",
            document_id="doc-000001",
            revision=2,
            author="per-daniel",
            content="Capped the confidentiality term at two years.",
            change_summary="s",
        ),
    )
    events = [
        own_revision,
        _chat(1, "per-daniel", "flagging: vendor NDAs get a two-year term cap"),
    ]
    result = knowledge_flow_litmus(
        events,
        statement_phrase="two-year term cap",
        artifact_markers=("two year", "two-year"),
        holder="per-daniel",
    )
    assert result.passed, "holder-authored artifact then statement is legitimate flow"


def test_litmus_still_requires_both_evidence_channels() -> None:
    from workbench.simulation.audit.heuristics import knowledge_flow_litmus

    only_statement = [_chat(0, "per-daniel", "two-year term cap please")]
    result = knowledge_flow_litmus(
        only_statement,
        statement_phrase="two-year term cap",
        artifact_markers=("two year",),
        holder="per-daniel",
    )
    assert not result.passed
