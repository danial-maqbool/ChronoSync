"""Explicit manual integration test. Never collected by pytest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime, timedelta, timezone
from backend.calendars import OutlookCalendarProvider

if __name__ == "__main__":
    p = OutlookCalendarProvider()
    print(
        "Outlook read check:", len(p.list_events()), "events in the inspection window"
    )
    if (
        input("Type CREATE to write one test appointment to your real calendar: ")
        != "CREATE"
    ):
        raise SystemExit("No write performed")
    start = datetime.now(timezone.utc) + timedelta(minutes=5)
    event = {
        "id": "manual-test",
        "title": "ChronoSync Integration Test",
        "description": "User-authorized manual integration test",
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=10)).isoformat(),
        "timezone": "UTC",
        "all_day": False,
        "reminders": [1],
    }
    ident = p.create_event(event)
    print("Created EntryID:", ident)
    if input("Type DELETE to remove the test appointment: ") == "DELETE":
        p.delete_event(ident)
        print("Deleted")
