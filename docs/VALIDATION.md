# Validation and remaining acceptance work

ChronoSync is a working local application. The full original specification is **not yet completely validated**. Real Outlook integration remains unverified. Optional cloud AI, OCR, Google Calendar, CalDAV and Windows startup are not implemented.

## Reproducible checks

Original local delivery: **107 backend tests passed**, **68/68 temporal benchmark cases passed**, **4 Vitest tests passed**, **2 Playwright scenarios passed**, production build passed. The Python test client emits two dependency deprecation warnings. `validation/summary.json` records that historical local delivery.

Android/cloud preparation: **111 backend tests passed**, **4 Vitest tests passed**,
**2 Playwright scenarios passed**, and the production web and Linux Docker builds
passed. A real disposable PostgreSQL 16 instance passed account isolation, source
and export access checks, and persistence across application restarts (see
`validation/cloud-smoke.json`). The running Docker service returned a healthy cloud
response and rejected an unauthenticated workspace request with HTTP 401.

The release APK builds and its signing certificate verifies. Installation and file
handling on a physical S25 Ultra remain unverified because no Android device is
connected. The Render/Neon deployment is now live at
https://chronosync-qk1q.onrender.com. Live health, authentication-status,
unauthenticated-access rejection, and cross-origin write rejection checks passed.
First-account registration and the authenticated dashboard were verified in the
live browser. This is not
an always-running reminder service; see [mobile hosting limitations](MOBILE_HOSTING.md).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/benchmark.py
cd frontend
npm.cmd test
npm.cmd run build
npm.cmd run e2e
```

Playwright starts an isolated server on port 8766 using a fresh database under `data/e2e-*`. It never touches the normal database or a real calendar. Generated sources are synthetic. Backend tests use temporary directories and MockCalendarProvider only.

The benchmark contains 68 fixed ground-truth cases anchored to 3 September 2026 at 10:00 Asia/Karachi. Passing this authored regression set is not an accuracy estimate for arbitrary documents. Results are in `validation/temporal-benchmark.json`.

## Browser acceptance

Two browser scenarios cover dashboard, inbox, upcoming, calendar, sources, tags, rules, completed, audit and settings; direct capture; evidence and date explanation; approve; mock sync; edit and update; completion; PDF/DOCX/VTT/chat/EML uploads; custom tag creation; rule creation; conflict review; and synchronized event deletion choices.

Layouts are checked at 1920×1080, 1440×900, 1366×768, 1024×768 and 390×844. Tests assert no horizontal document overflow, no uncaught frontend errors and no required asset failures in the primary scenario. Screenshots contain synthetic data only.

## Outlook status

Classic Outlook's COM registration was detected and pywin32 installed. The initial read-only COM probe did not return promptly. A subsequent probe through the implemented subprocess boundary timed out after 20 seconds. No real appointment was created, edited or deleted. This is **not** successful live integration validation.

`scripts/test_outlook_calendar.py` provides a separate manual read/create/delete check with explicit CREATE and DELETE prompts. Live approval is required before the write portion. Regular tests only verify recurrence mappings and mock behavior.

## Known limits

- Deterministic English rules cover the benchmarked patterns. Unrestricted natural-language understanding, multilingual semantics and implicit AM/PM are outside validated scope.
- AI semantics, OCR, Google Calendar, CalDAV, automatic high-confidence synchronization, system toasts and Windows startup are not shipped. AI-disabled mode is the only execution mode.
- Outlook common recurrence rules have COM mappings, but live timezone behavior needs validation. Recurring Outlook reconciliation is explicitly blocked rather than replacing the local RRULE with incomplete provider data. One native Outlook reminder is supported; other reminders belong to the running app.
- In-app reminders require the process to run. Extended downtime does not trigger a full historical reminder backlog.
- Recurrence conflict detection uses a 90-day horizon. Calendar display requests are limited to 400 days. Public holidays and travel times are not inferred.
- Source viewing preserves extracted text and segment/page references, not original PDF rendering. Original binaries are not retained. Scanned PDFs report that OCR is needed.
- Same-filename sources are possible versions. Missing events are reported, never silently cancelled. Differently named versions need manual review.
- Persistence uses an Alembic-managed SQLAlchemy JSON record store instead of the suggested fully normalized table list. Multi-record workflows are serialized within one process, not distributed transactions with a calendar.
- Trash remains recoverable indefinitely; the retention preference does not run an automatic permanent purge.
- Rules show potential conflicting assignments; project timelines and descriptive extraction analytics are available. Calendar drag-to-reschedule is not implemented.
- MSG has dependency-backed parsing but no validated real MSG fixture. Generic HTML retains text, not every vendor's message metadata.
- Profile changes apply to future extraction; existing reminders are not silently rewritten.

These limits must not be represented as completed acceptance criteria.
