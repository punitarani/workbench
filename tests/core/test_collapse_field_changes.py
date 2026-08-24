"""One update, two changes to the same field, is one change.

A recorded law firm produced this once in 377 updates:

    status: 'Intake' -> 'Awaiting Court'
    status: 'Intake' -> 'Active'

in a single event. Both claim the same prior value, and only the first
one is right. State ends at `Active`, and every later event in that
matter's chain reads from `Active` — so nothing is ambiguous about what
the status *is*, which is why the world-log validator classes this as
provenance rather than corruption.

The history is another matter. `matter_history` gained a row saying the
engagement moved to `Awaiting Court`, a transition the record never
durably held, and a status task reads exactly that table. A phantom row
is not a harmless one.

Four components read this rule, and three of them share this code. The
fourth — `analysis.world_facts` — deliberately restates it, because it
exists to disagree with the projection and code it imported could not.
"""

from core.events.tickets import FieldChange, collapse_field_changes


def _tuples(changes):
    return [(c.field, c.old, c.new) for c in changes]


def test_the_recorded_defect() -> None:
    got = collapse_field_changes(
        (
            FieldChange(field="status", old="Intake", new="Awaiting Court"),
            FieldChange(field="status", old="Intake", new="Active"),
        )
    )
    assert _tuples(got) == [("status", "Intake", "Active")]


def test_the_net_change_chains_with_what_came_next() -> None:
    """The point of the collapse: the surviving row must join to the
    following event, or the history is still broken, just differently.

    In the recorded world the next status event was `Active -> Closed`.
    """

    (row,) = collapse_field_changes(
        (
            FieldChange(field="status", old="Intake", new="Awaiting Court"),
            FieldChange(field="status", old="Intake", new="Active"),
        )
    )
    following = FieldChange(field="status", old="Active", new="Closed")
    assert row.new == following.old


def test_distinct_fields_are_all_kept() -> None:
    """Collapsing must not be deduplication. An update that moves status
    and priority together is ordinary and both rows belong in history."""

    got = collapse_field_changes(
        (
            FieldChange(field="status", old="Active", new="Closed"),
            FieldChange(field="priority", old="Emergency", new="Routine"),
        )
    )
    assert _tuples(got) == [
        ("status", "Active", "Closed"),
        ("priority", "Emergency", "Routine"),
    ]


def test_order_is_the_order_the_fields_first_appeared() -> None:
    got = collapse_field_changes(
        (
            FieldChange(field="priority", old="Low", new="High"),
            FieldChange(field="status", old="A", new="B"),
            FieldChange(field="priority", old="High", new="Urgent"),
        )
    )
    assert [c.field for c in got] == ["priority", "status"]


def test_three_changes_to_one_field_keep_the_outer_pair() -> None:
    got = collapse_field_changes(
        (
            FieldChange(field="status", old="A", new="B"),
            FieldChange(field="status", old="B", new="C"),
            FieldChange(field="status", old="C", new="D"),
        )
    )
    assert _tuples(got) == [("status", "A", "D")]


def test_an_ordinary_update_is_returned_unchanged() -> None:
    """The overwhelmingly common case must not move. 376 of 377 updates
    in the recorded world had nothing to collapse."""

    changes = (FieldChange(field="status", old="Active", new="Closed"),)
    assert _tuples(collapse_field_changes(changes)) == _tuples(changes)


def test_no_changes_is_no_changes() -> None:
    assert collapse_field_changes(()) == ()


def test_a_none_old_survives() -> None:
    """`old` is nullable, and `first_old` must keep None rather than
    coercing it — a field set for the first time has no prior value."""

    (row,) = collapse_field_changes(
        (
            FieldChange(field="assignee", old=None, new="per-ana"),
            FieldChange(field="assignee", old=None, new="per-cecile"),
        )
    )
    assert row.old is None
    assert row.new == "per-cecile"
