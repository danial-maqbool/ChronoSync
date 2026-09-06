from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from backend.temporal import aware


class CalendarProvider(ABC):
    @abstractmethod
    def create_event(self, event): ...
    @abstractmethod
    def update_event(self, external_id, event): ...
    @abstractmethod
    def delete_event(self, external_id): ...
    @abstractmethod
    def list_events(self): ...
    @abstractmethod
    def get_event(self, external_id): ...


class MockCalendarProvider(CalendarProvider):
    def __init__(self, store):
        self.store = store

    def create_event(self, event):
        return self.store.put(
            "mock_calendar",
            {**event, "id": "mock-" + event["id"], "app_id": event["id"]},
        )["id"]

    def update_event(self, external_id, event):
        if not self.get_event(external_id):
            raise ValueError("Calendar entry missing; explicit recreation required")
        self.store.put(
            "mock_calendar", {**event, "id": external_id, "app_id": event["id"]}
        )
        return external_id

    def delete_event(self, external_id):
        e = self.get_event(external_id)
        if e:
            self.store.put("mock_calendar", {**e, "deleted": True})

    def list_events(self):
        return [e for e in self.store.all("mock_calendar") if not e.get("deleted")]

    def get_event(self, external_id):
        e = self.store.get("mock_calendar", external_id)
        return e if e and not e.get("deleted") else None


@contextmanager
def outlook():
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(
            "Direct Outlook integration is unavailable. Install pywin32 and classic Outlook, or export ICS."
        ) from exc
    pythoncom.CoInitialize()
    try:
        app = win32com.client.Dispatch("Outlook.Application")
        yield app, app.GetNamespace("MAPI")
    finally:
        pythoncom.CoUninitialize()


class _OutlookCOMProvider(CalendarProvider):
    def _write(self, item, event):
        recurrence = outlook_recurrence(event.get("rrule"))
        item.Subject = event["title"]
        item.Body = event.get("description", "")
        item.Location = event.get("location", "")
        item.MeetingStatus = 0  # Appointment only; never send invitations.
        item.AllDayEvent = event.get("all_day", False)
        if event.get("all_day"):
            item.Start = aware(event["start"], event["timezone"]).replace(tzinfo=None)
            item.End = aware(event["end"], event["timezone"]).replace(tzinfo=None)
        else:
            item.StartUTC = (
                aware(event["start"], event["timezone"])
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )
            item.EndUTC = (
                aware(event["end"], event["timezone"])
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )
        reminders = event.get("reminders", [])
        item.ReminderSet = bool(reminders)
        if reminders:
            item.ReminderMinutesBeforeStart = min(reminders)
        if recurrence:
            pattern = item.GetRecurrencePattern()
            pattern.RecurrenceType = recurrence.pop("RecurrenceType")
            for name, value in recurrence.items():
                setattr(pattern, name, value)
            pattern.PatternStartDate = item.Start
            pattern.StartTime = item.Start
            pattern.Duration = int(
                (
                    aware(event["end"], event["timezone"])
                    - aware(event["start"], event["timezone"])
                ).total_seconds()
                / 60
            )
        elif getattr(item, "IsRecurring", False):
            item.ClearRecurrencePattern()
        item.Save()
        return item.EntryID

    def create_event(self, event):
        with outlook() as (app, ns):
            return self._write(app.CreateItem(1), event)

    def update_event(self, external_id, event):
        with outlook() as (_, ns):
            return self._write(ns.GetItemFromID(external_id), event)

    def delete_event(self, external_id):
        with outlook() as (_, ns):
            ns.GetItemFromID(external_id).Delete()

    def _read(self, item):
        return {
            "id": item.EntryID,
            "title": item.Subject,
            "start": item.StartUTC.replace(tzinfo=timezone.utc).isoformat(),
            "end": item.EndUTC.replace(tzinfo=timezone.utc).isoformat(),
            "all_day": bool(item.AllDayEvent),
            "timezone": "UTC",
            "location": item.Location,
            "description": item.Body,
            "rrule": None,
            "recurrence_unresolved": bool(item.IsRecurring),
        }

    def get_event(self, external_id):
        with outlook() as (_, ns):
            try:
                return self._read(ns.GetItemFromID(external_id))
            except Exception as exc:
                # Missing item is not conflated with general connection failures.
                if getattr(exc, "hresult", None) == -2147221233:
                    return None
                raise

    def list_events(self):
        with outlook() as (_, ns):
            items = ns.GetDefaultFolder(9).Items
            items.Sort("[Start]")
            items.IncludeRecurrences = True
            start = datetime.now() - timedelta(days=1)
            end = start + timedelta(days=100)
            items = items.Restrict(
                "[Start] < '"
                + end.strftime("%m/%d/%Y %I:%M %p")
                + "' AND [End] > '"
                + start.strftime("%m/%d/%Y %I:%M %p")
                + "'"
            )
            return [self._read(item) for item in items][:2000]


