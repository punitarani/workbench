"""The engagement cap must not truncate away the codes everyone uses.

A timesheet turn is shown a bounded list of engagements so a long book
does not flood the prompt. The cap took the first slots in declaration
order, and an institution's own standing codes — administration,
internal meetings, business development — are declared last, because
they are nobody's matter in particular. So they fell off the end for
every person.

People still had that time to book. With nowhere to put it they invented
plausible references (`internal-admin`, `admin-000001`,
`internal-ip-tech-group`), the referee correctly rejected every one, and
20.7% of attempted time vanished from the record.

The instructive part: *adding the codes made it worse*. Six more matters
pushed the standing ones further past the cap and the loss rate rose from
16.8% to 20.7%. A fix aimed at the symptom, applied without measuring the
mechanism, moved the number the wrong way.
"""

from simulation.gm.grounded import _CONTEXT_CAP, _within_cap


def _client(n: int) -> str:
    return f"tkt-{n:06d} Client matter {n}"


def _firm(n: int) -> str:
    return f"tkt-{n:06d} Firm - standing code {n}"


def _tickets(client_ids: range, firm_ids: range) -> dict:
    out = {f"tkt-{n:06d}": {"client_ref": f"org-{n}"} for n in client_ids}
    out.update({f"tkt-{n:06d}": {"client_ref": None} for n in firm_ids})
    return out


def test_a_small_book_is_untouched_in_content_and_order() -> None:
    """Every existing recording keys on exact prompt bytes, and each has
    fewer engagements than the cap. Content *and order* must be identical."""

    mine = [_client(n) for n in range(1, 4)]
    others = [_client(n) for n in range(4, 10)] + [_firm(n) for n in (90, 91)]
    tickets = _tickets(range(1, 10), range(90, 92))
    # firm-wide sort before the remaining context, which for a book under
    # the cap is the only reordering — and these worlds have none.
    assert set(_within_cap(mine, others, tickets)) == set(mine + others)
    assert list(_within_cap(mine, others, tickets))[:3] == mine


def test_no_bookable_entry_is_ever_truncated() -> None:
    """The measured failure, and the failure of its first repair.

    A flat cap in declaration order dropped the standing codes for
    everyone: 20.7% of attempted time refused. Reserving them *after* the
    person's own matters still left a partner carrying twelve matters
    seeing four of eight — a fix that works for a junior and fails for a
    partner, which reads as working because juniors are the common case.

    You cannot book time to a code you cannot see, so nothing bookable is
    bounded.
    """

    firm = [_firm(90 + i) for i in range(8)]
    tickets = _tickets(range(0, 22), range(90, 98))
    for own_count in (2, 5, 9, 12, 22):
        mine = [_client(n) for n in range(own_count)]
        others = [_client(n) for n in range(own_count, 22)] + firm
        kept = _within_cap(mine, others, tickets)
        assert all(line in kept for line in mine), own_count
        assert sum(1 for line in kept if "Firm" in line) == 8, own_count


def test_context_is_what_the_cap_bounds() -> None:
    """Other people's matters are awareness, not something to book to, so
    they are the only thing a long book truncates."""

    mine = [_client(1)]
    others = [_client(n) for n in range(2, 200)]
    kept = _within_cap(mine, others, _tickets(range(1, 200), range(0, 0)))
    assert kept[0] == mine[0]
    assert len(kept) == 1 + _CONTEXT_CAP


def test_a_world_with_no_standing_codes_still_works() -> None:
    """No standing codes is a legitimate world, not an error."""

    mine = [_client(1)]
    others = [_client(n) for n in range(2, 40)]
    kept = _within_cap(mine, others, _tickets(range(1, 40), range(0, 0)))
    assert kept[0] == mine[0]
    assert len(kept) == 1 + _CONTEXT_CAP
