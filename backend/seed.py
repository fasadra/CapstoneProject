"""Mengisi database dengan data contoh (Apel, Jeruk, Anggur) yang setara dengan data contoh lama di js/api.js.

Pakai (dari folder backend/):
    python seed.py            # isi data contoh bila database masih kosong
    python seed.py --reset    # HAPUS data stok & scan lalu isi ulang (akun pengguna tidak disentuh)

Catatan: akun pengguna (admin) dibuat pada Tahap 3 (login). Di sini kolom created_by dibiarkan kosong.
"""
import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import DEFAULT_SETTINGS, KODE
from app.database import SessionLocal
from app.models import Batch, BatchCounter, HasilScan, Scan, Setting, StockOut

WIB = ZoneInfo(settings.timezone)


def make_clock(now: datetime | None = None):
    """Mengembalikan fungsi ago/min_ago. Jam 'N hari lalu pukul H:M' dihitung menurut WIB, disimpan sebagai UTC."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    def ago(days: int, h: int, m: int) -> datetime:
        local = now.astimezone(WIB) - timedelta(days=days)
        t = local.replace(hour=h, minute=m, second=0, microsecond=0).astimezone(timezone.utc)
        # Tidak pernah melewati waktu sekarang, agar data contoh selalu tampak baru.
        return t if t <= now else now - timedelta(minutes=5)

    def min_ago(m: int) -> datetime:
        return now - timedelta(minutes=m)

    return ago, min_ago


def split_counts(n: int, comp: list[int]) -> list[int]:
    """Bagi n buah ke [segar, kurang, busuk] sesuai persen komposisi (metode sisa terbesar)."""
    raw = [n * p / 100 for p in comp]
    counts = [int(x) for x in raw]
    order = sorted(range(3), key=lambda i: raw[i] - counts[i], reverse=True)
    for i in order[: n - sum(counts)]:
        counts[i] += 1
    return counts


def sample(clock):
    ago, min_ago = clock
    # putaran: (waktu, komposisi [segar,kurang,busuk] %, jumlah buah seluruh lapis)
    return [
        dict(id="AGR-1003", buah="Anggur", kg=12, masuk=ago(2, 8, 0), lapis=4,
             putaran=[(ago(2, 8, 0), [70, 20, 10], 40), (min_ago(10), [60, 30, 10], 36)],
             keluar=[(ago(1, 16, 30), 4, "Terbuang")]),
        dict(id="JRK-1009", buah="Jeruk", kg=35, masuk=ago(5, 8, 30), lapis=5,
             putaran=[(ago(5, 8, 30), [70, 20, 10], 45)],
             keluar=[]),
        dict(id="APL-1012", buah="Apel", kg=30, masuk=ago(6, 8, 0), lapis=4,
             putaran=[(ago(6, 8, 0), [70, 20, 10], 44), (min_ago(60), [60, 10, 30], 40)],
             keluar=[(ago(2, 12, 0), 5, "Terbuang")]),
    ]


def wipe(db: Session) -> None:
    for model in (HasilScan, Scan, StockOut, Batch):
        db.execute(delete(model))
    db.execute(delete(BatchCounter))
    db.flush()


def ensure_defaults(db: Session) -> None:
    """Pastikan pengaturan & penghitung batch ada (biasanya sudah dibuat oleh migrasi)."""
    for k, v in DEFAULT_SETTINGS.items():
        if db.get(Setting, k) is None:
            db.add(Setting(key=k, value=v))
    for kode in KODE.values():
        if db.get(BatchCounter, kode) is None:
            db.add(BatchCounter(kode=kode, last_no=1000))
    db.flush()


def seed(db: Session, reset: bool = False, now: datetime | None = None) -> dict:
    if reset:
        wipe(db)
    elif db.scalar(select(func.count()).select_from(Batch)):
        return {"seeded": False}

    ensure_defaults(db)
    rng = random.Random(42)  # keyakinan acak tetapi selalu sama setiap kali seed
    n_scan = n_hasil = 0

    for b in sample(make_clock(now)):
        db.add(Batch(id=b["id"], buah=b["buah"], jumlah_kg=b["kg"], masuk_pada=b["masuk"]))
        db.flush()

        for putaran_no, (waktu, comp, n_buah) in enumerate(b["putaran"], start=1):
            s, k, bu = split_counts(n_buah, comp)
            kelas_list = [0] * s + [1] * k + [2] * bu
            per_lapis = [[] for _ in range(b["lapis"])]
            for i, kelas in enumerate(kelas_list):  # sebar rata supaya tiap lapis campuran
                per_lapis[i % b["lapis"]].append(kelas)

            for lapis_ke, daftar in enumerate(per_lapis, start=1):
                scan = Scan(batch_id=b["id"], putaran=putaran_no, lapis_ke=lapis_ke,
                            waktu=waktu + timedelta(seconds=20 * (lapis_ke - 1)))
                scan.hasil = [
                    HasilScan(buah=b["buah"], kelas=kelas, keyakinan=round(rng.uniform(0.78, 0.98), 3))
                    for kelas in daftar
                ]
                db.add(scan)
                n_scan += 1
                n_hasil += len(daftar)

        for waktu, qty, alasan in b["keluar"]:
            db.add(StockOut(gid=str(uuid.uuid4()), batch_id=b["id"], qty_kg=qty, alasan=alasan, waktu=waktu))

        kode, nomor = b["id"].split("-")
        counter = db.get(BatchCounter, kode)
        counter.last_no = max(counter.last_no, int(nomor))

    db.commit()
    return {"seeded": True, "batch": 3, "scan": n_scan, "hasil_scan": n_hasil}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true", help="hapus data stok & scan lalu isi ulang")
    args = ap.parse_args()
    with SessionLocal() as session:
        result = seed(session, reset=args.reset)
    if result["seeded"]:
        print(f"Selesai: {result['batch']} batch, {result['scan']} scan (lapis), {result['hasil_scan']} buah terdeteksi.")
    else:
        print("Database sudah berisi batch, tidak ada yang diubah. Gunakan --reset untuk mengisi ulang.")
