"""Bentuk jawaban API dashboard, analisis, laporan, dan notifikasi (muncul di /docs)."""
from typing import Literal

from pydantic import BaseModel


class Ringkasan(BaseModel):
    scanHariIni: int                      # jumlah scan (lapis) hari ini
    persen: list[int] | None              # [segar, kurang, busuk] % seluruh stok yang sudah dipindai; None bila belum ada
    trend: list[int | None]               # selisih % dibanding kemarin (negatif = turun); None bila belum ada pembanding


class Analisis(BaseModel):
    persen: list[int]                     # komposisi gabungan semua buah pada periode
    scan: list[int]                       # jumlah scan yang dominan segar / kurang segar / busuk


class LaporanBaris(BaseModel):
    buah: str
    masuk: float
    terjual: float
    terbuang: float
    sisa: float


class LaporanRingkas(BaseModel):
    masuk: float
    terjual: float
    terbuang: float


class Laporan(BaseModel):
    ringkas: LaporanRingkas
    rows: list[LaporanBaris]


class Notifikasi(BaseModel):
    id: str                               # 'batch|tipe|putaran'
    batch: str
    buah: str
    type: Literal["kurang", "busuk"]
    persen: int
    kg: float
    waktu: str
    putaran: int
    dibaca: bool
