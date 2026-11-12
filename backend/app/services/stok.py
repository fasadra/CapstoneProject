"""Logika stok masuk dan keluar.

Aturan penting:
- Sisa batch = jumlah masuk - total stok keluar. Batch yang dihapus (deleted_at terisi) tidak ikut dihitung.
- Stok keluar mengambil dari batch TERTUA dulu (FIFO), di dalam satu transaksi. Baris batch dikunci
  (SELECT ... FOR UPDATE) sebelum sisa dihitung, sehingga dua pencatatan bersamaan tidak membuat stok minus.
- Komposisi batch (segar/kurang/busuk) dihitung dari hasil_scan pada putaran terbaru (semua lapis digabung).
"""
import math
import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..constants import KODE, LATIN
from ..models import Batch, BatchCounter, HasilScan, Scan, StockOut, User
from .waktu import aware_utc, iso_wib, sekarang_utc


class StokError(Exception):
    """Kesalahan aturan bisnis; router mengubahnya menjadi respons HTTP."""
    def __init__(self, pesan: str, status: int = 400):
        super().__init__(pesan)
        self.pesan, self.status = pesan, status


# ---------------------------------------------------------------- angka

def q1(x) -> Decimal:
    """Bulatkan ke 1 desimal (kg)."""
    return Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def f1(x) -> float:
    return float(q1(x))


def fmt_kg(x) -> str:
    return f"{float(x):g}"          # 25.0 -> "25", 8.5 -> "8.5"


def _js_round(v: float) -> int:
    return math.floor(v + 0.5)      # sama dengan Math.round di JavaScript (0.5 dibulatkan ke atas)


def pct3(hitung: list[int]) -> list[int]:
    """[segar, kurang, busuk] -> persen bulat yang berjumlah 100. Rumusnya sama dengan frontend."""
    total = sum(hitung)
    if not total:
        return [0, 0, 0]
    x = _js_round(hitung[0] / total * 100)
    y = _js_round(hitung[1] / total * 100)
    if x + y > 100:
        y = 100 - x
    return [x, y, 100 - x - y]


# ---------------------------------------------------------------- pembantu query

