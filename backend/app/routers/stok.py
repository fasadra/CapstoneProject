"""Stok masuk dan keluar.

GET/POST  /api/stok/masuk          GET/PUT/DELETE  /api/stok/masuk/{id}
GET/POST  /api/stok/keluar
Semua endpoint wajib login.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import User
from ..schemas_stok import (
    BatchBaru, BatchDetail, BatchRingkas, KeluarBaru, KeluarIn, KeluarItem, MasukIn, Ok, PindaiUlangIn,
    PindaiUlangOut, UbahMasukIn,
)
from ..services import stok
from ..services.stok import StokError

router = APIRouter(prefix="/api/stok", tags=["stok"])


def _jalankan(fungsi, *args):
    try:
        return fungsi(*args)
    except StokError as e:
        raise HTTPException(status_code=e.status, detail=e.pesan)


@router.get("/masuk", response_model=list[BatchRingkas])
def daftar_masuk(
    limit: int | None = Query(None, ge=1, le=200, description="Batasi jumlah (mis. 5 untuk dashboard)"),
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    """Semua kiriman yang masih aktif, terbaru di atas."""
    return stok.daftar_masuk(db, limit)


@router.get("/masuk/{batch_id}", response_model=BatchDetail)
def detail_masuk(batch_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _jalankan(stok.detail_batch, db, batch_id)


@router.post("/masuk", response_model=BatchBaru, status_code=201)
def tambah_masuk(data: MasukIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Catat kiriman baru. 'lapis' (opsional) berisi hasil klasifikasi tiap foto/lapis; disimpan sebagai putaran 1."""
    return {"id": _jalankan(stok.buat_batch, db, user, data.buah, data.jumlah, data.lapis)}


@router.put("/masuk/{batch_id}", response_model=Ok)
def ubah_masuk(batch_id: str, data: UbahMasukIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _jalankan(stok.ubah_batch, db, batch_id, data.buah, data.jumlah)
    return Ok()


@router.post("/masuk/{batch_id}/scan", response_model=PindaiUlangOut, status_code=201)
def pindai_ulang(batch_id: str, data: PindaiUlangIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Scan ulang kiriman yang masih ada stoknya. Menjadi putaran baru; komposisi dan notifikasi ikut diperbarui."""
    return _jalankan(stok.pindai_ulang, db, user, batch_id, data.lapis)


@router.delete("/masuk/{batch_id}", response_model=Ok)
def hapus_masuk(batch_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _jalankan(stok.hapus_batch, db, batch_id)
    return Ok()


@router.get("/keluar", response_model=list[KeluarItem])
def daftar_keluar(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Satu baris per pencatatan (yang memotong beberapa batch digabung), terbaru di atas."""
    return stok.daftar_keluar(db)


@router.post("/keluar", response_model=KeluarBaru, status_code=201)
def tambah_keluar(data: KeluarIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Catat stok keluar. Diambil dari kiriman terlama dulu (FIFO)."""
    return _jalankan(stok.catat_keluar, db, user, data.buah, data.jumlah, data.alasan)
