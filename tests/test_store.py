from backend.db import Store


def test_migration_and_persistence(tmp_path):
    s = Store(tmp_path)
    s.migrate()
    item = s.put("event", {"title": "Synthetic event"})
    s.migrate()
    assert Store(tmp_path).get("event", item["id"])["title"] == "Synthetic event"
