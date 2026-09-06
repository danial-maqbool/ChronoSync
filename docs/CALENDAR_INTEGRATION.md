# Calendar integration

## Provider interface

`CalendarProvider` defines create_event, update_event, delete_event, list_events and get_event. Extraction never writes to providers. Manual approval is mandatory; uncertain dates, unresolved changes and possible duplicates block synchronization.

## Mock provider

The persistent mock provider stores synthetic calendar records in the local database. Stable mock IDs make repeated creation idempotent. Tests cover create/update/delete, external edits, missing entries and workflow history. A mock SYNCED label always identifies the mock provider; it is not a laptop-calendar write.

## Outlook Desktop

The Windows adapter uses pywin32 and classic Outlook COM, with CoInitialize/CoUninitialize on each calling thread. It creates appointments, sets MeetingStatus to appointment-only, and never sends invitations. EntryID is recorded after Save. Timed appointments use StartUTC/EndUTC; all-day appointments use date boundaries. Common RRULEs map to Outlook recurrence patterns. Unsupported rules fail explicitly and can use ICS instead.

Outlook supports one native reminder. The smallest configured offset is used; the app owns additional running-process reminders. Calendar inspection uses a bounded upcoming window. Live COM, profile, timezone and recurring reconciliation behavior must be validated on the target machine. Current local validation did not establish a working Outlook connection.

The separate `scripts/test_outlook_calendar.py` script first reads the calendar, then requires explicit CREATE and DELETE input. Normal pytest and Playwright never call this live write path.

## ICS fallback

The icalendar library emits VERSION 2.0, PRODID, VEVENT, stable UID, DTSTAMP, DTSTART, DTEND, SUMMARY, DESCRIPTION, LOCATION, RRULE and multiple VALARMs. All-day DTEND is exclusive. One-off timed values export in UTC; recurring timed events retain TZID and VTIMEZONE so local clock time survives daylight-saving changes. Unapproved/ambiguous/archived/deleted events are excluded. ICS export does not set SYNCED and does not silently open or import the file into a calendar.

## Sync state and external changes

States are NOT_SYNCED, SYNCED, OUT_OF_SYNC, SYNC_ERROR and CALENDAR_MISSING. The last successful snapshot is checked before updating. External changes block overwrites. Reconcile shows or accepts external state. Accepting an externally missing link detaches it; a later explicit sync is needed to recreate it.

App-only edits mark synchronized records OUT_OF_SYNC. App-and-calendar edits attempt provider update and preserve the local edit if the provider fails. Event status and provider failure are shown separately.

## Deletion and cancellation

Deleting a synced item requires choosing app-only or app-and-calendar. Internal deletion is soft deletion. Restore does not automatically recreate a removed calendar entry. Cancellation proposals require confirmation and an explicit calendar-copy choice. No attendee mail is sent.

## Conflicts

Before writes, compare event intervals with local and readable external records. FULL_OVERLAP, PARTIAL_OVERLAP and BACK_TO_BACK are supported with a configurable buffer. Recurrences expand over 90 days. All-day items do not block a whole day by default. A user must explicitly choose Keep Both to override a detected conflict.

Outlook identifiers follow Microsoft's [EntryID documentation](https://learn.microsoft.com/en-us/office/vba/api/outlook.appointmentitem.entryid).
