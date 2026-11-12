"""Pembantu waktu: database menyimpan UTC, tampilan memakai zona waktu aplikasi (WIB)."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..config import settings


def sekarang_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware_utc(dt: datetime) -> datetime:
    """SQLite mengembalikan waktu tanpa zona; anggap itu UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_wib(dt: datetime) -> str:
    """Contoh: 2026-10-13T08:00:00+07:00 (browser tetap menampilkan jam yang sama di zona mana pun)."""
    return aware_utc(dt).astimezone(ZoneInfo(settings.timezone)).isoformat(timespec="seconds")


# ---------------- batas hari menurut zona waktu aplikasi (WIB) ----------------
from datetime import date, time, timedelta  # noqa: E402


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def hari_ini(sekarang: datetime | None = None) -> date:
    """Tanggal hari ini menurut WIB (sekarang bisa disuntikkan untuk pengujian)."""
    return (sekarang or sekarang_utc()).astimezone(_tz()).date()


def awal_hari_utc(d: date) -> datetime:
    """Pukul 00:00:00 WIB pada tanggal d, dalam UTC."""
    return datetime.combine(d, time.min, tzinfo=_tz()).astimezone(timezone.utc)


def akhir_hari_utc(d: date) -> datetime:
    """Pukul 23:59:59 WIB pada tanggal d, dalam UTC (batas atas yang ikut dihitung)."""
    return datetime.combine(d, time(23, 59, 59), tzinfo=_tz()).astimezone(timezone.utc)
