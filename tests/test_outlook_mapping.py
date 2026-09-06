from backend.calendars import outlook_recurrence
import pytest


@pytest.mark.parametrize(
    "rule,expected",
    [
        ("FREQ=WEEKLY;BYDAY=MO", {"RecurrenceType": 1, "DayOfWeekMask": 2}),
        (
            "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
            {"RecurrenceType": 1, "DayOfWeekMask": 62},
        ),
        (
            "FREQ=MONTHLY;BYDAY=1TU",
            {"RecurrenceType": 3, "DayOfWeekMask": 4, "Instance": 1},
        ),
        ("FREQ=MONTHLY;BYMONTHDAY=5", {"RecurrenceType": 2, "DayOfMonth": 5}),
        ("FREQ=WEEKLY;INTERVAL=2", {"RecurrenceType": 1, "Interval": 2}),
    ],
)
def test_rrule_mapping(rule, expected):
    result = outlook_recurrence(rule)
    assert all(result[k] == v for k, v in expected.items())


def test_reject_before_write():
    with pytest.raises(ValueError):
        outlook_recurrence("FREQ=MONTHLY;BYSETPOS=2")


def test_com_timeout_is_bounded(monkeypatch):
    import subprocess
    from backend.calendars import OutlookCalendarProvider

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic COM test", 20)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="20 seconds"):
        OutlookCalendarProvider().list_events()
