from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models import Batch, BatchCounter, HasilScan, Scan, Setting, StockOut
from seed import make_clock, seed, split_counts

# 13 Okt 2026 12:00 UTC = 19:00 WIB
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def komposisi(db, batch_id, putaran):
    """Persen [segar, kurang, busuk] dari seluruh lapis pada satu putaran."""
    rows = db.execute(
        select(HasilScan.kelas, func.count())
        .join(Scan, Scan.id == HasilScan.scan_id)
        .where(Scan.batch_id == batch_id, Scan.putaran == putaran)
        .group_by(HasilScan.kelas)
    ).all()
    total = sum(n for _, n in rows)
    by = dict(rows)
    return [100 * by.get(k, 0) / total for k in range(3)], total


def test_seed_mengisi_tiga_batch(db):
    hasil = seed(db, now=NOW)
    assert hasil["seeded"] is True
    assert {b.buah for b in db.scalars(select(Batch))} == {"Apel", "Jeruk", "Anggur"}
    assert db.scalar(select(func.count()).select_from(Scan)) == 21
    assert db.scalar(select(func.count()).select_from(StockOut)) == 2


def test_seed_tidak_menggandakan_data(db):
    seed(db, now=NOW)
    assert seed(db, now=NOW)["seeded"] is False
    assert db.scalar(select(func.count()).select_from(Batch)) == 3


def test_seed_reset_mengisi_ulang_dengan_hasil_sama(db):
    seed(db, now=NOW)
    seed(db, reset=True, now=NOW)
    assert db.scalar(select(func.count()).select_from(Batch)) == 3
    assert db.scalar(select(func.count()).select_from(Scan)) == 21
    assert db.scalar(select(func.count()).select_from(HasilScan)) == 205


@pytest.mark.parametrize("batch_id,putaran,target,jumlah_buah", [
    ("AGR-1003", 1, [70, 20, 10], 40),
    ("AGR-1003", 2, [60, 30, 10], 36),
    ("JRK-1009", 1, [70, 20, 10], 45),
    ("APL-1012", 1, [70, 20, 10], 44),
    ("APL-1012", 2, [60, 10, 30], 40),
])
def test_komposisi_seed_sesuai_data_contoh_lama(db, batch_id, putaran, target, jumlah_buah):
    seed(db, now=NOW)
    persen, total = komposisi(db, batch_id, putaran)
    assert total == jumlah_buah
    for got, want in zip(persen, target):
        assert abs(got - want) <= 3, (persen, target)


def test_setiap_lapis_berisi_campuran_dan_hanya_buah_batchnya(db):
    seed(db, now=NOW)
    for scan in db.scalars(select(Scan)):
        assert scan.hasil, "lapis tanpa buah"
        assert {h.buah for h in scan.hasil} == {scan.batch.buah}


def test_penghitung_batch_mengikuti_nomor_terbesar(db):
    seed(db, now=NOW)
    assert {c.kode: c.last_no for c in db.scalars(select(BatchCounter))} == {"AGR": 1003, "JRK": 1009, "APL": 1012}
    assert db.get(Setting, "notif_kurang").value == "30"


def test_jam_dihitung_menurut_wib_disimpan_utc():
    ago, _ = make_clock(NOW)
    t = ago(2, 8, 0)  # 11 Okt pukul 08:00 WIB
    assert (t.year, t.month, t.day, t.hour) == (2026, 10, 11, 1) and t.utcoffset().total_seconds() == 0


def test_waktu_tidak_pernah_di_masa_depan():
    ago, _ = make_clock(datetime(2026, 10, 13, 0, 30, tzinfo=timezone.utc))  # 07:30 WIB
    assert ago(0, 23, 0) <= datetime(2026, 10, 13, 0, 30, tzinfo=timezone.utc)


def test_stok_keluar_tidak_melebihi_stok_masuk(db):
    seed(db, now=NOW)
    for b in db.scalars(select(Batch)):
        keluar = sum(float(s.qty_kg) for s in b.stock_outs)
        assert keluar <= float(b.jumlah_kg)


@pytest.mark.parametrize("n", [0, 1, 7, 36, 44, 100])
@pytest.mark.parametrize("comp", [[70, 20, 10], [60, 30, 10], [100, 0, 0], [34, 33, 33]])
def test_split_counts_selalu_berjumlah_n(n, comp):
    out = split_counts(n, comp)
    assert sum(out) == n and all(x >= 0 for x in out)
