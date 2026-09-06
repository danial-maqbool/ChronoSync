"""Small, invitation-only cloud workspace authentication (no email service)."""

import hashlib
import hmac
import os
import re
import secrets
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import String, Float, select, delete, func
from sqlalchemy.orm import Mapped, mapped_column, Session
from backend.db import Base, uid

COOKIE = "chronosync_session"


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)


class LoginSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String)
    expires: Mapped[float] = mapped_column(Float)


class Attempt(Base):
    __tablename__ = "auth_attempts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    at: Mapped[float] = mapped_column(Float)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    result = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
    ).hex()
    return salt + ":" + result


def password_matches(password, encoded):
    return hmac.compare_digest(password_hash(password, encoded.split(":")[0]), encoded)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Authentication:
    def __init__(self, store, lock, testing=False):
        self.store, self.lock = store, lock
        self.cloud = os.environ.get("CHRONOSYNC_MODE", "local") == "cloud"
        self.origin = (
            os.environ.get("CHRONOSYNC_PUBLIC_URL")
            or os.environ.get("RENDER_EXTERNAL_URL", "")
        ).rstrip("/")
        self.invite = os.environ.get("CHRONOSYNC_INVITE_CODE", "")
        if self.cloud:
            parsed = urlsplit(self.origin)
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
            ):
                raise RuntimeError(
                    "Cloud mode requires CHRONOSYNC_PUBLIC_URL with an HTTPS origin"
                )
            if len(self.invite) < 32:
                raise RuntimeError(
                    "Cloud mode requires a random CHRONOSYNC_INVITE_CODE of at least 32 characters"
                )
            if not testing and store.engine.dialect.name != "postgresql":
                raise RuntimeError(
                    "Cloud mode requires a persistent PostgreSQL DATABASE_URL"
                )

    def user(self, request):
        token = request.cookies.get(COOKIE, "")
        if not token or len(token) > 200:
            return None
        with Session(self.store.engine) as session:
            login = session.get(LoginSession, digest(token))
            if not login or login.expires <= time.time():
                return None
            account = session.get(Account, login.account_id)
            return {"id": account.id, "username": account.username} if account else None

    def account_ids(self):
        with Session(self.store.engine) as session:
            return list(session.scalars(select(Account.id)))

    def install(self, app, initialize):
        @app.get("/api/auth/status")
        def status(request: Request):
            return {
                "cloud": self.cloud,
                "user": self.user(request) if self.cloud else None,
            }

        @app.post("/api/auth/{action}")
        async def authenticate(action: str, request: Request):
            if not self.cloud:
                raise HTTPException(404, "Accounts are available in cloud mode")
            if action == "logout":
                with Session(self.store.engine) as s, s.begin():
                    s.execute(
                        delete(LoginSession).where(
                            LoginSession.id == digest(request.cookies.get(COOKIE, ""))
                        )
                    )
                response = JSONResponse({"ok": True})
                response.delete_cookie(
                    COOKIE, secure=True, httponly=True, samesite="strict"
                )
                return response
            if action not in {"login", "register", "password"}:
                raise HTTPException(404, "Unknown account action")
            raw = b""
            async for chunk in request.stream():
                raw += chunk
                if len(raw) > 4096:
                    raise HTTPException(413, "Account request too large")
            import json

            try:
                body = json.loads(raw)
                username = str(body.get("username", "")).strip().lower()
                password = str(body.get("password", ""))
                if not 12 <= len(password) <= 128 or not re.fullmatch(
                    r"[a-z0-9_.-]{3,40}", username
                ):
                    raise ValueError()
            except (ValueError, AttributeError):
                raise HTTPException(
                    400,
                    "Use a username of 3–40 letters/numbers and a password of 12–128 characters",
                )
            with self.lock:
                # Persist a bounded, service-wide brute-force budget across restarts.
                with Session(self.store.engine) as s, s.begin():
                    s.execute(delete(Attempt).where(Attempt.at < time.time() - 900))
                    if s.scalar(select(func.count()).select_from(Attempt)) >= 20:
                        raise HTTPException(
                            429, "Too many account attempts. Try again in 15 minutes."
                        )
                    attempt_id = uid()
                    s.add(Attempt(id=attempt_id, at=time.time()))
                with Session(self.store.engine) as s, s.begin():
                    account = s.scalar(
                        select(Account).where(Account.username == username)
                    )
                    if action == "register":
                        supplied = str(body.get("invite_code", ""))
                        if not hmac.compare_digest(
                            digest(supplied), digest(self.invite)
                        ):
                            raise HTTPException(403, "Invalid invitation code")
                        if (
                            account
                            or s.scalar(select(func.count()).select_from(Account)) >= 3
                        ):
                            raise HTTPException(
                                409,
                                "Username unavailable or all three account places are taken",
                            )
                        account = Account(
                            id=uid(),
                            username=username,
                            password_hash=password_hash(password),
                        )
                        s.add(account)
                        s.flush()
                    elif (
                        not password_matches(
                            password,
                            account.password_hash
                            if account
                            else password_hash(
                                "unavailable-account-password", "00" * 16
                            ),
                        )
                        or not account
                    ):
                        raise HTTPException(401, "Incorrect username or password")
                    if action == "password":
                        current = self.user(request)
                        if not current or current["id"] != account.id:
                            raise HTTPException(401, "Sign in to change your password")
                        new_password = str(body.get("new_password", ""))
                        if not 12 <= len(new_password) <= 128:
                            raise HTTPException(
                                400, "New password must have 12–128 characters"
                            )
                        account.password_hash = password_hash(new_password)
                        s.execute(
                            delete(LoginSession).where(
                                LoginSession.account_id == account.id
                            )
                        )
                    token = secrets.token_urlsafe(32)
                    s.execute(
                        delete(LoginSession).where(LoginSession.expires < time.time())
                    )
                    s.add(
                        LoginSession(
                            id=digest(token),
                            account_id=account.id,
                            expires=time.time() + 30 * 86400,
                        )
                    )
                    s.execute(delete(Attempt).where(Attempt.id == attempt_id))
                    user = {"id": account.id, "username": account.username}
                if action == "register":
                    initialize(user["id"])
            response = JSONResponse({"user": user})
            response.set_cookie(
                COOKIE,
                token,
                max_age=30 * 86400,
                secure=True,
                httponly=True,
                samesite="strict",
            )
            return response
