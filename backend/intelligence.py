import re
from difflib import SequenceMatcher
from datetime import timedelta
from backend.temporal import resolve, aware, DATE_PATTERN

TYPE_RULES = [
    ("Exam", r"\bexam|examination"),
    ("Interview", r"\binterview"),
    ("Presentation", r"\bpresentation"),
    ("Payment", r"\bpayment|invoice|bill due"),
    ("Renewal", r"\brenew|expir|valid until|subscription ends"),
    ("Follow-Up", r"follow.up|check back|revisit|contact again"),
    ("Travel", r"\bflight|train|departure|arrival|boarding|check.in"),
    ("Birthday", r"\bbirthday"),
    ("Appointment", r"\bappointment|consultation"),
    (
        "Deadline",
        r"\bdue|deadline|submit|no later than|must complete|respond by|rsvp by",
    ),
    ("Meeting", r"\bmeeting|conference|session|lecture|review"),
    ("Call", r"\bcall"),
    ("Reservation", r"\breservation"),
    ("Delivery", r"\bdelivery"),
    ("Maintenance", r"\bmaintenance"),
]


def key(title):
    return re.sub(r"\W+", " ", title.lower()).strip()


def similar(a, b):
    ka, kb = key(a), key(b)
    return SequenceMatcher(None, ka, kb).ratio()


def classify(text):
    return next(
        (kind for kind, pattern in TYPE_RULES if re.search(pattern, text, re.I)), "Task"
    )


def title_for(text):
    title = re.split(
        r"\b(?:on|at|by|tomorrow|today|next|every|moved|rescheduled|has been cancelled|is cancelled|is not|no longer|renews)\b",
        text,
        maxsplit=1,
        flags=re.I,
    )[0]
    match = DATE_PATTERN.search(title)
    if match:
        title = title[: match.start()]
    title = re.sub(
        r"^(?:please|reminder:?|the|your|actually,?)\s+", "", title.strip(), flags=re.I
    )
    title = re.sub(
        r"\s+(?:is|will be held|will be|has|from|for|no later than|due)$",
        "",
        title,
        flags=re.I,
    ).strip(" :,-.")
    return title[:1].upper() + title[1:100] if title else "Commitment requiring review"


def importance_for(text, kind):
    if re.search(r"urgent|critical|penalty|mandatory", text, re.I):
        return "CRITICAL"
    if kind in {"Exam", "Interview", "Deadline", "Payment", "Presentation"}:
        return "HIGH"
    if re.search(r"optional|social", text, re.I):
        return "LOW"
    return "MEDIUM"


