"""Dashboard, analisis, laporan, dan notifikasi.

Semuanya dihitung dari data stok dan scan (tidak ada angka yang disimpan terpisah):
- Komposisi sebuah batch = hasil_scan pada PUTARAN terbaru (semua lapis digabung).
- Stok sisa = jumlah masuk - stok keluar. Batch yang dihapus (deleted_at terisi) tidak ikut dihitung.
- Hari dan periode mengikuti WIB. Parameter 'sekarang' hanya untuk pengujian.
"""
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Batch, HasilScan, NotifRead, Scan, Setting, StockOut, User
from .stok import f1, pct3, q1
from .waktu import akhir_hari_utc, aware_utc, awal_hari_utc, hari_ini, iso_wib, sekarang_utc

AMBANG_BAWAAN = {"notif_kurang": 30, "notif_busuk": 20}
MAKS_HARI_LAPORAN = 366
KUNCI_NOTIF = re.compile(r"^[A-Z]{3}-\d{1,9}\|(kurang|busuk)\|\d{1,6}$")


class AnalitikError(Exception):
    def __init__(self, pesan: str, status: int = 422):
        super().__init__(pesan)
        self.pesan, self.status = pesan, status


@dataclass
class InfoScan:
    putaran: int
    waktu: datetime          # UTC, sudah aware
    hitung: list[int]        # [segar, kurang, busuk] jumlah buah, semua lapis pada putaran itu
    lapis: int


# ---------------------------------------------------------------- pembantu

def _scan_per_batch(db: Session, ids: list[str] | None = None, sampai: datetime | None = None) -> dict[str, list[InfoScan]]:
    """{batch_id: [InfoScan urut putaran]}; hanya batch aktif. 'sampai' membatasi pada scan yang sudah ada saat itu."""
    aktif = Batch.deleted_at.is_(None)
    waktu_q = (
        select(Scan.batch_id, Scan.putaran, func.min(Scan.waktu), func.count(Scan.id))
        .join(Batch, Batch.id == Scan.batch_id).where(aktif).group_by(Scan.batch_id, Scan.putaran)
    )
    kelas_q = (
        select(Scan.batch_id, Scan.putaran, HasilScan.kelas, func.count(HasilScan.id))
        .join(HasilScan, HasilScan.scan_id == Scan.id).join(Batch, Batch.id == Scan.batch_id)
        .where(aktif).group_by(Scan.batch_id, Scan.putaran, HasilScan.kelas)
    )
    if ids is not None:
        if not ids:
            return {}
        waktu_q, kelas_q = waktu_q.where(Scan.batch_id.in_(ids)), kelas_q.where(Scan.batch_id.in_(ids))

    hitung: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0, 0])
    for bid, putaran, kelas, n in db.execute(kelas_q).all():
        hitung[(bid, putaran)][kelas] = n

    hasil: dict[str, list[InfoScan]] = defaultdict(list)
    for bid, putaran, waktu, n_lapis in db.execute(waktu_q).all():
        t = aware_utc(waktu)
        if sampai is not None and t > sampai:
            continue
        hasil[bid].append(InfoScan(putaran, t, list(hitung[(bid, putaran)]), n_lapis))
    for daftar in hasil.values():
        daftar.sort(key=lambda s: s.putaran)
    return hasil


def _sisa_per_batch(db: Session, batches: list[Batch], sampai: datetime | None = None) -> dict[str, Decimal]:
    ids = [b.id for b in batches]
    if not ids:
        return {}
    q = select(StockOut.batch_id, func.sum(StockOut.qty_kg)).where(StockOut.batch_id.in_(ids))
    if sampai is not None:
        q = q.where(StockOut.waktu <= sampai)
    keluar = {bid: q1(total or 0) for bid, total in db.execute(q.group_by(StockOut.batch_id)).all()}
    return {b.id: q1(b.jumlah_kg) - keluar.get(b.id, Decimal("0.0")) for b in batches}


def _batch_aktif(db: Session, sampai: datetime | None = None) -> list[Batch]:
    q = select(Batch).where(Batch.deleted_at.is_(None))
    if sampai is not None:
        q = q.where(Batch.masuk_pada <= sampai)
    return list(db.scalars(q.order_by(Batch.masuk_pada, Batch.id)))


def snapshot(db: Session, sampai: datetime | None = None) -> list[int] | None:
    """Komposisi seluruh stok (dalam %), dibobot sisa kg tiap batch. Hanya batch yang masih ada stok dan sudah dipindai.
    'sampai' = kondisi pada waktu itu (untuk membandingkan dengan kemarin). None bila belum ada data."""
    batches = _batch_aktif(db, sampai)
    sisa = _sisa_per_batch(db, batches, sampai)
    scans = _scan_per_batch(db, [b.id for b in batches], sampai)
    total = s = k = b_ = 0.0
    for b in batches:
        stok, daftar = float(sisa[b.id]), scans.get(b.id)
        if stok <= 0 or not daftar:
            continue
        komp = pct3(daftar[-1].hitung)
        total += stok
        s += stok * komp[0] / 100
        k += stok * komp[1] / 100
        b_ += stok * komp[2] / 100
    return pct3([s, k, b_]) if total else None


