"""Destructive-free smoke test against a fresh, disposable LOCAL PostgreSQL test DB."""
import json
import os
import secrets
import sys
from pathlib import Path
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app import create_app

url = os.environ["CHRONOSYNC_TEST_DATABASE_URL"]
parsed = make_url(url)
if parsed.host not in {"localhost", "127.0.0.1", "host.docker.internal"} or parsed.database != "chronosync_test":
    raise SystemExit("Only a disposable local chronosync_test database is allowed")
os.environ.update(DATABASE_URL=url, CHRONOSYNC_MODE="cloud",
    CHRONOSYNC_PUBLIC_URL="https://chronosync.example", CHRONOSYNC_INVITE_CODE=secrets.token_urlsafe(32))
headers = {"Origin": "https://chronosync.example"}
password = secrets.token_urlsafe(24)

def client(app):
    return TestClient(app, base_url=headers["Origin"], headers=headers)

def register(c, name):
    response = c.post("/api/auth/register", json={"username": name, "password": password,
        "invite_code": os.environ["CHRONOSYNC_INVITE_CODE"]})
    assert response.status_code == 200, response.status_code

app = create_app()
assert app.state.store.engine.dialect.name == "postgresql"
with client(app) as first:
    register(first, "cloud_smoke_alice")
    cookie = first.cookies.get("chronosync_session")
    source = first.post("/api/sources/import", files=[("files", ("private.txt", b"Project meeting on 12 October 2026 at 09:00.", "text/plain"))])
    assert source.status_code == 200, source.status_code
    workspace = first.get("/api/workspace").json()
    source_id = workspace["sources"][0]["id"]
    event = first.post("/api/events", json={"title": "Private test event", "start": "2026-10-12T09:00:00+05:00", "end": "2026-10-12T10:00:00+05:00"}).json()
    assert "id" in event
    assert first.put("/api/settings", json={"timezone": "Europe/London"}).status_code == 200
    # Independent request cookies, one running application lifespan.
    second = client(app)
    register(second, "cloud_smoke_bob")
    other = second.get("/api/workspace").json()
    assert other["events"] == [] and other["sources"] == []
    assert other["settings"]["timezone"] == "Asia/Karachi"
    assert second.get("/api/sources/" + source_id).status_code == 404
    assert second.delete("/api/sources/" + source_id).status_code == 404
    assert second.get("/api/export/json").json() == []
    second.close()
app.state.store.engine.dispose()
with client(create_app()) as restarted:
    restarted.cookies.set("chronosync_session", cookie)
    workspace = restarted.get("/api/workspace").json()
    assert workspace["settings"]["timezone"] == "Europe/London"
    assert any(e["id"] == event["id"] for e in workspace["events"])
    assert any(s["id"] == source_id for s in workspace["sources"])
report = {"postgresql": "passed", "account_isolation": "passed", "sources_and_exports_isolated": "passed", "restart_persistence": "passed", "live_hosted_deployment": "not_run"}
Path("docs/validation/cloud-smoke.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
