# Privacy

## Local storage

Original uploaded binaries are read locally but not retained. Extracted text, source metadata, event evidence, notes, audit history and mock calendar entries live in the local SQLite store. The default directory is ignored `data/`; CHRONOSYNC_DATA_DIR can relocate it. SQLite is not encrypted at rest; use OS disk encryption and normal file permissions if required.

## Network behavior

Local mode binds to 127.0.0.1 and retains single-user behavior. Cloud mode binds to the hosting interface, requires HTTPS, persistent PostgreSQL and invitation-only authentication, and isolates records by account. It rejects unauthenticated private API requests and cross-origin writes. Never expose local mode through a public proxy. See [hosted account security](MOBILE_HOSTING.md).

No external AI calls are implemented. In local mode processing occurs on the laptop. In cloud mode documents are uploaded to the hosted Python server; extracted text and calendar records persist in the hosted PostgreSQL database under the signed-in account. The UI distinguishes these modes. There are no remote fonts, tracking pixels or analytics services. Clipboard use is explicit paste only. Desktop Outlook is disabled in cloud mode.

## Credentials

No API keys or OAuth tokens are needed for default operation. Outlook profile credentials are managed by Outlook. Never add credentials to the repository. `.gitignore` excludes .env files, tokens, credentials, databases, uploaded files and exports. Only `.env.example` is tracked.

## Deletion and retention

Event deletion moves the record to recoverable Trash. Calendar-copy deletion is a separate explicit choice. There is currently no background permanent-trash purge.

Deleting source text removes stored source segments and linked source-evidence references. Event descriptions/notes and relevant edit history can retain user-visible text; source deletion is not a complete personal-data erasure mechanism. To erase all local data, stop the app and deliberately remove its selected data directory after exporting anything needed. ChronoSync never performs that destructive operation automatically.

## Exports and public repository

ICS, CSV, JSON and Excel exports can contain private event text. Settings backup contains only tags, rules, reminder profiles and event types, not credentials. Export paths are controlled by the user's browser and are not automatically added to Git. Formula-leading CSV/Excel cells are escaped.

All checked-in screenshots and generated demo definitions use fictional data. Tests use isolated databases and never write to real calendars. See [validation](VALIDATION.md) for the limits of the current checks.
