"""Private subprocess boundary for potentially blocking COM calls."""

import json
import sys
from backend.calendars import _OutlookCOMProvider

if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.read())
        provider = _OutlookCOMProvider()
        action = request["action"]
        if action == "list_events":
            result = provider.list_events()
        elif action == "get_event":
            result = provider.get_event(request["external_id"])
        elif action == "create_event":
            result = provider.create_event(request["event"])
        elif action == "update_event":
            result = provider.update_event(request["external_id"], request["event"])
        elif action == "delete_event":
            result = provider.delete_event(request["external_id"])
        else:
            raise ValueError("Unknown Outlook operation")
        print(json.dumps({"result": result}))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
