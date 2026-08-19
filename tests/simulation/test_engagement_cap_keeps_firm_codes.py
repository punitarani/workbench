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

from simulation.gm.grounded import _ENGAGEMENT_CAP, _within_cap


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
    assert _within_cap(mine, others, tickets) == tuple(mine + others)


def test_the_firm_codes_survive_a_long_book() -> None:
    """The measured failure: 30 engagements, standing codes declared last."""

    mine = [_client(n) for n in range(1, 5)]
    others = [_client(n) for n in range(5, 25)] + [_firm(n) for n in (90, 91, 92)]
    tickets = _tickets(range(1, 25), range(90, 93))

    naive = tuple(mine + others)[:_ENGAGEMENT_CAP]
    assert not any("Firm" in line for line in naive), "precondition: naive drops them"

    kept = _within_cap(mine, others, tickets)
    assert len(kept) == _ENGAGEMENT_CAP
    assert sum(1 for line in kept if "Firm" in line) == 3
    # The person's own matters are still first, and still all present.
    assert list(kept[:4]) == mine


def test_the_persons_own_matters_are_never_dropped_for_firm_codes() -> None:
    """Reserving must not push somebody's actual caseload out."""

    mine = [_client(n) for n in range(1, 13)]
    others = [_client(n) for n in range(13, 30)] + [_firm(n) for n in range(90, 96)]
    kept = _within_cap(mine, others, _tickets(range(1, 30), range(90, 96)))
    assert all(line in kept for line in mine)
    assert len(kept) == _ENGAGEMENT_CAP


def test_a_world_with_no_firm_codes_still_truncates() -> None:
    """No standing codes is a legitimate world, not an error."""

    mine = [_client(1)]
    others = [_client(n) for n in range(2, 40)]
    kept = _within_cap(mine, others, _tickets(range(1, 40), range(0, 0)))
    assert len(kept) == _ENGAGEMENT_CAP
    assert kept[0] == mine[0]
