import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.db import Store, scoped_account

ORIGIN = "https://chronosync.example"
INVITE = "test-invitation-" + "x" * 40


@pytest.fixture
def cloud(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONOSYNC_MODE", "cloud")
    monkeypatch.setenv("CHRONOSYNC_PUBLIC_URL", ORIGIN)
    monkeypatch.setenv("CHRONOSYNC_INVITE_CODE", INVITE)
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        yield app, client


def register(client, username):
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "a-long-private-password",
            "invite_code": INVITE,
        },
    )


def test_cloud_isolation_and_sessions(cloud):
    app, client = cloud
    assert client.get("/api/workspace").status_code == 401
    assert (
        client.post(
            "/api/auth/register",
            json={
                "username": "bad",
                "password": "a-long-private-password",
                "invite_code": "wrong",
            },
        ).status_code
        == 403
    )
    response = register(client, "alice")
    assert response.status_code == 200
    assert (
        "HttpOnly" in response.headers["set-cookie"]
        and "Secure" in response.headers["set-cookie"]
    )
    alice_cookie = client.cookies.get("chronosync_session")
    event = client.post(
        "/api/events",
        json={
            "title": "Alice private document",
            "start": "2026-10-01T09:00:00+05:00",
            "end": "2026-10-01T10:00:00+05:00",
        },
    ).json()
    assert "id" in event
    client.put("/api/settings", json={"timezone": "Europe/London"})
    response = register(client, "bob")
    assert response.status_code == 200
    workspace = client.get("/api/workspace").json()
    assert workspace["events"] == []
    assert workspace["settings"]["timezone"] == "Asia/Karachi"
    assert (
        client.put("/api/events/" + event["id"], json={"title": "stolen"}).status_code
        == 404
    )
    assert (
        client.post(
            "/api/events/" + event["id"] + "/action", json={"action": "delete"}
        ).status_code
        == 404
    )
    assert (
        client.get("/api/workspace", headers={"host": "evil.example"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/events",
            json={"title": "CSRF"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/events", json={"title": "CSRF"}, headers={"Origin": ""}
        ).status_code
        == 403
    )
    bob_cookie = client.cookies.get("chronosync_session")
    assert client.post("/api/auth/logout").status_code == 200
    client.cookies.set("chronosync_session", bob_cookie)
    assert client.get("/api/workspace").status_code == 401
    client.cookies.clear()
    client.cookies.set("chronosync_session", alice_cookie)
    assert (
        client.get("/api/workspace").json()["events"][0]["title"]
        == "Alice private document"
    )
    assert (
        client.post(
            "/api/auth/password",
            json={
                "username": "alice",
                "password": "a-long-private-password",
                "new_password": "my-new-long-password",
            },
        ).status_code
        == 200
    )
    client.cookies.clear()
    client.cookies.set("chronosync_session", alice_cookie)
    assert client.get("/api/workspace").status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "my-new-long-password"},
        ).status_code
        == 200
    )


def test_three_accounts_only_and_rate_limit(cloud):
    _, client = cloud
    for username in ["alice", "bob", "carol"]:
        assert register(client, username).status_code == 200
    assert register(client, "david").status_code == 409
    for _ in range(19):
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "alice", "password": "incorrect-long-password"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "incorrect-long-password"},
        ).status_code
        == 429
    )


def test_record_id_collision_and_parallel_context(tmp_path):
    store = Store(tmp_path)
    store.migrate()
    store.put("settings", {"id": "settings", "private": "legacy local"})

    def work(owner):
        with scoped_account(owner):
            store.put("settings", {"id": "settings", "private": owner})
            return store.get("settings", "settings")["private"]

    with concurrent.futures.ThreadPoolExecutor() as pool:
        assert list(pool.map(work, ["alice", "bob"])) == ["alice", "bob"]
    assert store.get("settings", "settings")["private"] == "legacy local"


def test_cloud_requires_secure_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONOSYNC_MODE", "cloud")
    monkeypatch.delenv("CHRONOSYNC_PUBLIC_URL", raising=False)
    with pytest.raises(RuntimeError, match="HTTPS"):
        create_app(tmp_path)