# ---------------------------------------------------------------- dashboard

def ringkasan(db: Session, sekarang: datetime | None = None) -> dict:
    """scanHariIni = jumlah scan (lapis) hari ini; persen = komposisi stok saat ini; trend = selisih dari kemarin."""
    hari = hari_ini(sekarang)
    awal, besok = awal_hari_utc(hari), awal_hari_utc(hari + timedelta(days=1))
    scan_hari_ini = db.scalar(
        select(func.count(Scan.id)).join(Batch, Batch.id == Scan.batch_id)
        .where(Batch.deleted_at.is_(None), Scan.waktu >= awal, Scan.waktu < besok)
    )
    sekarang_ = snapshot(db, sekarang)
    kemarin = snapshot(db, akhir_hari_utc(hari - timedelta(days=1)))
    trend = [c - p for c, p in zip(sekarang_, kemarin)] if sekarang_ and kemarin else [None, None, None]
    return {"scanHariIni": scan_hari_ini, "persen": sekarang_, "trend": trend}


def _dominan(c: list[int]) -> int:
    return 0 if c[0] >= c[1] and c[0] >= c[2] else 1 if c[1] >= c[2] else 2


def analisis(db: Session, periode: str, sekarang: datetime | None = None) -> dict:
    """persen = komposisi gabungan semua buah pada semua scan di periode; scan = jumlah scan (lapis) yang kelas dominannya
    segar / kurang segar / busuk. minggu = 7 hari terakhir, bulan = 30 hari terakhir (termasuk hari ini)."""
    mulai = awal_hari_utc(hari_ini(sekarang) - timedelta(days=29 if periode == "bulan" else 6))
    rows = db.execute(
        select(Scan.id, HasilScan.kelas, func.count(HasilScan.id))
        .join(HasilScan, HasilScan.scan_id == Scan.id).join(Batch, Batch.id == Scan.batch_id)
        .where(Batch.deleted_at.is_(None), Scan.waktu >= mulai)
        .group_by(Scan.id, HasilScan.kelas)
    ).all()
    per_scan: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0])
    for sid, kelas, n in rows:
        per_scan[sid][kelas] = n
    total, cacah = [0, 0, 0], [0, 0, 0]
    for hitung in per_scan.values():
        for i in range(3):
            total[i] += hitung[i]
        cacah[_dominan(hitung)] += 1
    return {"persen": pct3(total), "scan": cacah}


# ---------------------------------------------------------------- laporan

def laporan(db: Session, dari: date, sampai: date) -> dict:
    """Per jenis buah: masuk, terjual, terbuang pada rentang tanggal; sisa = stok pada akhir rentang."""
    if sampai < dari:
        raise AnalitikError("Tanggal akhir tidak boleh sebelum tanggal awal")
    if (sampai - dari).days + 1 > MAKS_HARI_LAPORAN:
        raise AnalitikError(f"Rentang laporan maksimal {MAKS_HARI_LAPORAN} hari")
    mulai, selesai = awal_hari_utc(dari), akhir_hari_utc(sampai)
    aktif = Batch.deleted_at.is_(None)

    def jumlah(q):
        return {k: q1(v or 0) for k, v in db.execute(q).all()}

    masuk = jumlah(select(Batch.buah, func.sum(Batch.jumlah_kg)).where(aktif, Batch.masuk_pada >= mulai, Batch.masuk_pada <= selesai).group_by(Batch.buah))
    masuk_s_d_akhir = jumlah(select(Batch.buah, func.sum(Batch.jumlah_kg)).where(aktif, Batch.masuk_pada <= selesai).group_by(Batch.buah))
    keluar_s_d_akhir = jumlah(
        select(Batch.buah, func.sum(StockOut.qty_kg)).join(StockOut, StockOut.batch_id == Batch.id)
        .where(aktif, StockOut.waktu <= selesai).group_by(Batch.buah)
    )
    keluar_alasan = {
        (buah, alasan): q1(total or 0)
        for buah, alasan, total in db.execute(
            select(Batch.buah, StockOut.alasan, func.sum(StockOut.qty_kg)).join(StockOut, StockOut.batch_id == Batch.id)
            .where(aktif, StockOut.waktu >= mulai, StockOut.waktu <= selesai).group_by(Batch.buah, StockOut.alasan)
        ).all()
    }
    terakhir_masuk = {
        buah: aware_utc(t)
        for buah, t in db.execute(select(Batch.buah, func.max(Batch.masuk_pada)).where(aktif, Batch.masuk_pada <= selesai).group_by(Batch.buah)).all()
    }

    baris = []
    for buah in set(masuk_s_d_akhir) | set(masuk) | {b for b, _ in keluar_alasan}:
        r = {
            "buah": buah,
            "masuk": masuk.get(buah, Decimal("0.0")),
            "terjual": keluar_alasan.get((buah, "Terjual"), Decimal("0.0")),
            "terbuang": keluar_alasan.get((buah, "Terbuang"), Decimal("0.0")),
            "sisa": masuk_s_d_akhir.get(buah, Decimal("0.0")) - keluar_s_d_akhir.get(buah, Decimal("0.0")),
        }
        if any(r[k] > 0 for k in ("masuk", "terjual", "terbuang", "sisa")):
            baris.append(r)
    # yang masuknya paling baru di atas; yang belum pernah masuk sampai akhir rentang di bawah
    baris.sort(key=lambda r: (terakhir_masuk.get(r["buah"]) is not None, terakhir_masuk.get(r["buah"]) or datetime.min.replace(tzinfo=aware_utc(mulai).tzinfo)), reverse=True)

    rows = [{k: (f1(v) if k != "buah" else v) for k, v in r.items()} for r in baris]
    jml = lambda k: f1(sum((q1(r[k]) for r in rows), Decimal("0.0")))
    return {"ringkas": {"masuk": jml("masuk"), "terjual": jml("terjual"), "terbuang": jml("terbuang")}, "rows": rows}


