"""Dashboard, analisis, laporan, notifikasi. Semua endpoint wajib login.

GET  /api/dashboard/summary           GET  /api/analisis?period=minggu|bulan
GET  /api/laporan?periode=minggu|bulan  atau  ?from=YYYY-MM-DD&to=YYYY-MM-DD
GET  /api/notifications               POST /api/notifications/{id}/baca    POST /api/notifications/baca-semua
"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import User
from ..schemas_dash import Analisis, Laporan, Notifikasi, Ringkasan
from ..schemas_stok import Ok
from ..services import analitik
from ..services.analitik import AnalitikError
from ..services.waktu import hari_ini

router = APIRouter(prefix="/api", tags=["dashboard"])


def _jalankan(fungsi, *args):
    try:
        return fungsi(*args)
    except AnalitikError as e:
        raise HTTPException(status_code=e.status, detail=e.pesan)


@router.get("/dashboard/summary", response_model=Ringkasan)
def summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return analitik.ringkasan(db)


@router.get("/analisis", response_model=Analisis)
def get_analisis(
    period: Literal["minggu", "bulan"] = "minggu",
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    return analitik.analisis(db, period)


@router.get("/laporan", response_model=Laporan)
def get_laporan(
    periode: Literal["minggu", "bulan"] = "minggu",
    dari: date | None = Query(None, alias="from", description="YYYY-MM-DD"),
    sampai: date | None = Query(None, alias="to", description="YYYY-MM-DD"),
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    """Rentang tanggal eksplisit (from + to) didahulukan; kalau tidak ada, dipakai periode (7 atau 30 hari terakhir)."""
    if (dari is None) != (sampai is None):
        raise HTTPException(status_code=422, detail="Isi 'from' dan 'to' bersamaan")
    if dari is None:
        sampai = hari_ini()
        dari = sampai - timedelta(days=29 if periode == "bulan" else 6)
    return _jalankan(analitik.laporan, db, dari, sampai)


@router.get("/notifications", response_model=list[Notifikasi])
def notifikasi(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Terbaru di atas."""
    return analitik.daftar_notifikasi(db, user)


# 'baca-semua' didaftarkan SEBELUM '{notif_id}/baca' agar jelas tidak tertukar
@router.post("/notifications/baca-semua", response_model=Ok)
def baca_semua(user: User = Depends(current_user), db: Session = Depends(get_db)):
    analitik.tandai_semua_dibaca(db, user)
    return Ok()


@router.post("/notifications/{notif_id}/baca", response_model=Ok)
def baca(notif_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _jalankan(analitik.tandai_dibaca, db, user, notif_id)
    return Ok()