class OutlookCalendarProvider(CalendarProvider):
    """Bound COM calls so an unconfigured Outlook profile cannot hang the API."""

    def _call(self, action, external_id=None, event=None):
        import json
        import subprocess
        import sys
        from pathlib import Path

        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.outlook_worker"],
                input=json.dumps(
                    {"action": action, "external_id": external_id, "event": event}
                ),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=20,
                cwd=Path(__file__).resolve().parents[1],
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Outlook did not respond within 20 seconds. Check its profile/sign-in dialogs or use ICS. A timed-out write must be reconciled in Outlook before retrying."
            ) from exc
        if result.returncode:
            raise RuntimeError(
                "Outlook connection failed: " + result.stderr.strip()[-1000:]
            )
        payload = json.loads(result.stdout)
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        return payload.get("result")

    def create_event(self, event):
        return self._call("create_event", event=event)

    def update_event(self, external_id, event):
        return self._call("update_event", external_id, event)

    def delete_event(self, external_id):
        return self._call("delete_event", external_id)

    def list_events(self):
        return self._call("list_events")

    def get_event(self, external_id):
        return self._call("get_event", external_id)


def outlook_recurrence(rule):
    """Translate supported RRULE fields before touching a COM appointment."""
    if not rule:
        return None
    import re

    fields = dict(part.split("=", 1) for part in rule.split(";"))
    if not set(fields) <= {
        "FREQ",
        "INTERVAL",
        "BYDAY",
        "BYMONTHDAY",
        "BYMONTH",
        "COUNT",
        "UNTIL",
    }:
        raise ValueError(
            "This recurrence needs ICS export; unsupported Outlook RRULE fields"
        )
    freq = fields["FREQ"]
    byday = fields.get("BYDAY", "")
    pattern = {
        "RecurrenceType": {"DAILY": 0, "WEEKLY": 1, "MONTHLY": 2, "YEARLY": 5}.get(freq)
    }
    if pattern["RecurrenceType"] is None:
        raise ValueError("Unsupported Outlook recurrence frequency")
    pattern["Interval"] = int(fields.get("INTERVAL", "1"))
    masks = {"SU": 1, "MO": 2, "TU": 4, "WE": 8, "TH": 16, "FR": 32, "SA": 64}
    if byday:
        ordinal = re.fullmatch(r"(-1|[1-4])(MO|TU|WE|TH|FR|SA|SU)", byday)
        if ordinal and freq in {"MONTHLY", "YEARLY"}:
            pattern["RecurrenceType"] = 3 if freq == "MONTHLY" else 6
            pattern["Instance"] = 5 if ordinal[1] == "-1" else int(ordinal[1])
            pattern["DayOfWeekMask"] = masks[ordinal[2]]
        else:
            if any(d not in masks for d in byday.split(",")):
                raise ValueError("Unsupported Outlook ordinal recurrence")
            pattern["DayOfWeekMask"] = sum(masks[d] for d in byday.split(","))
    if fields.get("BYMONTHDAY"):
        if not fields["BYMONTHDAY"].isdigit():
            raise ValueError("Use ICS for negative or multiple month days")
        pattern["DayOfMonth"] = int(fields["BYMONTHDAY"])
    if fields.get("BYMONTH"):
        pattern["MonthOfYear"] = int(fields["BYMONTH"])
    if fields.get("COUNT"):
        pattern["Occurrences"] = int(fields["COUNT"])
    elif fields.get("UNTIL"):
        pattern["PatternEndDate"] = datetime.strptime(fields["UNTIL"][:8], "%Y%m%d")
    else:
        pattern["NoEndDate"] = True
    return pattern


def provider(name, store):
    if name == "mock":
        return MockCalendarProvider(store)
    if name == "outlook":
        return OutlookCalendarProvider()
    raise ValueError("Unknown calendar provider")


def snapshot(event):
    return {
        k: event.get(k)
        for k in [
            "title",
            "start",
            "end",
            "all_day",
            "location",
            "description",
            "rrule",
        ]
    }


def same_calendar(a, b):
    for k in ["title", "all_day", "location", "description", "rrule"]:
        if (a.get(k) or "") != (b.get(k) or ""):
            return False
    return all(
        aware(a[k], a.get("timezone", "UTC")) == aware(b[k], b.get("timezone", "UTC"))
        for k in ["start", "end"]
    )


def export_ics(events):
    from icalendar import Calendar, Event, Alarm

    cal = Calendar()
    cal.add("prodid", "-//ChronoSync//Local Calendar Assistant//EN")
    cal.add("version", "2.0")
    for event in events:
        if (
            not event.get("start")
            or event.get("deleted")
            or event.get("status") in {"PROPOSED", "NEEDS_REVIEW", "ARCHIVED"}
        ):
            continue
        ve = Event()
        ve.add("uid", event["id"] + "@chronosync.local")
        ve.add("dtstamp", datetime.now(timezone.utc))
        ve.add("summary", event["title"])
        start = aware(event["start"], event["timezone"])
        end = aware(event["end"], event["timezone"])
        ve.add(
            "dtstart",
            start.date() if event.get("all_day") else start.astimezone(timezone.utc),
        )
        ve.add(
            "dtend",
            end.date() if event.get("all_day") else end.astimezone(timezone.utc),
        )
        ve.add("description", event.get("description", ""))
        ve.add("location", event.get("location", ""))
        if event.get("rrule"):
            ve.add(
                "rrule", dict(part.split("=", 1) for part in event["rrule"].split(";"))
            )
        if event.get("status") == "CANCELLED":
            ve.add("status", "CANCELLED")
        for offset in event.get("reminders", []):
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", event["title"])
            alarm.add("trigger", -timedelta(minutes=offset))
            ve.add_component(alarm)
        cal.add_component(ve)
    return cal.to_ical()
