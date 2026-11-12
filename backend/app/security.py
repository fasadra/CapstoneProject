"""Sandi (argon2) dan token sesi (cookie bertanda tangan)."""
import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import settings

_hasher = PasswordHasher()
# Hash palsu untuk menyamakan waktu respons saat email tidak terdaftar (mencegah tebak-tebakan email).
_DUMMY_HASH = _hasher.hash("kata-sandi-palsu-untuk-penyamaan-waktu")

_CONTOH_KUNCI = {"ganti-di-env", "ganti-dengan-nilai-acak", ""}


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerificationError, InvalidHashError):
        return False


def verify_dummy(plain: str) -> None:
    verify_password(plain, _DUMMY_HASH)


# ---------- Token sesi ----------
# Isi token: id pengguna + sidik jari singkat dari hash sandi. Begitu sandi diganti, token lama
# otomatis tidak berlaku lagi (sesi di perangkat lain keluar sendiri).

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="freshsense-session")


def _fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def make_session_token(user_id: int, password_hash: str) -> str:
    return _serializer().dumps({"uid": user_id, "pv": _fingerprint(password_hash)})


def read_session_token(token: str) -> tuple[int, str] | None:
    """Kembalikan (user_id, sidik_jari) bila token sah dan belum kedaluwarsa, selain itu None."""
    try:
        data = _serializer().loads(token, max_age=settings.session_hours * 3600)
        return int(data["uid"]), str(data["pv"])
    except (BadSignature, KeyError, TypeError, ValueError):
        return None   # SignatureExpired adalah turunan BadSignature


def fingerprint_matches(fp: str, password_hash: str) -> bool:
    return fp == _fingerprint(password_hash)


def secret_is_weak() -> bool:
    return settings.secret_key in _CONTOH_KUNCI or len(settings.secret_key) < 32