def extract(source, settings, existing, rules):
    candidates = []
    for segment in source["segments"]:
        text = segment["text"]
        # Keep correction sentences together so pronoun references retain their subject.
        chunks = (
            [text]
            if re.search(r"\bnot\b|no longer|make it", text, re.I)
            else re.split(
                r"(?<=[.!?])\s+|\n|;\s*|\s+and\s+(?=(?:the )?(?:exam|meeting|presentation|payment|interview|project deadline)\b)",
                text,
                flags=re.I,
            )
        )
        for evidence in chunks:
            if not evidence.strip():
                continue
            if re.match(
                r"^(?:document date|meeting date|transcript date|date):", evidence, re.I
            ):
                continue
            if re.search(
                r"\b(occurred|took place|was held|happened|met yesterday)\b",
                evidence,
                re.I,
            ):
                continue
            kind = classify(evidence)
            cancel = bool(
                re.search(
                    r"cancelled|canceled|called off|no longer happening|postponed indefinitely|won.t take place",
                    evidence,
                    re.I,
                )
            )
            changed = bool(
                re.search(
                    r"moved|rescheduled|postponed until|changed to|no longer|instead of|make it",
                    evidence,
                    re.I,
                )
            )
            if not (
                DATE_PATTERN.search(evidence)
                or cancel
                or changed
                or re.search(
                    r"next week|next month|around the|every|annually|business day|working day|days? before",
                    evidence,
                    re.I,
                )
            ):
                continue
            if re.search(r"\bnot\s+(?:on\s+)?\w+\.?$", evidence, re.I) and not cancel:
                continue
            reference = (
                segment.get("timestamp")
                or source.get("metadata", {}).get("document_date")
                or source.get("source_timestamp")
                or source["created_at"]
            )
            resolution = resolve(evidence, reference, settings)
            reference_kind = (
                segment.get("reference_kind")
                if segment.get("timestamp")
                else (
                    "explicit document date"
                    if source.get("metadata", {}).get("document_date")
                    else (
                        "user-defined source date"
                        if source.get("source_timestamp")
                        else "import date fallback"
                    )
                )
            )
            resolution["reference_kind"] = reference_kind
            title = title_for(evidence)
            related = [
                e
                for e in existing + candidates
                if not e.get("deleted")
                and e.get("status") not in {"CANCELLED", "ARCHIVED", "COMPLETED"}
                and (
                    similar(e["title"], title) >= 0.55
                    or (kind == e["type"] and kind != "Task")
                )
            ]
            relation = re.search(
                r"(\d+|one|two|three|four|five|seven) days? before the (\w+)",
                evidence,
                re.I,
            )
            if relation:
                from backend.temporal import NUMS

                targets = [
                    e
                    for e in existing + candidates
                    if relation[2].lower() in e["title"].lower() and e.get("start")
                ]
                if len(targets) == 1:
                    count = (
                        int(relation[1]) if relation[1].isdigit() else NUMS[relation[1]]
                    )
                    dt = aware(targets[0]["start"], settings["timezone"]) - timedelta(
                        days=count
                    )
                    resolution = resolve(dt.isoformat()[:10], reference, settings)
                    resolution["explanation"].append(
                        "Derived " + str(count) + " days before " + targets[0]["title"]
                    )
                    resolution["depends_on"] = targets[0].get("id")
                else:
                    resolution["start"] = None
                    resolution["warnings"] = [
                        "Unable to resolve dependent event uniquely."
                    ]
            importance = importance_for(evidence, kind)
            tags = []
            for tag, pattern in [
                (
                    "University",
                    r"exam|lecture|assignment|university|course|presentation",
                ),
                ("Work", r"project|team|contract|interview"),
                ("Finance", r"payment|invoice|subscription"),
                ("Travel", r"flight|hotel|train"),
                ("Health", r"doctor|dentist|consultation"),
                ("Personal", r"birthday|family"),
            ]:
                if re.search(pattern, evidence, re.I):
                    tags.append(tag)
            people = []
            m = re.search(r"\bwith ([A-Z][a-z]+(?: and [A-Z][a-z]+)?)", evidence)
            if m:
                people = m[1].split(" and ")
            location = re.search(
                r"\b(?:Room\s+[A-Za-z0-9]+|Office\s+\d+|Zoom|Teams|Online)\b",
                evidence,
                re.I,
            )
            links = re.findall(r"https?://[^\s<>]+", evidence)
            warnings = resolution["warnings"]
            confidence = round(
                max(
                    0.1,
                    min(
                        0.98,
                        0.45
                        + (0.25 if resolution["start"] else 0)
                        + (0.12 if not resolution["time_unknown"] else 0)
                        + (0.08 if kind != "Task" else 0)
                        + (
                            0.06
                            if segment.get("timestamp")
                            or source.get("source_timestamp")
                            else 0
                        )
                        - (0.35 if warnings else 0),
                    ),
                ),
                2,
            )
            event = {
                "title": title,
                "description": evidence,
                "type": kind,
                "importance": importance,
                "tags": tags[:3],
                "people": people,
                "location": location[0] if location else "",
                "meeting_links": links,
                "organization": "",
                "notes": "",
                "status": "NEEDS_REVIEW" if warnings else "PROPOSED",
                "confidence": confidence,
                "confidence_label": "HIGH"
                if confidence >= 0.9
                else ("MEDIUM" if confidence >= 0.7 else "LOW"),
                "sync_state": "NOT_SYNCED",
                "sources": [
                    {
                        "source_id": source["id"],
                        "name": source["name"],
                        "evidence": evidence,
                        "segment": segment,
                    }
                ],
                "resolution": resolution,
                "start": resolution["start"],
                "end": resolution["end"],
                "all_day": resolution["all_day"],
                "timezone": settings["timezone"],
                "rrule": resolution["rrule"],
                "reminders": settings["reminder_profiles"][importance],
                "pinned": False,
                "deleted": False,
                "history": [],
                "related_ids": [],
                "projects": [],
            }
            for rule in sorted(rules, key=lambda r: r.get("priority", 0)):
                if not rule.get("enabled", True):
                    continue
                conditions = rule.get("conditions", {})
                if all(
                    (
                        str(v).lower()
                        in str(
                            source["name"]
                            if k == "source"
                            else (evidence if k == "contains" else event.get(k, ""))
                        ).lower()
                    )
                    for k, v in conditions.items()
                ):
                    for field, value in rule.get("actions", {}).items():
                        if field in {"importance", "reminders"}:
                            event[field] = value
                        elif field == "tags":
                            event["tags"] = list(dict.fromkeys(event["tags"] + value))
                    event.setdefault("applied_rules", []).append(rule["name"])
            if cancel or changed:
                event["change_kind"] = "CANCEL" if cancel else "RESCHEDULE"
                event["status"] = "NEEDS_REVIEW"
                event["related_ids"] = [e["id"] for e in related if e.get("id")]
                if len(related) != 1:
                    warnings.append("Related event could not be identified uniquely.")
            duplicates = [
                e
                for e in existing + candidates
                if not e.get("deleted")
                and e.get("start")
                and e["start"] == event["start"]
                and similar(e["title"], title) > 0.7
            ]
            if duplicates and not (cancel or changed):
                event["duplicate_ids"] = [e["id"] for e in duplicates if e.get("id")]
                event["status"] = "NEEDS_REVIEW"
            candidates.append(event)
    return candidates


