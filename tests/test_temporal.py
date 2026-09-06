from backend.temporal import resolve
from backend.db import DEFAULTS
import pytest


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Meeting tomorrow at 4 PM", "2026-09-04T16:00"),
        ("Exam October 3 at 11 AM", "2026-10-03T11:00"),
        ("Submit 3 October", "2026-10-03T00:00"),
        ("Meeting next Friday at noon", "2026-09-11T12:00"),
        ("Meeting in two weeks", "2026-09-17T00:00"),
        ("Meeting moved from Tuesday to Thursday at 4 PM", "2026-09-03T16:00"),
        ("Conference September 3–5", "2026-09-03T00:00"),
        ("Meeting first Monday of next month", "2026-10-05T00:00"),
    ],
)
def test_temporal(text, expected):
    assert resolve(text, "2026-09-03T10:00:00+05:00", DEFAULTS)["start"].startswith(
        expected
    )


def test_timezone():
    assert (
        "T21:00"
        in resolve(
            "Meeting September 4 at 4 PM GMT", "2026-09-03T00:00:00+05:00", DEFAULTS
        )["start"]
    )


def test_ambiguity():
    for text in [
        "Meeting sometime next week",
        "Meeting Friday at 4",
        "EOD Friday",
        "Meeting not on Monday",
    ]:
        assert resolve(text, "2026-09-03", DEFAULTS)["warnings"]


def test_recurrence():
    assert (
        resolve("Meeting every Tuesday", "2026-09-03", DEFAULTS)["rrule"]
        == "FREQ=WEEKLY;BYDAY=TU"
    )


def test_range():
    assert resolve("Conference September 3–5", "2026-09-03", DEFAULTS)[
        "end"
    ].startswith("2026-09-06")
