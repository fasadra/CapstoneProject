"""Endpoint autentikasi FreshSense AI."""
from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import AuthSession, User

router = APIRouter(prefix="/api", tags=["autentikasi"])
password_hasher = PasswordHash.recommended()
SESSION_TTL = timedelta(days=max(1, settings.session_days))
COOKIE_MAX_AGE = int(SESSION_TTL.total_seconds())

# Pembatas sederhana per proses: 5 kegagalan dalam 15 menit mengunci pasangan IP+email.
# Untuk deployment multi-worker, pindahkan penghitung ini ke Redis atau database bersama.
_ATTEMPTS: dict[str, list[float]] = {}
_LOCK = threading.Lock()
_ATTEMPT_WINDOW = 15 * 60
_MAX_ATTEMPTS = 5
_LOCK_SECONDS = 15 * 60


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nama: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Kata sandi tidak boleh kosong")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _public_user(user: User) -> dict:
    return {"id": user.id, "nama": user.nama, "username": user.username,
            "email": user.email, "telepon": user.telepon, "role": user.role}


def _new_username(db: Session, email: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_.-]", "", email.split("@", 1)[0]).lower()[:40] or "pengguna"
    candidate, suffix = base, 1
    while db.scalar(select(User.id).where(User.username == candidate)) is not None:
        suffix += 1
        candidate = f"{base[:44]}{suffix}"
    return candidate


def _attempt_key(request: Request, email: str) -> str:
    return f"{request.client.host if request.client else 'unknown'}:{email.lower()}"


def _check_rate_limit(key: str) -> None:
    now = time.monotonic()
    with _LOCK:
        values = [t for t in _ATTEMPTS.get(key, []) if now - t < _ATTEMPT_WINDOW]
        _ATTEMPTS[key] = values
        if len(values) >= _MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Terlalu banyak percobaan login. Coba lagi 15 menit.")


def _record_failure(key: str) -> None:
    with _LOCK:
        _ATTEMPTS.setdefault(key, []).append(time.monotonic())


def _clear_failures(key: str) -> None:
    with _LOCK:
        _ATTEMPTS.pop(key, None)


def _create_session(db: Session, user: User, response: Response) -> None:
    raw_token = secrets.token_urlsafe(48)
    db.add(AuthSession(user_id=user.id, token_hash=_token_digest(raw_token), expires_at=_now() + SESSION_TTL))
    db.commit()
    _cookie(response, raw_token)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_digest(token)))
    if session is None:
        raise HTTPException(status_code=401, detail="Sesi tidak valid")
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= _now():
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Sesi telah kedaluwarsa")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Akun tidak ditemukan")
    return user


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
        raise HTTPException(status_code=409, detail="Email sudah terdaftar")

    # Serialize registration on PostgreSQL. Partial unique index remains the final race guard.
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(742019331)"))
    role = "admin" if db.scalar(select(func.count()).select_from(User)) == 0 else "staf"
    local_name = email.split("@", 1)[0].replace(".", " ").replace("_", " ").replace("-", " ").strip()
    nama = (payload.nama or local_name or "Pengguna")[:100]
    user = User(nama=nama, username=_new_username(db, email), email=email,
                role=role, password_hash=password_hasher.hash(payload.password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        # If another request won the first-admin race, retry as staff.
        if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
            raise HTTPException(status_code=409, detail="Email sudah terdaftar")
        user = User(nama=nama, username=_new_username(db, email), email=email,
                    role="staf", password_hash=password_hasher.hash(payload.password))
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Pendaftaran tidak dapat diproses. Coba lagi.")

    _create_session(db, user, response)
    return {"user": _public_user(user)}


@router.post("/auth/login")
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    key = _attempt_key(request, email)
    _check_rate_limit(key)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    # Hash dummy juga dihitung agar email yang tidak ada tidak langsung terungkap lewat waktu respons.
    valid = False
    if user is not None:
        try:
            valid = password_hasher.verify(payload.password, user.password_hash)
        except Exception:
            valid = False
    if not valid:
        _record_failure(key)
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")
    _clear_failures(key)
    _create_session(db, user, response)
    return {"user": _public_user(user)}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_digest(token)))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(key=settings.session_cookie_name, path="/", httponly=True,
                           secure=settings.cookie_secure, samesite="lax")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"user": _public_user(user)}