def occurrences(event, start, end):
    if not event.get("start"):
        return []
    a = aware(event["start"], event["timezone"])
    b = aware(event.get("end") or event["start"], event["timezone"])
    duration = b - a
    if event.get("rrule"):
        from dateutil.rrule import rrulestr

        rule = rrulestr(event["rrule"], dtstart=a)
        return [
            (d, d + duration) for d in rule.between(start - duration, end, inc=True)
        ][:2000]
    return [(a, b)]


def conflicts(event, others, buffer=15):
    if not event.get("start") or event.get("all_day"):
        return []
    a = aware(event["start"], event["timezone"])
    end = (
        a + timedelta(days=90)
        if event.get("rrule")
        else aware(event["end"], event["timezone"])
    )
    found = []
    for other in others:
        if (
            other.get("id") == event.get("id")
            or not other.get("start")
            or other.get("all_day")
            or other.get("deleted")
            or other.get("status") in {"COMPLETED", "CANCELLED", "ARCHIVED"}
        ):
            continue
        severity = None
        for s, e in occurrences(event, a, end):
            for os, oe in occurrences(
                other, a - timedelta(minutes=buffer), end + timedelta(minutes=buffer)
            ):
                if s < oe and os < e:
                    severity = (
                        "FULL_OVERLAP"
                        if (s <= os and e >= oe) or (os <= s and oe >= e)
                        else "PARTIAL_OVERLAP"
                    )
                elif timedelta(0) <= os - e < timedelta(minutes=buffer) or timedelta(
                    0
                ) <= s - oe < timedelta(minutes=buffer):
                    severity = severity or "BACK_TO_BACK"
        if severity:
            found.append(
                {
                    "id": other["id"],
                    "title": other["title"],
                    "severity": severity,
                    "start": other["start"],
                    "end": other.get("end"),
                }
            )
    return found
