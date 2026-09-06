# Android and free private hosting

The hosted edition preserves the Python application, adds invitation-only accounts
(maximum three), and keeps every account's records separate. Local mode still uses
the existing SQLite workspace. Hosted mode requires PostgreSQL; it refuses to start
with ephemeral SQLite storage or without HTTPS and an invitation secret.

## Free service setup

Use **Render Free** for the Docker web service and **Neon Free** for PostgreSQL.
Do not add payment methods or enable paid plans. These are third-party free tiers,
not a promise of perpetual availability or unlimited storage. Check the provider
dashboards for current usage and limits. There is no paid AI or email dependency.

1. Sign in to [Neon](https://console.neon.tech), create a Free project, and copy its
   pooled PostgreSQL connection string with `sslmode=require`. Store it only in the
   Render secret field below, never in Git or screenshots.
2. Sign in to [Render](https://dashboard.render.com). Create a Blueprint from
   `https://github.com/danial-maqbool/ChronoSync`, using the repository's `render.yaml`.
3. Confirm the web service plan is **Free** and that no Render database or paid
   resource is being added. Set `DATABASE_URL` to the Neon connection string.
4. Render generates `CHRONOSYNC_INVITE_CODE`; keep it private. The first three
   people using this invitation can create accounts. Share it only with the two
   intended friends. Each person chooses a unique username and a password of at
   least 12 characters. No public, uninvited signup is allowed.
5. Deploy. The app uses Render's `RENDER_EXTERNAL_URL` automatically. If using a
   different host, set `CHRONOSYNC_PUBLIC_URL` to its exact HTTPS origin.
6. Open the service URL, create the first account, and verify uploads and event
   review. Check another account cannot see the first account's records.

Do not use Render's free PostgreSQL product for permanent data: its free databases
expire after 30 days. Render's free filesystem is ephemeral. Only PostgreSQL holds
the app's records in hosted mode. Existing laptop documents are not automatically
uploaded or assigned to a cloud account.

## Android installation

Install the signed `ChronoSync.apk` directly on the S25 Ultra. This avoids app-store
publishing requirements. Transfer the APK to the phone, open it, and allow that file
source to install this app when Android prompts. The app requires Android 11+.

On first launch, enter the deployed HTTPS website address, then sign in. Each friend
uses the same website address and their own credentials. The APK is an Android
WebView client for the hosted interface, with Android's document picker and download
manager. It is not an offline rewrite of the application. It does not request
contacts, SMS, camera, or broad storage permissions. Exported files go to Downloads.

The Server button changes the website address and clears account cookies when the
address changes. Only enter a trusted ChronoSync address. Server-side UI updates
appear automatically; Android client changes require a newer APK signed with the
same private signing key. The signing key stays outside Git in `.tools/android-signing`;
back it up securely before moving or deleting this checkout.

## What free hosting means

Render Free sleeps after 15 minutes without traffic and may need about a minute to
wake. Monthly resource limits can suspend access. The laptop can remain off, but
this is not guaranteed continuously running infrastructure. No artificial traffic
or keep-alive workaround is configured.

Server reminders do not run while the service sleeps. This APK does not yet schedule
native alarms or push notifications. Export approved events as ICS and import them
into a compatible phone calendar for its own reminder delivery; verify the imported
times and alarms on your device. Live desktop Outlook COM is intentionally unavailable
in cloud mode. Mock calendar entries are app testing records, not phone-calendar sync.

## Account security and operations

Passwords use salted scrypt. Random session tokens have only SHA-256 digests stored
in PostgreSQL; secure, HttpOnly, SameSite=Strict cookies expire after 30 days. Logout
revokes the current session; changing the password revokes previous sessions.
All API writes require the configured origin. A database-backed limit blocks login
attempts after 20 failures within 15 minutes across this small private service.
There is no email password-reset service; save passwords in a password manager.

Account IDs come from server-validated sessions, never request-provided ownership.
Database reads and writes filter by that account, including source evidence, settings,
audit history, exports, mock calendar records, and reminders. Legacy laptop records
remain in their local scope. Authentication and database credentials are not in the APK.

Use one application process, as configured by `run.py`. The invitation/account limit
and related event operations use a process lock; horizontal scaling is not supported
by this small free deployment. Periodically export each account's events and settings
and use the database provider's supported export tools for full database backups.

## Rebuilding the APK

Use JDK 17, Android SDK platform 35, and Gradle 8.9. From `android`, run `gradlew.bat
assembleRelease` (or `./gradlew assembleRelease`). Signing requires environment
variables `CHRONOSYNC_KEYSTORE` and `CHRONOSYNC_KEY_PASSWORD`; the key alias is
`chronosync`. Never commit the keystore or password. `assembleDebug` is for development
only. Release artifacts are ignored by Git and can be distributed separately.

## References

- [Render free-service limits](https://render.com/docs/free)
- [Render Blueprint configuration](https://render.com/docs/blueprint-spec)
- [Neon plans](https://neon.com/pricing)
- [Android WebView](https://developer.android.com/develop/ui/views/layout/webapps/webview)

Deployment status and device verification must be recorded separately after the
cloud accounts are connected. A local build does not prove a live deployment or
successful installation on a physical Samsung phone.