# ---------------------------------------------------------------- notifikasi

def ambang(db: Session) -> tuple[int, int]:
    nilai = {s.key: s.value for s in db.scalars(select(Setting).where(Setting.key.in_(AMBANG_BAWAAN)))}
    def angka(k):
        try:
            return int(nilai.get(k, AMBANG_BAWAAN[k]))
        except (TypeError, ValueError):
            return AMBANG_BAWAAN[k]
    return angka("notif_kurang"), angka("notif_busuk")


def _notifikasi_saat_ini(db: Session) -> list[dict]:
    """Dari komposisi scan TERAKHIR tiap batch yang masih ada stoknya: kurang segar >= ambang atau busuk >= ambang.
    Stok habis atau batch dihapus = notifikasinya hilang. Scan baru = notifikasi baru (belum dibaca)."""
    min_kurang, min_busuk = ambang(db)
    batches = _batch_aktif(db)
    sisa = _sisa_per_batch(db, batches)
    scans = _scan_per_batch(db, [b.id for b in batches])
    hasil = []
    for b in batches:
        daftar = scans.get(b.id)
        if sisa[b.id] <= 0 or not daftar:
            continue
        terakhir = daftar[-1]
        komp = pct3(terakhir.hitung)
        for tipe, idx, minimum in (("busuk", 2, min_busuk), ("kurang", 1, min_kurang)):
            if komp[idx] >= minimum:
                hasil.append({
                    "id": f"{b.id}|{tipe}|{terakhir.putaran}", "batch": b.id, "buah": b.buah, "type": tipe,
                    "persen": komp[idx], "kg": f1(float(sisa[b.id]) * komp[idx] / 100),
                    "waktu": iso_wib(terakhir.waktu), "putaran": terakhir.putaran, "_t": terakhir.waktu,
                })
    hasil.sort(key=lambda n: (n["_t"], n["type"] == "busuk"), reverse=True)     # terbaru dulu; busuk sebelum kurang
    return hasil


def daftar_notifikasi(db: Session, user: User) -> list[dict]:
    dibaca = set(db.scalars(select(NotifRead.notif_key).where(NotifRead.user_id == user.id)))
    return [{**{k: v for k, v in n.items() if k != "_t"}, "dibaca": n["id"] in dibaca} for n in _notifikasi_saat_ini(db)]


def _tandai(db: Session, user: User, kunci: list[str]) -> None:
    sudah = set(db.scalars(select(NotifRead.notif_key).where(NotifRead.user_id == user.id, NotifRead.notif_key.in_(kunci)))) if kunci else set()
    for k in kunci:
        if k not in sudah:
            db.add(NotifRead(user_id=user.id, notif_key=k))
    try:
        db.commit()
    except IntegrityError:          # dibaca bersamaan dari dua tab: hasil akhirnya sama
        db.rollback()


def tandai_dibaca(db: Session, user: User, notif_id: str) -> None:
    if not KUNCI_NOTIF.match(notif_id):
        raise AnalitikError("Format id notifikasi tidak dikenal")
    _tandai(db, user, [notif_id])


def tandai_semua_dibaca(db: Session, user: User) -> None:
    _tandai(db, user, [n["id"] for n in _notifikasi_saat_ini(db)])
