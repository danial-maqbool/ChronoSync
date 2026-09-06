import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from contextvars import ContextVar
from contextlib import contextmanager
from sqlalchemy import create_engine, String, JSON, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

account_scope = ContextVar("account_scope", default="local")


@contextmanager
def scoped_account(account_id):
    token = account_scope.set(account_id)
    try:
        yield
    finally:
        account_scope.reset(token)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    body: Mapped[dict] = mapped_column(JSON)
    owner_id: Mapped[str] = mapped_column(String, index=True, default="local")


class Store:
    def __init__(self, directory=None):
        self.directory = Path(
            directory or os.environ.get("CHRONOSYNC_DATA_DIR", "data")
        ).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        url = os.environ.get("DATABASE_URL") if directory is None else None
        if url and url.startswith(("postgres://", "postgresql://")):
            url = "postgresql+psycopg://" + url.split("://", 1)[1]
        url = url or "sqlite:///" + (self.directory / "chronosync.db").as_posix()
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False}
            if url.startswith("sqlite")
            else {},
        )

    def migrate(self):
        from alembic.config import Config
        from alembic import command

        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        cfg.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
        )
        with self.engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")

    def all(self, kind):
        with Session(self.engine) as s:
            return [
                r.body
                for r in s.scalars(
                    select(Record).where(
                        Record.kind == kind, Record.owner_id == account_scope.get()
                    )
                )
            ]

    def get(self, kind, ident):
        with Session(self.engine) as s:
            r = s.get(Record, self.record_id(ident))
            return (
                r.body
                if r and r.kind == kind and r.owner_id == account_scope.get()
                else None
            )

    def record_id(self, ident):
        owner = account_scope.get()
        return ident if owner == "local" else owner + ":" + ident

    def put(self, kind, body):
        body = dict(body)
        body.setdefault("id", uid())
        body.setdefault("created_at", now())
        body["updated_at"] = now()
        with Session(self.engine) as s, s.begin():
            physical_id = self.record_id(body["id"])
            r = s.get(Record, physical_id)
            if r:
                if r.kind != kind or r.owner_id != account_scope.get():
                    raise ValueError("Record kind mismatch")
                r.body = body
            else:
                s.add(
                    Record(
                        id=physical_id,
                        kind=kind,
                        body=body,
                        owner_id=account_scope.get(),
                    )
                )
        return body

    def audit(self, action, event_id=None, detail=None):
        return self.put(
            "audit", {"action": action, "event_id": event_id, "detail": detail or {}}
        )


DEFAULTS = {
    "id": "settings",
    "timezone": "Asia/Karachi",
    "date_order": "DMY",
    "week_start": 0,
    "eod": None,
    "cob": None,
    "default_deadline_time": None,
    "duration": 60,
    "buffer": 15,
    "provider": "mock",
    "auto_sync": False,
    "ai_enabled": False,
    "trash_retention_days": 30,
    "event_types": [
        "Meeting",
        "Deadline",
        "Appointment",
        "Presentation",
        "Exam",
        "Assignment",
        "Interview",
        "Follow-Up",
        "Renewal",
        "Payment",
        "Travel",
        "Reservation",
        "Delivery",
        "Birthday",
        "Maintenance",
        "Submission",
        "Call",
        "Task",
        "Other",
    ],
    "reminder_profiles": {
        "CRITICAL": [10080, 4320, 1440, 120],
        "HIGH": [4320, 1440, 60],
        "MEDIUM": [1440, 60],
        "LOW": [60],
        "NONE": [],
    },
}
