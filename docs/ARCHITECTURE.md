# Architecture

## Runtime

`python run.py` selects the local virtual environment and serves the built React app and FastAPI API at loopback port 8765. `CHRONOSYNC_DATA_DIR` selects a data directory; `CHRONOSYNC_PORT` selects the listening port. Environment variables must be set in the process; `.env.example` is a template, not an automatically loaded secret file.

The FastAPI lifespan applies migrations and starts the reminder task. Shutdown cancels the task. API writes reject cross-site requests and unrecognized Host headers. This is a single-user local application, not an authenticated multi-user internet service.

## Modules

| Module | Responsibility |
|---|---|
| `ingestion.py` | Format-specific local parsing into evidence segments |
| `temporal.py` | Deterministic dates, clocks, zones, ranges, recurrence, warnings |
| `intelligence.py` | Context/type/title/importance, rules, duplicate/change proposals, conflicts |
| `schemas.py` | Pydantic validation of events, tags, rules and actions |
| `db.py` | SQLAlchemy persistence and record categories |
| `calendars.py` | Provider interface, Mock, Outlook COM, ICS serialization |
| `app.py` | API operations, workflow gates, reminders, exports and static hosting |
| `frontend/src/main.tsx` | Workspace views, forms, review drawer and navigation |
| `frontend/src/projects.tsx` | Project creation and event timelines |

## Persistence

Alembic manages an indexed `records` table with `id`, `kind` and JSON `body`. Record categories include event, source, tag, rule, project, view, notification, audit, settings and mock_calendar. JSON allows event-specific provenance and inference details while keeping migrations explicit. The record schema is intentionally simpler than the normalized table list in the initial brief.

Application event history records before/after snapshots for edits and reschedules. Audit records provide workspace chronology. The in-process lock serializes multi-step event workflows. Individual records are committed in SQLAlchemy transactions. An external calendar and SQLite do not share an atomic transaction; failure states remain visible.

## Extraction flow

1. Validate batch/file bounds and hash source bytes.
2. Check prior imports; keep duplicates reviewable and avoid repeat extraction by default.
3. Parse source into exact text segments with available sender/page/cue metadata.
4. Resolve reference timestamp precedence and deterministic dates.
5. Apply context classification, importance, tags, rules and confidence.
6. Attach exact duplicate evidence; propose uncertain duplicates, reschedules or cancellations.
7. Persist candidates and audit history. No calendar call occurs during extraction.
8. User approval gates provider writes. Conflict and reconciliation checks run before sync.

## Frontend

React and TypeScript provide view state, accessible form labels, keyboard-aware navigation and focus-trapped dialogs. Tailwind is compiled through Vite; local CSS defines the visual design. Lucide icons ship in the bundle. There are no remote fonts or runtime image dependencies. The server returns the built index for app routes and explicit 404s for unknown API paths.

## Tests

Backend tests use temporary data stores. Browser tests launch a fresh port-8766 server and generated synthetic files. Unit tests, the 68-case benchmark and Playwright are separate runners. See [validation](VALIDATION.md).

FastAPI lifecycle follows the [official lifespan API](https://fastapi.tiangolo.com/advanced/events/).
