from worldlog_fixtures import coherent_events

from core.worldlog.views import (
    conversation,
    directory,
    document_head,
    email_thread,
    inbox,
    ticket_snapshot,
)


def test_inbox_includes_to_and_cc() -> None:
    events = coherent_events()
    tom = inbox(events, "per-tom-okafor")
    meredith = inbox(events, "per-meredith-chao")
    daniel = inbox(events, "per-daniel-reyes")
    assert [m.message_id for m in tom] == ["msg-000001"]
    assert [m.message_id for m in meredith] == ["msg-000001"]
    assert daniel == ()


def test_email_thread_is_ordered() -> None:
    thread = email_thread(coherent_events(), "thr-000001")
    assert [m.message_id for m in thread] == ["msg-000001", "msg-000002"]


def test_conversation_messages() -> None:
    messages = conversation(coherent_events(), "cnv-000001")
    assert [m.chat_message_id for m in messages] == ["chm-000001"]


def test_ticket_snapshot_folds_changes() -> None:
    snapshot = ticket_snapshot(coherent_events(), "tkt-000001")
    assert snapshot.status == "in-review"
    assert snapshot.assignee == "per-daniel-reyes"
    assert snapshot.title == "Review NDA"


def test_document_head_returns_latest_revision() -> None:
    head = document_head(coherent_events(), "doc-000001")
    assert head.revision == 2
    assert head.content == "v2"
    assert head.path == "/legal/playbooks/nda-playbook.md"


def test_directory_lists_people() -> None:
    people = directory(coherent_events())
    assert len(people) == 4
    assert people[0].person_id == "per-meredith-chao"