def _kunci_batch_aktif(db: Session, **kondisi) -> select:
    return (
        select(Batch)
        .where(Batch.deleted_at.is_(None), *[getattr(Batch, k) == v for k, v in kondisi.items()])
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _jumlah_keluar(db: Session, ids: list[str]) -> dict[str, Decimal]:
    if not ids:
        return {}
    rows = db.execute(
        select(StockOut.batch_id, func.sum(StockOut.qty_kg))
        .where(StockOut.batch_id.in_(ids)).group_by(StockOut.batch_id)
    ).all()
    return {bid: q1(total or 0) for bid, total in rows}


def _hitung_per_putaran(db: Session, ids: list[str]) -> dict[str, dict[int, list[int]]]:
    """{batch_id: {putaran: [segar, kurang, busuk]}} (jumlah buah, semua lapis digabung)."""
    if not ids:
        return {}
    rows = db.execute(
        select(Scan.batch_id, Scan.putaran, HasilScan.kelas, func.count())
        .join(HasilScan, HasilScan.scan_id == Scan.id)
        .where(Scan.batch_id.in_(ids))
        .group_by(Scan.batch_id, Scan.putaran, HasilScan.kelas)
    ).all()
    per: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for bid, putaran, kelas, n in rows:
        per[bid][putaran][kelas] = n
    return per


def _ringkas(db: Session, batches: list[Batch]) -> list[dict]:
    ids = [b.id for b in batches]
    keluar = _jumlah_keluar(db, ids)
    per = _hitung_per_putaran(db, ids)
    hasil = []
    for b in batches:
        k = keluar.get(b.id, Decimal("0.0"))
        putaran = per.get(b.id) or {}
        hasil.append({
            "id": b.id,
            "buah": b.buah,
            "jumlah": f1(b.jumlah_kg),
            "keluar": f1(k),
            "sisa": f1(q1(b.jumlah_kg) - k),
            "komposisi": pct3(putaran[max(putaran)]) if putaran else None,
            "komposisiAwal": pct3(putaran[min(putaran)]) if putaran else None,
            "masukPada": iso_wib(b.masuk_pada),
        })
    return hasil


# ---------------------------------------------------------------- stok masuk

def daftar_masuk(db: Session, limit: int | None = None) -> list[dict]:
    q = select(Batch).where(Batch.deleted_at.is_(None)).order_by(Batch.masuk_pada.desc(), Batch.id.desc())
    if limit:
        q = q.limit(limit)
    return _ringkas(db, list(db.scalars(q).all()))


def detail_batch(db: Session, batch_id: str) -> dict:
    b = db.scalar(select(Batch).where(Batch.id == batch_id, Batch.deleted_at.is_(None)))
    if b is None:
        raise StokError("Kiriman tidak ditemukan", 404)
    ringkas = _ringkas(db, [b])[0]
    per = _hitung_per_putaran(db, [b.id])

    # (waktu, urutan bila waktunya sama, isi)
    kejadian = [(aware_utc(b.masuk_pada), 0, {"k": "in", "t": iso_wib(b.masuk_pada), "q": f1(b.jumlah_kg)})]

    scan_rows = db.execute(
        select(Scan.putaran, func.min(Scan.waktu), func.count(Scan.id))
        .where(Scan.batch_id == b.id).group_by(Scan.putaran)
    ).all()
    for putaran, waktu, n_lapis in scan_rows:
        hitung = per[b.id][putaran]
        kejadian.append((aware_utc(waktu), 1, {
            "k": "scan", "t": iso_wib(waktu), "c": pct3(hitung), "n": sum(hitung),
            "putaran": putaran, "lapis": n_lapis,
        }))

    for so in db.scalars(select(StockOut).where(StockOut.batch_id == b.id).order_by(StockOut.waktu, StockOut.id)):
        kejadian.append((aware_utc(so.waktu), 2, {
            "k": "out", "t": iso_wib(so.waktu), "q": f1(so.qty_kg), "r": so.alasan,
        }))

    kejadian.sort(key=lambda e: (e[0], e[1]))
    sisa = Decimal("0.0")
    riwayat = []
    for _, _, item in kejadian:
        if item["k"] == "in":
            sisa += q1(item["q"])
        elif item["k"] == "out":
            sisa -= q1(item["q"])
        item["sisa"] = f1(sisa) if item["k"] != "scan" else None
        riwayat.append(item)

    return {**ringkas, "latin": LATIN.get(b.buah, ""), "riwayat": riwayat}


def _baris_hasil(lapis) -> list[dict]:
    """Ubah satu lapis (hitung / kotak) menjadi baris hasil_scan, satu baris per buah."""
    if lapis.kotak:
        return [{"kelas": k.k, "keyakinan": k.keyakinan, "bbox": [k.x, k.y, k.w, k.h]} for k in lapis.kotak]
    return [
        {"kelas": kelas, "keyakinan": None, "bbox": None}
        for kelas, n in enumerate(lapis.hitung) for _ in range(n)
    ]


def _ambil_penghitung(db: Session, kode: str) -> BatchCounter:
    """Ambil penghitung nomor batch untuk satu kode dan kunci barisnya sampai transaksi selesai."""
    stmt = select(BatchCounter).where(BatchCounter.kode == kode).with_for_update().execution_options(populate_existing=True)
    counter = db.scalar(stmt)
    if counter is None:                     # belum ada (basis data baru): buat, tahan bila bentrok
        try:
            with db.begin_nested():
                db.add(BatchCounter(kode=kode, last_no=1000))
                db.flush()
        except IntegrityError:
            pass
        counter = db.scalar(stmt)
    return counter


def buat_batch(db: Session, user: User, buah: str, jumlah: Decimal, lapis) -> str:
    kode = KODE[buah]
    counter = _ambil_penghitung(db, kode)
    counter.last_no += 1
    batch_id = f"{kode}-{counter.last_no}"

    waktu = sekarang_utc()
    db.add(Batch(id=batch_id, buah=buah, jumlah_kg=q1(jumlah), masuk_pada=waktu, created_by=user.id))
    for nomor, l in enumerate(lapis or [], start=1):
        scan = Scan(batch_id=batch_id, putaran=1, lapis_ke=nomor, waktu=waktu, created_by=user.id)
        scan.hasil = [HasilScan(buah=buah, **baris) for baris in _baris_hasil(l)]
        db.add(scan)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if db.get(Batch, batch_id) is not None:          # nomor itu memang sudah dipakai batch lain
            raise StokError("Nomor batch bentrok, silakan coba lagi", 409)
        if "keyakinan" in str(e.orig):                    # kolom masih NOT NULL = migrasi 0002 belum dijalankan
            raise StokError(
                "Struktur database belum diperbarui. Jalankan 'alembic upgrade head' di folder backend, lalu coba lagi.",
                500,
            )
        raise                                             # penyebab lain: biarkan terlihat di log server
    return batch_id


def ubah_batch(db: Session, batch_id: str, buah: str, jumlah: Decimal) -> None:
    b = db.scalar(_kunci_batch_aktif(db, id=batch_id))
    if b is None:
        raise StokError("Kiriman tidak ditemukan", 404)
    if buah != b.buah:
        raise StokError("Jenis buah tidak bisa diubah. Hapus kiriman ini lalu catat ulang dengan jenis yang benar.")
    keluar = _jumlah_keluar(db, [b.id]).get(b.id, Decimal("0.0"))
    if q1(jumlah) < keluar:
        raise StokError(f"Jumlah tidak boleh di bawah stok yang sudah keluar ({fmt_kg(keluar)} kg)")
    b.jumlah_kg = q1(jumlah)
    db.commit()


def pindai_ulang(db: Session, user: User, batch_id: str, lapis) -> dict:
    """Scan ulang (QC berkala): putaran baru berisi hasil semua lapis yang difoto kali ini.
    Baris batch dikunci dulu, jadi dua pindai bersamaan mendapat nomor putaran yang berbeda."""
    b = db.scalar(_kunci_batch_aktif(db, id=batch_id))
    if b is None:
        raise StokError("Kiriman tidak ditemukan", 404)
    keluar = _jumlah_keluar(db, [b.id]).get(b.id, Decimal("0.0"))
    if q1(b.jumlah_kg) - keluar <= 0:
        raise StokError("Stok kiriman ini sudah habis, tidak perlu dipindai ulang")

    sebelumnya = _hitung_per_putaran(db, [b.id]).get(b.id) or {}
    putaran = (max(sebelumnya) + 1) if sebelumnya else 1
    waktu = sekarang_utc()
    n_lapis = len(lapis)
    for nomor, l in enumerate(lapis, start=1):
        scan = Scan(batch_id=b.id, putaran=putaran, lapis_ke=nomor, waktu=waktu, created_by=user.id)
        scan.hasil = [HasilScan(buah=b.buah, **baris) for baris in _baris_hasil(l)]
        db.add(scan)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if "keyakinan" in str(e.orig):
            raise StokError(
                "Struktur database belum diperbarui. Jalankan 'alembic upgrade head' di folder backend, lalu coba lagi.", 500)
        raise

    total = [0, 0, 0]
    for l in lapis:
        for i in range(3):
            total[i] += l.hitung[i]
    n_sebelumnya = db.scalar(
        select(func.count(Scan.id)).where(Scan.batch_id == b.id, Scan.putaran == max(sebelumnya))
    ) if sebelumnya else None
    return {
        "putaran": putaran,
        "lapis": n_lapis,
        "lapisSebelumnya": n_sebelumnya,
        "komposisi": pct3(total),
        "komposisiSebelumnya": pct3(sebelumnya[max(sebelumnya)]) if sebelumnya else None,
    }


def hapus_batch(db: Session, batch_id: str) -> None:
    """Hapus lunak: hilang dari daftar, laporan, dan stok keluar, tapi barisnya tetap ada di database."""
    b = db.scalar(_kunci_batch_aktif(db, id=batch_id))
    if b is None:
        raise StokError("Kiriman tidak ditemukan", 404)
    b.deleted_at = sekarang_utc()
    db.commit()


# ---------------------------------------------------------------- stok keluar

def daftar_keluar(db: Session) -> list[dict]:
    rows = db.execute(
        select(StockOut.gid, Batch.buah, StockOut.qty_kg, StockOut.alasan, StockOut.waktu)
        .join(Batch, Batch.id == StockOut.batch_id)
        .where(Batch.deleted_at.is_(None))
        .order_by(StockOut.waktu.desc(), StockOut.id.desc())
    ).all()
    grup: dict[str, dict] = {}
    for gid, buah, qty, alasan, waktu in rows:
        g = grup.setdefault(gid, {"gid": gid, "buah": buah, "jumlah": Decimal("0.0"), "alasan": alasan, "waktu": iso_wib(waktu)})
        g["jumlah"] += q1(qty)
    return [{**g, "jumlah": f1(g["jumlah"])} for g in grup.values()]


def catat_keluar(db: Session, user: User, buah: str, jumlah: Decimal, alasan: str) -> dict:
    """FIFO: ambil dari batch tertua yang masih punya sisa."""
    batches = db.scalars(
        _kunci_batch_aktif(db, buah=buah).order_by(Batch.masuk_pada, Batch.id)
    ).all()
    # sisa dihitung SETELAH baris dikunci, jadi pencatatan lain yang baru selesai sudah terhitung
    keluar = _jumlah_keluar(db, [b.id for b in batches])
    sisa = {b.id: q1(b.jumlah_kg) - keluar.get(b.id, Decimal("0.0")) for b in batches}
    tersedia = sum((s for s in sisa.values() if s > 0), Decimal("0.0"))

    jumlah = q1(jumlah)
    if jumlah > tersedia:
        raise StokError(f"Stok {buah} hanya tersisa {fmt_kg(tersedia)} kg")

    gid, waktu, perlu, diambil = str(uuid.uuid4()), sekarang_utc(), jumlah, []
    for b in batches:
        if perlu <= 0:
            break
        if sisa[b.id] <= 0:
            continue
        ambil = min(sisa[b.id], perlu)
        db.add(StockOut(gid=gid, batch_id=b.id, qty_kg=ambil, alasan=alasan, waktu=waktu, created_by=user.id))
        diambil.append({"batch": b.id, "jumlah": f1(ambil)})
        perlu -= ambil
    db.commit()
    return {"gid": gid, "diambil": diambil}
