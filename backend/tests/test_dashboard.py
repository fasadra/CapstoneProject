"""Pengujian dashboard, analisis, laporan, dan notifikasi (Tahap 4b).

Datanya dibuat dengan tanggal tetap (September 2026) dan 'sekarang' disuntikkan, sehingga hasilnya tidak
bergantung pada kapan tes dijalankan. Dunia contoh (WIB):

  APL-2001 Apel  20 kg  masuk 13/9 08:00  scan p1 [8,2,0]   keluar 5 kg Terjual 14/9 10:00   scan p2 15/9 09:00 [5,3,2]
  JRK-2002 Jeruk 10 kg  masuk 14/9 09:00  scan p1 lapis1 [4,1,0] + lapis2 [3,2,0]
  APL-2003 Apel   8 kg  masuk 15/9 07:00  scan p1 [2,2,4]   keluar 8 kg Terbuang 15/9 11:00 (stok habis)
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Batch, HasilScan, NotifRead, Scan, Setting, StockOut, User
from app.security import hash_password, make_session_token
from app.services import analitik
from app.services.analitik import AnalitikError
from seed import seed

WIB = ZoneInfo(settings.timezone)
HASH = hash_password("SandiBagus123")


def W(hari, jam=0, menit=0):
    """Waktu WIB pada September 2026, dalam UTC."""
    return datetime(2026, 9, hari, jam, menit, tzinfo=WIB).astimezone(timezone.utc)


SEKARANG = W(15, 12)


def tambah_scan(db, batch_id, buah, putaran, lapis, waktu, hitung):
    s = Scan(batch_id=batch_id, putaran=putaran, lapis_ke=lapis, waktu=waktu)
    s.hasil = [HasilScan(buah=buah, kelas=k) for k, n in enumerate(hitung) for _ in range(n)]
    db.add(s)


def buat_dunia(db):
    db.add_all([
        Batch(id="APL-2001", buah="Apel", jumlah_kg=20, masuk_pada=W(13, 8)),
        Batch(id="JRK-2002", buah="Jeruk", jumlah_kg=10, masuk_pada=W(14, 9)),
        Batch(id="APL-2003", buah="Apel", jumlah_kg=8, masuk_pada=W(15, 7)),
    ])
    db.flush()
    tambah_scan(db, "APL-2001", "Apel", 1, 1, W(13, 8), [8, 2, 0])
    tambah_scan(db, "APL-2001", "Apel", 2, 1, W(15, 9), [5, 3, 2])
    tambah_scan(db, "JRK-2002", "Jeruk", 1, 1, W(14, 9), [4, 1, 0])
    tambah_scan(db, "JRK-2002", "Jeruk", 1, 2, W(14, 9), [3, 2, 0])
    tambah_scan(db, "APL-2003", "Apel", 1, 1, W(15, 7), [2, 2, 4])
    db.add_all([
        StockOut(gid="g1", batch_id="APL-2001", qty_kg=5, alasan="Terjual", waktu=W(14, 10)),
        StockOut(gid="g2", batch_id="APL-2003", qty_kg=8, alasan="Terbuang", waktu=W(15, 11)),
    ])
    db.commit()


def _klien(db, nama="uji"):
    user = User(nama=nama, username=nama, email=f"{nama}@toko.id", role="admin", password_hash=HASH)
    db.add(user)
    db.commit()
    c = TestClient(app)
    c.cookies.set(settings.cookie_name, make_session_token(user.id, user.password_hash))
    return c, user


@pytest.fixture()
def dunia(db):
    buat_dunia(db)
    app.dependency_overrides[get_db] = lambda: db
    c, user = _klien(db)
    c.user = user
    yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def klien_seed(db):
    seed(db, reset=True)
    app.dependency_overrides[get_db] = lambda: db
    c, _ = _klien(db)
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------- dashboard (logika)

def test_ringkasan_hitungan_dan_tren(db, dunia):
    r = analitik.ringkasan(db, SEKARANG)
    assert r["scanHariIni"] == 2                       # scan p2 APL-2001 dan scan APL-2003 (15/9)
    assert r["persen"] == [58, 30, 12]                 # APL-2001 15 kg [50,30,20] + JRK-2002 10 kg [70,30,0]
    assert r["trend"] == [-18, 6, 12]                  # kemarin: [76,24,0] (masih scan p1 APL-2001, belum ada APL-2003)


def test_ringkasan_hari_tanpa_pembanding(db, dunia):
    r = analitik.ringkasan(db, W(13, 12))              # 13/9: belum ada data kemarin
    assert r["scanHariIni"] == 1 and r["trend"] == [None, None, None]
    assert r["persen"] == [80, 20, 0]


def test_ringkasan_tanpa_stok_atau_scan(db):
    assert analitik.ringkasan(db, SEKARANG) == {"scanHariIni": 0, "persen": None, "trend": [None, None, None]}
    db.add(Batch(id="APL-1", buah="Apel", jumlah_kg=5, masuk_pada=W(14, 8)))
    db.commit()                                          # ada stok tetapi belum pernah dipindai
    assert analitik.ringkasan(db, SEKARANG)["persen"] is None


def test_ringkasan_mengabaikan_batch_terhapus(db, dunia):
    db.get(Batch, "JRK-2002").deleted_at = W(15, 10)
    db.commit()
    r = analitik.ringkasan(db, SEKARANG)
    assert r["persen"] == [50, 30, 20] and r["scanHariIni"] == 2


def test_batas_hari_mengikuti_wib(db):
    """00:30 WIB tanggal 15 = 17:30 UTC tanggal 14. Harus dihitung sebagai hari ke-15."""
    db.add(Batch(id="APL-1", buah="Apel", jumlah_kg=5, masuk_pada=W(14, 8)))
    db.flush()
    tambah_scan(db, "APL-1", "Apel", 1, 1, W(15, 0, 30), [3, 0, 0])
    tambah_scan(db, "APL-1", "Apel", 2, 1, W(14, 23, 30), [3, 0, 0])
    db.commit()
    assert analitik.ringkasan(db, SEKARANG)["scanHariIni"] == 1


# ---------------------------------------------------------------- analisis (logika)

def test_analisis_minggu(db, dunia):
    assert analitik.analisis(db, "minggu", SEKARANG) == {"persen": [58, 26, 16], "scan": [4, 0, 1]}


def test_analisis_periode_dibatasi_waktu(db, dunia):
    kosong = {"persen": [0, 0, 0], "scan": [0, 0, 0]}
    assert analitik.analisis(db, "minggu", W(30, 12)) == kosong        # 7 hari terakhir dari 30/9: mulai 24/9
    assert analitik.analisis(db, "bulan", W(30, 12)) == {"persen": [58, 26, 16], "scan": [4, 0, 1]}


def test_analisis_batas_awal_periode_termasuk(db, dunia):
    # 'minggu' pada 21/9 mulai 15/9 00:00 WIB: hanya scan 15/9 yang ikut (p2 APL-2001 dan APL-2003)
    assert analitik.analisis(db, "minggu", W(21, 12)) == {"persen": [39, 28, 33], "scan": [1, 0, 1]}


# ---------------------------------------------------------------- laporan (logika)

def test_laporan_rentang(db, dunia):
    r = analitik.laporan(db, date(2026, 9, 13), date(2026, 9, 15))
    assert r["rows"] == [
        {"buah": "Apel", "masuk": 28.0, "terjual": 5.0, "terbuang": 8.0, "sisa": 15.0},
        {"buah": "Jeruk", "masuk": 10.0, "terjual": 0.0, "terbuang": 0.0, "sisa": 10.0},
    ]
    assert r["ringkas"] == {"masuk": 38.0, "terjual": 5.0, "terbuang": 8.0}


def test_laporan_sehari_sisa_adalah_stok_akhir_hari(db, dunia):
    r = analitik.laporan(db, date(2026, 9, 14), date(2026, 9, 14))
    assert r["rows"] == [
        {"buah": "Jeruk", "masuk": 10.0, "terjual": 0.0, "terbuang": 0.0, "sisa": 10.0},   # masuk paling baru di atas
        {"buah": "Apel", "masuk": 0.0, "terjual": 5.0, "terbuang": 0.0, "sisa": 15.0},
    ]
    assert r["ringkas"] == {"masuk": 10.0, "terjual": 5.0, "terbuang": 0.0}


def test_laporan_sebelum_ada_data(db, dunia):
    assert analitik.laporan(db, date(2026, 9, 10), date(2026, 9, 12)) == {
        "ringkas": {"masuk": 0.0, "terjual": 0.0, "terbuang": 0.0}, "rows": []}


def test_laporan_hanya_stok_sisa_tetap_muncul(db, dunia):
    r = analitik.laporan(db, date(2026, 9, 20), date(2026, 9, 20))        # tak ada kejadian, tapi stok masih ada
    assert [(x["buah"], x["masuk"], x["sisa"]) for x in r["rows"]] == [("Apel", 0.0, 15.0), ("Jeruk", 0.0, 10.0)]


def test_laporan_mengabaikan_batch_terhapus(db, dunia):
    db.get(Batch, "APL-2003").deleted_at = W(15, 12)
    db.commit()
    r = analitik.laporan(db, date(2026, 9, 13), date(2026, 9, 15))
    assert r["rows"] == [                                   # masuk Apel terakhir kini 13/9, jadi Jeruk (14/9) di atas
        {"buah": "Jeruk", "masuk": 10.0, "terjual": 0.0, "terbuang": 0.0, "sisa": 10.0},
        {"buah": "Apel", "masuk": 20.0, "terjual": 5.0, "terbuang": 0.0, "sisa": 15.0},
    ]
    assert r["ringkas"] == {"masuk": 30.0, "terjual": 5.0, "terbuang": 0.0}


def test_laporan_rentang_tidak_valid(db):
    with pytest.raises(AnalitikError):
        analitik.laporan(db, date(2026, 9, 15), date(2026, 9, 14))
    with pytest.raises(AnalitikError):
        analitik.laporan(db, date(2025, 8, 31), date(2026, 9, 1))       # 367 hari
    analitik.laporan(db, date(2025, 9, 1), date(2026, 9, 1))            # tepat 366 hari (batas), boleh


# ---------------------------------------------------------------- notifikasi (logika + API)

IDS = ["APL-2001|busuk|2", "APL-2001|kurang|2", "JRK-2002|kurang|1"]


def test_notifikasi_isi_dan_urutan(dunia):
    data = dunia.get("/api/notifications").json()
    assert [n["id"] for n in data] == IDS                         # terbaru dulu; busuk sebelum kurang pada waktu yang sama
    a_busuk, a_kurang, b_kurang = data
    assert (a_busuk["batch"], a_busuk["buah"], a_busuk["type"], a_busuk["persen"], a_busuk["kg"]) == ("APL-2001", "Apel", "busuk", 20, 3.0)
    assert (a_kurang["persen"], a_kurang["kg"], a_kurang["putaran"]) == (30, 4.5, 2)
    assert (b_kurang["buah"], b_kurang["persen"], b_kurang["kg"], b_kurang["putaran"]) == ("Jeruk", 30, 3.0, 1)
    assert a_busuk["waktu"] == "2026-09-15T09:00:00+07:00" and not any(n["dibaca"] for n in data)
    assert set(a_busuk) == {"id", "batch", "buah", "type", "persen", "kg", "waktu", "putaran", "dibaca"}


def test_notifikasi_stok_habis_atau_batch_dihapus_hilang(db, dunia):
    # APL-2003 stoknya habis dan komposisinya buruk [25,25,50], tetapi tidak boleh muncul
    assert all(n["batch"] != "APL-2003" for n in dunia.get("/api/notifications").json())
    assert dunia.post("/api/stok/keluar", json={"buah": "Jeruk", "jumlah": 10, "alasan": "Terjual"}).status_code == 201
    assert [n["id"] for n in dunia.get("/api/notifications").json()] == IDS[:2]
    assert dunia.delete("/api/stok/masuk/APL-2001").status_code == 200
    assert dunia.get("/api/notifications").json() == []


def test_notifikasi_ambang_dari_pengaturan(db, dunia):
    db.add_all([Setting(key="notif_kurang", value="31"), Setting(key="notif_busuk", value="20")])
    db.commit()
    assert [n["id"] for n in dunia.get("/api/notifications").json()] == ["APL-2001|busuk|2"]
    db.get(Setting, "notif_busuk").value = "21"
    db.commit()
    assert dunia.get("/api/notifications").json() == []
    db.get(Setting, "notif_busuk").value = "bukan angka"                  # nilai rusak -> kembali ke bawaan (20)
    db.commit()
    assert [n["id"] for n in dunia.get("/api/notifications").json()] == ["APL-2001|busuk|2"]


def test_tandai_satu_dibaca(dunia):
    assert dunia.post(f"/api/notifications/{IDS[1]}/baca".replace("|", "%7C")).json() == {"ok": True}
    assert [(n["id"], n["dibaca"]) for n in dunia.get("/api/notifications").json()] == [
        (IDS[0], False), (IDS[1], True), (IDS[2], False)]
    assert dunia.post(f"/api/notifications/{IDS[1]}/baca".replace("|", "%7C")).status_code == 200      # boleh diulang


def test_tandai_semua_dibaca_dan_scan_baru_membuat_notifikasi_baru(db, dunia):
    assert dunia.post("/api/notifications/baca-semua").json() == {"ok": True}
    assert all(n["dibaca"] for n in dunia.get("/api/notifications").json())
    # scan ulang (putaran 3) dengan komposisi buruk -> id baru, belum dibaca
    tambah_scan(db, "JRK-2002", "Jeruk", 3, 1, W(15, 10), [2, 4, 4])
    db.commit()
    baru = {n["id"]: n["dibaca"] for n in dunia.get("/api/notifications").json()}
    assert baru["JRK-2002|busuk|3"] is False and baru["JRK-2002|kurang|3"] is False
    assert "JRK-2002|kurang|1" not in baru                                   # putaran lama digantikan


def test_status_dibaca_terpisah_per_pengguna(db, dunia):
    dunia.post("/api/notifications/baca-semua")
    c2, user2 = _klien(db, "kedua")
    assert not any(n["dibaca"] for n in c2.get("/api/notifications").json())
    assert db.scalar(select(func.count()).select_from(NotifRead).where(NotifRead.user_id == user2.id)) == 0
    assert db.scalar(select(func.count()).select_from(NotifRead).where(NotifRead.user_id == dunia.user.id)) == 3


@pytest.mark.parametrize("kunci", ["ngawur", "APL-2001|rusak|2", "apl-2001|busuk|2", "APL-2001|busuk|x", "APL-2001|busuk|2|3", "A" * 200])
def test_tandai_dibaca_menolak_id_tak_dikenal(dunia, kunci):
    assert dunia.post(f"/api/notifications/{kunci.replace('|', '%7C')}/baca").status_code == 422


# ---------------------------------------------------------------- API: bentuk, validasi, login

def test_semua_endpoint_wajib_login(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        anon = TestClient(app)
        for metode, url in [("get", "/api/dashboard/summary"), ("get", "/api/analisis"), ("get", "/api/laporan"),
                            ("get", "/api/notifications"), ("post", "/api/notifications/baca-semua"),
                            ("post", "/api/notifications/APL-1012%7Cbusuk%7C2/baca")]:
            assert getattr(anon, metode)(url).status_code == 401, (metode, url)
    finally:
        app.dependency_overrides.clear()


def test_api_laporan_rentang_eksplisit(dunia):
    r = dunia.get("/api/laporan", params={"from": "2026-09-13", "to": "2026-09-15"})
    assert r.status_code == 200
    assert r.json()["ringkas"] == {"masuk": 38.0, "terjual": 5.0, "terbuang": 8.0}
    assert [x["buah"] for x in r.json()["rows"]] == ["Apel", "Jeruk"]


@pytest.mark.parametrize("params", [
    {"from": "2026-09-13"}, {"to": "2026-09-13"},
    {"from": "2026-09-15", "to": "2026-09-14"},
    {"from": "bukan-tanggal", "to": "2026-09-14"},
    {"from": "2025-01-01", "to": "2026-09-14"},
    {"periode": "tahun"},
])
def test_api_laporan_validasi(dunia, params):
    assert dunia.get("/api/laporan", params=params).status_code == 422


def test_api_analisis_validasi(dunia):
    assert dunia.get("/api/analisis", params={"period": "tahun"}).status_code == 422


def test_api_bentuk_jawaban_dengan_data_contoh(klien_seed):
    s = klien_seed.get("/api/dashboard/summary").json()
    assert isinstance(s["scanHariIni"], int) and s["scanHariIni"] >= 0
    assert len(s["persen"]) == 3 and sum(s["persen"]) == 100 and len(s["trend"]) == 3
    for periode in ("minggu", "bulan"):
        a = klien_seed.get("/api/analisis", params={"period": periode}).json()
        assert len(a["persen"]) == 3 and len(a["scan"]) == 3
        l = klien_seed.get("/api/laporan", params={"periode": periode}).json()
        assert set(l) == {"ringkas", "rows"} and set(l["ringkas"]) == {"masuk", "terjual", "terbuang"}
    assert [n["id"] for n in klien_seed.get("/api/notifications").json()] == ["AGR-1003|kurang|2", "APL-1012|busuk|2"]


def test_api_stok_masuk_dengan_limit(klien_seed):
    assert len(klien_seed.get("/api/stok/masuk").json()) == 3
    assert [b["id"] for b in klien_seed.get("/api/stok/masuk", params={"limit": 2}).json()] == ["AGR-1003", "JRK-1009"]
    assert klien_seed.get("/api/stok/masuk", params={"limit": 0}).status_code == 422
    assert klien_seed.get("/api/stok/masuk", params={"limit": 201}).status_code == 422
