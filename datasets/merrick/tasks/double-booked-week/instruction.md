<!--
STOP — DO NOT FILL THIS BRIEF. The premise does not hold on this world.

Measured on the finished 67-day Merrick v6 record, over the 69 working days
its calendar actually covers:

    events per working day    4.7   the text below assumes ~47
    genuine clashes           5     in the WHOLE record; the text below
                                    assumes ~3.4 a day, i.e. ~34 rows in a
                                    two-week window

A ten-fold shortfall in volume and a register with five rows available in
six months. The numbers in the text were carried across from a different
world — this firm holds about five meetings a day, all of them scheduled by
the same docket manager into non-overlapping slots, and its people are not
double-booked because nothing here books them twice.

Retire it, or re-found it on a mechanism this world has. Do not re-window:
there is no window of a 69-working-day record that contains 34 clashes when
the record contains 5.

See docs/fidelity/task-viability.md, "double-booked-week has no material".
-->

# Who is actually double-booked

You are the practice manager at **Merrick Stanton LLP**, a litigation and
transactions firm.

The firm books its diary on a fixed grid and people are starting to miss
things. Before the partners agree to change how meetings are scheduled,
they want to know how bad the problem really is: how many times someone is
expected in two places **at the same moment**.

**Back-to-back is not double-booked.** A day of meetings that run straight
into one another is a hard day; it is not a clash, and counting it as one
is how a diary review turns into a number nobody believes. In this record
back-to-back pairs outnumber real clashes by roughly four to one, so the
distinction is most of the work.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage**, and **calendar**.

## The window

Register clashes on events starting **on or before «MEASURE: the last day
of the window, as a weekday and a date — e.g. "Friday 16 January 2026". At
the recorded rate this world schedules ~47 events per working day and
produces ~3.4 genuine clashes per working day against ~15 back-to-back
pairs. Two weeks puts ~470 events in front of the reader for ~34 rows.
Re-measure on the finished record: event volume scales with the cast.»** —
the firm's «MEASURE: how many working days that window is, counted as
weekdays from the record's first day to the boundary above, inclusive. This
is *not* a calendar-day count; the two differ by every weekend inside the
window.» working days.

An event starting after that boundary makes no row, even if it clashes with
one inside the window.

Which side of the boundary an event falls on is decided by its start in the
firm's own time zone (New York) — the same date this register reports as
`date` — not by UTC and not by any other clock a tool prints.

## What counts as a clash

Two events clash **for a person** when all of these hold:

1. That person is an attendee of **both**. The organizer of an event is
   always among its attendees in this firm's records, so organising counts
   as attending.
2. The two events **share at least one minute**.
3. They are different events.

**Sharing at least one minute is the whole rule, and it is exact.** An
event running 10:00–10:30 and an event running 10:30–11:00 share no minute:
the first has ended when the second begins. That is **not** a clash. An
event running 10:00–10:30 and one running 10:29–11:00 share one minute, and
that **is** a clash.

Whether the person could realistically get between them, whether one is
optional, whether either was declined, and whether one is a recurring
standing meeting make no difference. None of those are part of this
question.

## The register

Write `double_bookings.json` to the workspace root:

```json
{
  "window_end": "2026-01-16",
  "events_read": 0,
  "double_bookings": [
    {
      "person": "Rosalie Duchamp",
      "first_event": "cal-000041",
      "second_event": "cal-000052",
      "first_title": "Docket call",
      "second_title": "Northmoor diligence sync",
      "date": "2026-01-13",
      "overlap_minutes": 15
    }
  ]
}
```

One row per person per clashing pair. Two people caught by the same pair of
events make **two rows**; one person clashing three times in a week makes
three.

**The order of the two events is fixed, not free.** `first_event` is the
one that starts earlier. When both start at the same moment — which happens
often on a fixed grid — `first_event` is the one whose id sorts first as
text. Without this the same clash can be written two ways and the register
cannot be compared with itself.

`person` is the full name as the firm's records give it, not the internal
identifier. `first_title` and `second_title` are those events' own titles.

`date` is the date the **first** event starts.

`overlap_minutes` is the **shared time in whole minutes, rounded down**:
take the seconds the two events share and divide by 60, discarding any
remainder. For 10:00–10:30 against 10:15–11:00 that is 15.

Say it that precisely because a handful of events in this diary do not
start on a whole minute, and the other natural reading — counting the
clock-minutes both events are inside — gives a different answer for those.
Two events sharing 1,555 seconds share 25 whole minutes by this rule, not
26. Requirement 2 above follows the same definition: **events sharing less
than one whole minute do not clash.**

`events_read` counts the events inside the window — the ones you had to
look at.

## What is being measured

Whether the register is exactly the rule's output. The expensive mistake is
counting a pair that merely touches; the quiet one is missing a clash
because it spans two people who each need their own row.
