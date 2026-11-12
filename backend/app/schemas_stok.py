"""Bentuk data masuk/keluar untuk API stok."""
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .constants import FRUITS

MAKS_KG = Decimal("100000")
MAKS_BUAH_PER_LAPIS = 500
MAKS_LAPIS = 200


def _normalisasi_buah(v):
    if not isinstance(v, str):
        raise ValueError("Nama buah wajib diisi")
    teks = " ".join(v.split())
    for nama in FRUITS:
        if nama.lower() == teks.lower():
            return nama
    raise ValueError(f"Buah belum didukung. Pilih salah satu: {', '.join(FRUITS)}")


def _normalisasi_kg(v: Decimal) -> Decimal:
    d = v.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if d <= 0:
        raise ValueError("Jumlah harus lebih dari 0")
    if d > MAKS_KG:
        raise ValueError("Jumlah terlalu besar (maksimal 100.000 kg)")
    return d


class KotakIn(BaseModel):
    """Kotak deteksi satu buah. x, y, w, h berupa pecahan 0 sampai 1 terhadap ukuran foto."""
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(ge=0, le=1)
    h: float = Field(ge=0, le=1)
    k: int = Field(ge=0, le=2)                                     # 0 segar, 1 kurang segar, 2 busuk
    keyakinan: float | None = Field(default=None, ge=0, le=1)


class LapisIn(BaseModel):
    """Hasil satu foto = satu lapis. hitung = [jumlah segar, kurang segar, busuk]."""
    hitung: list[int] = Field(min_length=3, max_length=3)
    kotak: list[KotakIn] | None = None

    @model_validator(mode="after")
    def _cek(self):
        if any(n < 0 for n in self.hitung):
            raise ValueError("Hitungan buah tidak boleh negatif")
        total = sum(self.hitung)
        if total < 1:
            raise ValueError("Setiap lapis harus berisi minimal 1 buah")
        if total > MAKS_BUAH_PER_LAPIS:
            raise ValueError(f"Satu lapis maksimal {MAKS_BUAH_PER_LAPIS} buah")
        if not self.kotak:
            self.kotak = None          # daftar kosong = tidak ada data kotak
        else:
            per_kelas = [sum(1 for k in self.kotak if k.k == i) for i in range(3)]
            if per_kelas != self.hitung:
                raise ValueError("Isi 'kotak' tidak sama dengan 'hitung'")
        return self


class MasukIn(BaseModel):
    buah: str
    jumlah: Decimal = Field(allow_inf_nan=False)
    lapis: list[LapisIn] | None = Field(default=None, max_length=MAKS_LAPIS)

    _buah = field_validator("buah", mode="before")(_normalisasi_buah)
    _jumlah = field_validator("jumlah")(_normalisasi_kg)


class PindaiUlangIn(BaseModel):
    """Scan ulang sebuah kiriman: semua lapis yang masih ada difoto lagi. Hasil tiap foto = satu lapis."""
    lapis: list[LapisIn] = Field(min_length=1, max_length=MAKS_LAPIS)


class UbahMasukIn(BaseModel):
    buah: str
    jumlah: Decimal = Field(allow_inf_nan=False)

    _buah = field_validator("buah", mode="before")(_normalisasi_buah)
    _jumlah = field_validator("jumlah")(_normalisasi_kg)


class KeluarIn(BaseModel):
    buah: str
    jumlah: Decimal = Field(allow_inf_nan=False)
    alasan: Literal["Terjual", "Terbuang"]

    _buah = field_validator("buah", mode="before")(_normalisasi_buah)
    _jumlah = field_validator("jumlah")(_normalisasi_kg)


# ---------------- bentuk jawaban (juga muncul di /docs) ----------------

class BatchRingkas(BaseModel):
    id: str
    buah: str
    jumlah: float
    sisa: float
    komposisi: list[int] | None           # [segar, kurang, busuk] dalam %, dari putaran scan terbaru
    komposisiAwal: list[int] | None       # dari putaran pertama (saat stok masuk)
    masukPada: str


class RiwayatItem(BaseModel):
    k: Literal["in", "scan", "out"]
    t: str
    q: float | None = None                # jumlah kg (masuk/keluar)
    r: str | None = None                  # alasan (keluar)
    c: list[int] | None = None            # komposisi % (scan)
    n: int | None = None                  # jumlah buah (scan)
    sisa: float | None = None             # sisa stok setelah kejadian ini (masuk/keluar)
    putaran: int | None = None
    lapis: int | None = None              # jumlah lapis yang difoto pada putaran itu


class BatchDetail(BatchRingkas):
    latin: str
    keluar: float
    riwayat: list[RiwayatItem]


class BatchBaru(BaseModel):
    id: str


class DiambilDari(BaseModel):
    batch: str
    jumlah: float


class PindaiUlangOut(BaseModel):
    putaran: int                                  # nomor putaran yang baru dibuat (2, 3, ...)
    lapis: int                                    # jumlah lapis yang dipindai kali ini
    lapisSebelumnya: int | None                   # jumlah lapis pada putaran sebelumnya (None bila belum pernah dipindai)
    komposisi: list[int]                          # [segar, kurang, busuk] % hasil pindai ini
    komposisiSebelumnya: list[int] | None


class KeluarBaru(BaseModel):
    gid: str
    diambil: list[DiambilDari]


class KeluarItem(BaseModel):
    gid: str
    buah: str
    jumlah: float
    alasan: str
    waktu: str


class Ok(BaseModel):
    ok: bool = True
