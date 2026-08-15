"""Ashgrove's spec: the comparison firm compiles and differs where it should.

The first launch of this firm died in the compiler on invented person
ids — names that read plausibly but belonged to nobody. These tests make
that a test failure instead of a failed run, and pin the properties that
make Ashgrove a *comparison* rather than a replicate.
"""

from workbench.core.seed import Seed
from workbench.simulation.workplace.compile import compile_workplace
from workbench.workplaces.ashgrove.epoch import epoch_director
from workbench.workplaces.ashgrove.epoch import epoch_spec as ashgrove_spec
from workbench.workplaces.calder.epoch import epoch_spec as calder_spec


class TestReferences:
    def test_every_reference_names_someone_who_exists(self) -> None:
        spec = ashgrove_spec(5)
        known = {person.person_id for person in spec.people}
        for ticket in spec.seed_tickets:
            for ref in (ticket.actor, ticket.requester, ticket.assignee):
                assert ref is None or ref in known, f"engagement names {ref}"
        for document in spec.seed_documents:
            assert document.author in known, f"document names {document.author}"
        for channel in spec.channels:
            for member in channel.members:
                assert member in known, f"channel {channel.name} names {member}"
        for event in spec.seed_calendar:
            assert event.organizer in known
            for attendee in event.attendees:
                assert attendee in known

    def test_it_compiles(self) -> None:
        compiled = compile_workplace(ashgrove_spec(3), Seed(root=7))
        assert len(compiled.personas) == 17
        assert len(compiled.clients) == 10
        assert compiled.timesheets, "the comparison firm runs the v2 engine"


class TestComparability:
    def test_the_cast_is_the_controlled_variable(self) -> None:
        """Same people, so a difference in the data belongs to the practice.

        One deliberate exception: Maya joins Calder mid-epoch as a scripted
        arrival, and works Ashgrove from day one. Ashgrove therefore has no
        arrival event at all, which keeps the comparison free of a
        mid-run cast change on one side only.
        """

        ashgrove = {
            person.person_id
            for person in ashgrove_spec(5).people
            if person.affiliation == "internal"
        }
        calder_at_genesis = {
            person.person_id
            for person in calder_spec(5).people
            if person.affiliation == "internal"
        }
        assert ashgrove - calder_at_genesis == {"per-maya-lindqvist"}
        assert calder_at_genesis - ashgrove == set()
        assert ashgrove_spec(5).arrivals == ()

    def test_the_book_is_the_variable_under_study(self) -> None:
        ashgrove = {
            person.person_id
            for person in ashgrove_spec(5).people
            if person.client_persona is not None
        }
        calder = {
            person.person_id
            for person in calder_spec(5).people
            if person.client_persona is not None
        }
        assert not (ashgrove & calder), "the two firms share no clients"

    def test_the_firms_are_separately_identified(self) -> None:
        assert ashgrove_spec(2).workplace_id != calder_spec(2).workplace_id
        assert "@ashgrovereid.example" in ashgrove_spec(2).people[0].email_address


class TestSeason:
    def test_fieldwork_season_is_busier_than_the_summer(self) -> None:
        director = epoch_director(Seed(root=7))
        february = sum(
            len(director.cues_for(f"2026-02-{day:02d}")) for day in range(9, 14)
        )
        july = sum(len(director.cues_for(f"2026-07-{day:02d}")) for day in range(6, 11))
        assert february > july, (
            f"audit fieldwork ({february}) should outweigh July ({july})"
        )

    def test_benefit_plan_work_peaks_before_the_5500_deadline(self) -> None:
        from workbench.workplaces.ashgrove.season import season_multipliers

        october = season_multipliers("2026-10-09")
        march = season_multipliers("2026-03-09")
        assert october.get("per-nora-behrens", 1000) > march.get(
            "per-nora-behrens", 1000
        )

    def test_the_two_firms_peak_in_different_months(self) -> None:
        """Calder crests at April 15; Ashgrove crests in fieldwork season."""

        from workbench.workplaces.ashgrove.season import (
            season_multipliers as ashgrove_season,
        )
        from workbench.workplaces.calder.season import (
            season_multipliers as calder_season,
        )

        april = "2026-04-13"
        february = "2026-02-11"
        assert max(calder_season(april).values(), default=0) > max(
            calder_season(february).values(), default=0
        )
        assert max(ashgrove_season(february).values(), default=0) >= max(
            ashgrove_season(april).values(), default=0
        )
