from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Batch, HasilScan, Scan, StockOut

NOW = datetime(2026, 10, 13, 5, 0, tzinfo=timezone.utc)


def batch(id="APL-1001", buah="Apel", kg=10):
    return Batch(id=id, buah=buah, jumlah_kg=kg, masuk_pada=NOW)


def commit_fails(db, obj):
    db.add(obj)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_batch_valid_tersimpan(db):
    db.add(batch())
    db.commit()
    assert db.get(Batch, "APL-1001").buah == "Apel"


@pytest.mark.parametrize("buah", ["Pisang", "Strawberry", "apel", ""])
def test_batch_hanya_menerima_apel_jeruk_anggur(db, buah):
    commit_fails(db, batch(buah=buah))


@pytest.mark.parametrize("kg", [0, -3])
def test_batch_jumlah_harus_positif(db, kg):
    commit_fails(db, batch(kg=kg))


def test_stock_out_aturan(db):
    db.add(batch())
    db.commit()
    commit_fails(db, StockOut(gid="g", batch_id="APL-1001", qty_kg=0, alasan="Terjual", waktu=NOW))
    commit_fails(db, StockOut(gid="g", batch_id="APL-1001", qty_kg=2, alasan="Hilang", waktu=NOW))
    commit_fails(db, StockOut(gid="g", batch_id="TIDAK-ADA", qty_kg=2, alasan="Terjual", waktu=NOW))
    db.add(StockOut(gid="g", batch_id="APL-1001", qty_kg=2.5, alasan="Terjual", waktu=NOW))
    db.commit()


def test_scan_unik_per_batch_putaran_lapis(db):
    db.add(batch())
    db.add(Scan(batch_id="APL-1001", putaran=1, lapis_ke=1, waktu=NOW))
    db.commit()
    commit_fails(db, Scan(batch_id="APL-1001", putaran=1, lapis_ke=1, waktu=NOW))
    db.add(Scan(batch_id="APL-1001", putaran=1, lapis_ke=2, waktu=NOW))   # lapis lain: boleh
    db.add(Scan(batch_id="APL-1001", putaran=2, lapis_ke=1, waktu=NOW))   # putaran lain: boleh
    db.commit()


def test_scan_putaran_dan_lapis_mulai_dari_satu(db):
    db.add(batch())
    db.commit()
    commit_fails(db, Scan(batch_id="APL-1001", putaran=0, lapis_ke=1, waktu=NOW))
    commit_fails(db, Scan(batch_id="APL-1001", putaran=1, lapis_ke=0, waktu=NOW))


@pytest.mark.parametrize("kelas,keyakinan", [(3, 0.9), (-1, 0.9), (0, 1.5), (0, -0.1)])
def test_hasil_scan_nilai_tidak_valid(db, kelas, keyakinan):
    db.add(batch())
    scan = Scan(batch_id="APL-1001", putaran=1, lapis_ke=1, waktu=NOW)
    db.add(scan)
    db.commit()
    commit_fails(db, HasilScan(scan_id=scan.id, buah="Apel", kelas=kelas, keyakinan=keyakinan))


def test_hasil_scan_menyimpan_bbox_json(db):
    db.add(batch())
    scan = Scan(batch_id="APL-1001", putaran=1, lapis_ke=1, waktu=NOW)
    scan.hasil = [HasilScan(buah="Apel", kelas=0, keyakinan=0.9, bbox=[10, 20, 110, 120])]
    db.add(scan)
    db.commit()
    assert db.scalar(select(HasilScan.bbox)) == [10, 20, 110, 120]


def test_hapus_scan_ikut_menghapus_hasilnya(db):
    db.add(batch())
    scan = Scan(batch_id="APL-1001", putaran=1, lapis_ke=1, waktu=NOW)
    scan.hasil = [HasilScan(buah="Apel", kelas=0, keyakinan=0.9) for _ in range(3)]
    db.add(scan)
    db.commit()
    db.delete(scan)
    db.commit()
    assert db.scalar(select(func.count()).select_from(HasilScan)) == 0
