from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.temporal import resolve
from backend.db import DEFAULTS
from backend.intelligence import conflicts


def test_dst_safety():
    s = {**DEFAULTS, "timezone": "America/New_York"}
    assert resolve("Meeting March 8 2026 at 2:30 AM", "2026-03-01", s)["start"] is None
    assert (
        resolve("Meeting November 1 2026 at 1:30 AM", "2026-10-01", s)["start"] is None
    )


def test_reminder_exact_once_and_snooze(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as c:
        start = datetime.now(timezone.utc) + timedelta(minutes=59, seconds=30)
        e = c.post(
            "/api/events",
            json={
                "title": "Reminder test",
                "start": start.isoformat(),
                "end": (start + timedelta(hours=1)).isoformat(),
                "reminders": [60],
            },
        ).json()
        app.state.reminder_tick()
        app.state.reminder_tick()
        assert len(app.state.store.all("notification")) == 1
        current = app.state.store.get("event", e["id"])
        current["snoozed_until"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        current["status"] = "SNOOZED"
        app.state.store.put("event", current)
        app.state.reminder_tick()
        app.state.reminder_tick()
        assert len(app.state.store.all("notification")) == 2


def test_external_change_blocks_overwrite(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as c:
        e = c.post(
            "/api/events",
            json={
                "title": "Test",
                "start": "2026-10-03T10:00:00+05:00",
                "end": "2026-10-03T11:00:00+05:00",
            },
        ).json()
        r = c.post("/api/events/" + e["id"] + "/action", json={"action": "sync"})
        assert r.status_code == 200
        external = app.state.store.all("mock_calendar")[0]
        external["title"] = "Changed externally"
        app.state.store.put("mock_calendar", external)
        assert (
            c.post(
                "/api/events/" + e["id"] + "/action", json={"action": "sync"}
            ).status_code
            == 409
        )
        assert app.state.store.all("mock_calendar")[0]["title"] == "Changed externally"


def test_recurrence_occurrences_and_conflicts(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        e = c.post(
            "/api/events",
            json={
                "title": "Weekly review",
                "start": "2026-09-07T10:00:00+05:00",
                "end": "2026-09-07T11:00:00+05:00",
                "rrule": "FREQ=WEEKLY;BYDAY=MO",
            },
        ).json()
        rows = c.get(
            "/api/calendar/occurrences",
            params={"start": "2026-09-01", "end": "2026-10-01"},
        ).json()
        assert len(rows) == 4
        later = {
            **e,
            "id": "other",
            "start": "2026-09-14T10:30:00+05:00",
            "end": "2026-09-14T11:30:00+05:00",
            "rrule": None,
        }
        assert conflicts(later, [e])[0]["severity"] == "PARTIAL_OVERLAP"


def test_manual_validation_and_export_formulas(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        assert (
            c.post(
                "/api/events",
                json={
                    "title": "bad",
                    "start": "2026-10-03T11:00:00",
                    "end": "2026-10-03T12:00:00",
                },
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/events",
                json={
                    "title": "bad",
                    "start": "2026-10-03T11:00:00+05:00",
                    "end": "2026-10-03T10:00:00+05:00",
                },
            ).status_code
            == 422
        )
        assert c.put("/api/settings", json={"eod": "25:00"}).status_code == 422
        c.post(
            "/api/events",
            json={
                "title": "=formula",
                "start": "2026-10-03T11:00:00+05:00",
                "end": "2026-10-03T12:00:00+05:00",
            },
        )
        assert "'=formula" in c.get("/api/export/csv").text


def test_outlook_reconciliation_preserves_unresolved_recurrence(tmp_path, monkeypatch):
    import backend.app as app_module
    from backend.calendars import MockCalendarProvider

    app = create_app(tmp_path)
    with TestClient(app) as c:
        e = c.post(
            "/api/events",
            json={
                "title": "Series",
                "start": "2026-10-05T10:00:00+05:00",
                "end": "2026-10-05T11:00:00+05:00",
                "rrule": "FREQ=WEEKLY;BYDAY=MO",
            },
        ).json()
        assert (
            c.post(
                "/api/events/" + e["id"] + "/action", json={"action": "sync"}
            ).status_code
            == 200
        )

        class UnresolvedProvider(MockCalendarProvider):
            def get_event(self, ident):
                return {
                    **super().get_event(ident),
                    "rrule": None,
                    "recurrence_unresolved": True,
                }

        monkeypatch.setattr(
            app_module, "provider", lambda name, store: UnresolvedProvider(store)
        )
        assert (
            c.post(
                "/api/events/" + e["id"] + "/action",
                json={"action": "reconcile", "confirm": True},
            ).status_code
            == 409
        )
        assert app.state.store.get("event", e["id"])["rrule"] == "FREQ=WEEKLY;BYDAY=MO"


def test_recurring_local_time_survives_dst_and_ics():
    from backend.intelligence import occurrences
    from backend.calendars import export_ics
    from icalendar import Calendar
    from dateutil.rrule import rrulestr

    event = {
        "id": "dst",
        "title": "Weekly New York call",
        "start": "2026-03-03T09:00:00-05:00",
        "end": "2026-03-03T10:00:00-05:00",
        "timezone": "America/New_York",
        "rrule": "FREQ=WEEKLY;BYDAY=TU",
        "status": "CONFIRMED",
    }
    rows = occurrences(
        event,
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    assert rows[0][0].hour == rows[1][0].hour == 9
    assert rows[0][0].utcoffset() == timedelta(hours=-5)
    assert rows[1][0].utcoffset() == timedelta(hours=-4)
    calendar = Calendar.from_ical(export_ics([event]))
    item = calendar.walk("VEVENT")[0]
    assert item["DTSTART"].params["TZID"] == "America/New_York"
    dates = list(
        rrulestr(
            item["RRULE"].to_ical().decode() + ";COUNT=2",
            dtstart=item.decoded("DTSTART"),
        )
    )
    assert dates[1].hour == 9 and dates[1].utcoffset() == timedelta(hours=-4)
    assert calendar.walk("VTIMEZONE")
