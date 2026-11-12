"""Akun: daftar, masuk, keluar, profil, ganti sandi.

POST /api/auth/register   POST /api/auth/login   POST /api/auth/logout
GET  /api/me              GET/PUT /api/profil    POST /api/profil/sandi
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import User
from ..ratelimit import limiter
from ..schemas import LoginIn, ProfilIn, RegisterIn, SandiIn, UserOut
from ..security import hash_password, make_session_token, verify_dummy, verify_password

router = APIRouter(prefix="/api", tags=["akun"])

ROLE_LABEL = {"admin": "Admin", "staf": "Staf"}


def _out(user: User) -> UserOut:
    return UserOut(
        nama=user.nama, username=user.username, email=user.email,
        telepon=user.telepon or "", role=ROLE_LABEL.get(user.role, user.role),
    )


def _set_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=make_session_token(user.id, user.password_hash),
        max_age=settings.session_hours * 3600,
        httponly=True, samesite="lax", secure=settings.cookie_secure, path="/",
    )


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _username_ada(db: Session, username: str, kecuali_id: int | None = None) -> bool:
    q = select(User.id).where(func.lower(User.username) == username.lower())
    if kecuali_id is not None:
        q = q.where(User.id != kecuali_id)
    return db.scalar(q) is not None


def _email_ada(db: Session, email: str, kecuali_id: int | None = None) -> bool:
    q = select(User.id).where(User.email == email)
    if kecuali_id is not None:
        q = q.where(User.id != kecuali_id)
    return db.scalar(q) is not None


def buat_username(db: Session, email: str) -> str:
    """Username awal dari bagian depan email: hanya huruf/angka/titik/garis bawah, 3-20 karakter, unik."""
    dasar = re.sub(r"[^A-Za-z0-9_.]", "", email.split("@")[0])[:20]
    if len(dasar) < 3:
        dasar = (dasar + "user")[:20]
    calon, n = dasar, 1
    while _username_ada(db, calon):
        n += 1
        akhiran = str(n)
        calon = dasar[: 20 - len(akhiran)] + akhiran
    return calon


# ---------------------------------------------------------------- daftar / masuk / keluar

@router.post("/auth/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    # Akun PERTAMA menjadi admin, selanjutnya staf. Di PostgreSQL dikunci agar dua pendaftaran
    # bersamaan tidak sama-sama menjadi admin.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7301)"))
    if _email_ada(db, data.email):
        raise HTTPException(status_code=409, detail="Email sudah terdaftar")

    role = "admin" if db.scalar(select(func.count(User.id))) == 0 else "staf"
    username = buat_username(db, data.email)
    user = User(
        nama=username.replace("_", " ").replace(".", " ").title()[:100],
        username=username, email=data.email, role=role,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email sudah terdaftar")
    return {"pesan": "Akun berhasil dibuat", "role": ROLE_LABEL[role]}


@router.post("/auth/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    key = f"login|{_ip(request)}|{data.email}"
    tunggu = limiter.blocked_for(key)
    if tunggu:
        menit = max(1, round(tunggu / 60))
        raise HTTPException(
            status_code=429,
            detail=f"Terlalu banyak percobaan gagal. Coba lagi sekitar {menit} menit lagi.",
            headers={"Retry-After": str(tunggu)},
        )

    user = db.scalar(select(User).where(User.email == data.email))
    if user is None:
        verify_dummy(data.password)
        ok = False
    else:
        ok = verify_password(data.password, user.password_hash)
    if not ok:
        limiter.fail(key)
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")

    limiter.reset(key)
    _set_cookie(response, user)
    response.headers["Cache-Control"] = "no-store"
    return _out(user)


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(settings.cookie_name, path="/", httponly=True, samesite="lax",
                           secure=settings.cookie_secure)
    return {"ok": True}


# ---------------------------------------------------------------- profil

@router.get("/me", response_model=UserOut)
def me(response: Response, user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return _out(user)


@router.get("/profil", response_model=UserOut)
def get_profil(response: Response, user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return _out(user)


@router.put("/profil", response_model=UserOut)
def update_profil(data: ProfilIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Role tidak bisa diubah dari sini."""
    if _email_ada(db, data.email, kecuali_id=user.id):
        raise HTTPException(status_code=409, detail="Email sudah dipakai akun lain")
    if _username_ada(db, data.username, kecuali_id=user.id):
        raise HTTPException(status_code=409, detail="Username sudah dipakai akun lain")
    user.nama, user.username = data.nama, data.username
    user.email, user.telepon = data.email, data.telepon
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email atau username sudah dipakai akun lain")
    return _out(user)


@router.post("/profil/sandi")
def ubah_sandi(
    data: SandiIn, response: Response,
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    key = f"sandi|{user.id}"
    tunggu = limiter.blocked_for(key)
    if tunggu:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan gagal. Coba lagi beberapa menit lagi.",
            headers={"Retry-After": str(tunggu)},
        )
    # Status 400 (bukan 401) supaya frontend tidak mengira sesi berakhir.
    if not verify_password(data.lama, user.password_hash):
        limiter.fail(key)
        raise HTTPException(status_code=400, detail="Kata sandi lama salah")
    if data.baru == data.lama:
        raise HTTPException(status_code=400, detail="Kata sandi baru harus berbeda dari yang lama")

    user.password_hash = hash_password(data.baru)
    db.commit()
    limiter.reset(key)
    _set_cookie(response, user)    # sesi ini tetap sah; sesi lain (token lama) otomatis gugur
    return {"ok": True}
