"""Pengujian stok masuk dan keluar (Tahap 4a)."""
import os
import threading
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Batch, BatchCounter, HasilScan, Scan, StockOut, User
from app.security import hash_password, make_session_token
from app.services import stok as svc
from seed import seed

HASH = hash_password("SandiBagus123")           # dihitung sekali (argon2 sengaja lambat)
PG = not os.environ.get("TEST_DATABASE_URL", "sqlite://").startswith("sqlite")


@pytest.fixture()
def client(db):
    """Klien yang sudah login, dengan data contoh (APL-1012 sisa 25, JRK-1009 sisa 35, AGR-1003 sisa 8)."""
    seed(db, reset=True)
    user = User(nama="Uji", username="uji", email="uji@toko.id", role="admin", password_hash=HASH)
    db.add(user)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    c.cookies.set(settings.cookie_name, make_session_token(user.id, user.password_hash))
    yield c
    app.dependency_overrides.clear()


def lapis(*hitung):
    return [{"hitung": list(h)} for h in hitung]


def batch_by_id(c, bid):
    return next(b for b in c.get("/api/stok/masuk").json() if b["id"] == bid)


# ---------------------------------------------------------------- umum

def test_semua_endpoint_wajib_login(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        anon = TestClient(app)
        for metode, url in [("get", "/api/stok/masuk"), ("get", "/api/stok/masuk/APL-1012"), ("post", "/api/stok/masuk"),
                            ("put", "/api/stok/masuk/APL-1012"), ("delete", "/api/stok/masuk/APL-1012"),
                            ("get", "/api/stok/keluar"), ("post", "/api/stok/keluar")]:
            assert getattr(anon, metode)(url).status_code == 401, (metode, url)
    finally:
        app.dependency_overrides.clear()


def test_pct3_sama_dengan_frontend():
    assert svc.pct3([24, 12, 4]) == [60, 30, 10]
    assert svc.pct3([22, 11, 3]) == [61, 31, 8]
    assert svc.pct3([1, 7, 0]) == [13, 87, 0]       # 12,5 dibulatkan ke atas seperti Math.round JavaScript
    assert svc.pct3([0, 0, 0]) == [0, 0, 0]
    for h in ([5, 3, 2], [1, 1, 1], [9, 0, 1], [33, 33, 34]):
        assert sum(svc.pct3(h)) == 100


# ---------------------------------------------------------------- daftar & detail

def test_daftar_masuk_data_contoh(client):
    r = client.get("/api/stok/masuk")
    assert r.status_code == 200
    data = r.json()
    assert [b["id"] for b in data] == ["AGR-1003", "JRK-1009", "APL-1012"]            # terbaru di atas
    by = {b["id"]: b for b in data}
    assert (by["AGR-1003"]["jumlah"], by["AGR-1003"]["sisa"]) == (12.0, 8.0)
    assert (by["JRK-1009"]["jumlah"], by["JRK-1009"]["sisa"]) == (35.0, 35.0)
    assert (by["APL-1012"]["jumlah"], by["APL-1012"]["sisa"]) == (30.0, 25.0)
    # Persen dihitung dari hitungan buah yang bulat: 36 buah tidak bisa persis 60/30/10 (jadi 22/11/3 = 61/31/8),
    # dan 45 buah tidak bisa persis 70/20/10 (jadi 32/9/4 = 71/20/9).
    assert by["AGR-1003"]["komposisi"] == [61, 31, 8] and by["AGR-1003"]["komposisiAwal"] == [70, 20, 10]
    assert by["JRK-1009"]["komposisi"] == [71, 20, 9] == by["JRK-1009"]["komposisiAwal"]
    assert by["APL-1012"]["komposisi"] == [60, 10, 30] and by["APL-1012"]["komposisiAwal"] == [70, 20, 10]
    assert set(by["APL-1012"]) == {"id", "buah", "jumlah", "sisa", "komposisi", "komposisiAwal", "masukPada"}


def test_waktu_berformat_wib(client):
    t = client.get("/api/stok/masuk").json()[0]["masukPada"]
    assert t.endswith("+07:00")
    datetime.fromisoformat(t)


def test_detail_dan_riwayat(client):
    d = client.get("/api/stok/masuk/AGR-1003").json()
    assert d["latin"] == "Vitis vinifera" and d["keluar"] == 4.0 and d["sisa"] == 8.0
    urutan = [(e["k"], e["sisa"]) for e in d["riwayat"]]
    assert urutan == [("in", 12.0), ("scan", None), ("out", 8.0), ("scan", None)]
    scans = [e for e in d["riwayat"] if e["k"] == "scan"]
    assert scans[0]["c"] == [70, 20, 10] and scans[0]["n"] == 40 and scans[0]["putaran"] == 1 and scans[0]["lapis"] == 4
    assert scans[1]["c"] == [61, 31, 8] and scans[1]["n"] == 36 and scans[1]["putaran"] == 2
    out = next(e for e in d["riwayat"] if e["k"] == "out")
    assert out["q"] == 4.0 and out["r"] == "Terbuang"


def test_detail_tidak_ditemukan(client):
    r = client.get("/api/stok/masuk/XXX-9999")
    assert r.status_code == 404 and r.json()["detail"] == "Kiriman tidak ditemukan"


# ---------------------------------------------------------------- tambah batch

def test_tambah_batch_dengan_hasil_scan(client, db):
    r = client.post("/api/stok/masuk", json={"buah": "Anggur", "jumlah": 10, "lapis": lapis([6, 3, 1], [8, 2, 0])})
    assert r.status_code == 201
    bid = r.json()["id"]
    assert bid == "AGR-1004"                                   # lanjut dari AGR-1003
    b = batch_by_id(client, bid)
    assert b["jumlah"] == 10.0 and b["sisa"] == 10.0
    assert b["komposisi"] == b["komposisiAwal"] == svc.pct3([14, 5, 1])
    scans = db.scalars(select(Scan).where(Scan.batch_id == bid).order_by(Scan.lapis_ke)).all()
    assert [(s.putaran, s.lapis_ke, len(s.hasil)) for s in scans] == [(1, 1, 10), (1, 2, 10)]
    assert all(h.keyakinan is None and h.bbox is None and h.buah == "Anggur" for s in scans for h in s.hasil)
    assert client.get("/api/stok/masuk").json()[0]["id"] == bid                      # terbaru di atas


def test_tambah_batch_dengan_kotak_menyimpan_bbox_dan_keyakinan(client, db):
    kotak = [{"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4, "k": 0, "keyakinan": 0.91},
             {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2, "k": 2}]
    r = client.post("/api/stok/masuk", json={"buah": "apel", "jumlah": 5.5,
                                             "lapis": [{"hitung": [1, 0, 1], "kotak": kotak}]})
    assert r.status_code == 201
    hasil = db.scalars(select(HasilScan).join(Scan).where(Scan.batch_id == r.json()["id"]).order_by(HasilScan.id)).all()
    assert [(h.kelas, h.keyakinan, h.bbox) for h in hasil] == [(0, 0.91, [0.1, 0.2, 0.3, 0.4]), (2, None, [0.5, 0.5, 0.2, 0.2])]


def test_tambah_batch_tanpa_scan_boleh(client):
    r = client.post("/api/stok/masuk", json={"buah": "Jeruk", "jumlah": 3})
    assert r.status_code == 201
    b = batch_by_id(client, r.json()["id"])
    assert b["komposisi"] is None and b["komposisiAwal"] is None


def test_kotak_kosong_dianggap_tidak_ada(client):
    r = client.post("/api/stok/masuk", json={"buah": "Jeruk", "jumlah": 3, "lapis": [{"hitung": [2, 1, 0], "kotak": []}]})
    assert r.status_code == 201


def test_nama_buah_dinormalisasi(client):
    r = client.post("/api/stok/masuk", json={"buah": "  aNGgur  ", "jumlah": "2.04"})
    assert r.status_code == 201 and r.json()["id"].startswith("AGR-")
    assert batch_by_id(client, r.json()["id"])["jumlah"] == 2.0          # dibulatkan ke 1 desimal


def test_nomor_batch_per_kode_dan_tidak_dipakai_ulang(client):
    a1 = client.post("/api/stok/masuk", json={"buah": "Apel", "jumlah": 1}).json()["id"]
    j1 = client.post("/api/stok/masuk", json={"buah": "Jeruk", "jumlah": 1}).json()["id"]
    assert (a1, j1) == ("APL-1013", "JRK-1010")
    assert client.delete(f"/api/stok/masuk/{a1}").status_code == 200
    a2 = client.post("/api/stok/masuk", json={"buah": "Apel", "jumlah": 1}).json()["id"]
    assert a2 == "APL-1014"


def test_nomor_bentrok_dilaporkan_sebagai_409(client, db):
    """Penghitung tertinggal dari batch yang sudah ada (mis. data dimasukkan manual)."""
    db.get(BatchCounter, "AGR").last_no = 1002                  # AGR-1003 sudah ada
    db.commit()
    r = client.post("/api/stok/masuk", json={"buah": "Anggur", "jumlah": 1})
    assert r.status_code == 409 and r.json()["detail"] == "Nomor batch bentrok, silakan coba lagi"
    assert db.scalar(select(func.count()).select_from(Batch).where(Batch.buah == "Anggur")) == 1


def test_migrasi_belum_dijalankan_diberi_petunjuk_jelas(client, db, monkeypatch):
    """Kolom keyakinan masih NOT NULL (migrasi 0002 belum jalan) tidak boleh dilaporkan sebagai 'nomor bentrok'."""
    def gagal():
        raise IntegrityError("INSERT ...", {}, Exception('null value in column "keyakinan" violates not-null constraint'))
    monkeypatch.setattr(db, "commit", gagal)
    r = client.post("/api/stok/masuk", json={"buah": "Anggur", "jumlah": 1, "lapis": lapis([1, 0, 0])})
    assert r.status_code == 500
    assert "alembic upgrade head" in r.json()["detail"] and "bentrok" not in r.json()["detail"]


def test_kegagalan_lain_tidak_disamarkan(client, db, monkeypatch):
    def gagal():
        raise IntegrityError("INSERT ...", {}, Exception("sesuatu yang lain"))
    monkeypatch.setattr(db, "commit", gagal)
    with pytest.raises(IntegrityError):
        client.post("/api/stok/masuk", json={"buah": "Anggur", "jumlah": 1})


def test_penghitung_dibuat_otomatis_jika_belum_ada(client, db):
    db.delete(db.get(BatchCounter, "AGR"))
    db.commit()
    bid = client.post("/api/stok/masuk", json={"buah": "Anggur", "jumlah": 1}).json()["id"]
    assert bid == "AGR-1001"


@pytest.mark.parametrize("badan", [
    {"buah": "Mangga", "jumlah": 5},
    {"buah": "", "jumlah": 5},
    {"buah": "Apel", "jumlah": 0},
    {"buah": "Apel", "jumlah": -3},
    {"buah": "Apel", "jumlah": 0.04},                    # dibulatkan jadi 0.0
    {"buah": "Apel", "jumlah": 100000.1},
    {"buah": "Apel", "jumlah": "abc"},
    {"buah": "Apel", "jumlah": "NaN"},
    {"buah": "Apel"},
    {"jumlah": 5},
    {"buah": "Apel", "jumlah": 5, "lapis": [{"hitung": [0, 0, 0]}]},
    {"buah": "Apel", "jumlah": 5, "lapis": [{"hitung": [1, 2]}]},
    {"buah": "Apel", "jumlah": 5, "lapis": [{"hitung": [-1, 2, 1]}]},
    {"buah": "Apel", "jumlah": 5, "lapis": [{"hitung": [501, 0, 0]}]},
    {"buah": "Apel", "jumlah": 5, "lapis": [{"hitung": [1, 1, 0], "kotak": [{"x": 0, "y": 0, "w": 1, "h": 1, "k": 0}]}]},
    {"buah": "Apel", "jumlah": 5, "lapis": [{"hitung": [1, 0, 0], "kotak": [{"x": 2, "y": 0, "w": 1, "h": 1, "k": 0}]}]},
    {"buah": "Apel", "jumlah": 5, "lapis": [{"hitung": [1, 0, 0], "kotak": [{"x": 0, "y": 0, "w": 1, "h": 1, "k": 5}]}]},
    {"buah": "Apel", "jumlah": 5, "lapis": [{"hitung": [1, 0, 0]}] * 201},
])
def test_tambah_batch_ditolak(client, badan):
    r = client.post("/api/stok/masuk", json=badan)
    assert r.status_code == 422, r.text
    assert len(client.get("/api/stok/masuk").json()) == 3          # tidak ada batch yang tersimpan


# ---------------------------------------------------------------- ubah batch

def test_ubah_jumlah(client):
    assert client.put("/api/stok/masuk/APL-1012", json={"buah": "Apel", "jumlah": 40}).json() == {"ok": True}
    b = batch_by_id(client, "APL-1012")
    assert (b["jumlah"], b["sisa"]) == (40.0, 35.0)


def test_ubah_jumlah_tidak_boleh_di_bawah_yang_sudah_keluar(client):
    r = client.put("/api/stok/masuk/AGR-1003", json={"buah": "Anggur", "jumlah": 3.9})
    assert r.status_code == 400
    assert r.json()["detail"] == "Jumlah tidak boleh di bawah stok yang sudah keluar (4 kg)"
    assert client.put("/api/stok/masuk/AGR-1003", json={"buah": "Anggur", "jumlah": 4}).status_code == 200
    assert batch_by_id(client, "AGR-1003")["sisa"] == 0.0


def test_jenis_buah_tidak_bisa_diubah(client):
    r = client.put("/api/stok/masuk/APL-1012", json={"buah": "Jeruk", "jumlah": 30})
    assert r.status_code == 400 and "tidak bisa diubah" in r.json()["detail"]
    assert batch_by_id(client, "APL-1012")["buah"] == "Apel"


def test_ubah_tidak_ditemukan_atau_tidak_valid(client):
    assert client.put("/api/stok/masuk/ZZZ-1", json={"buah": "Apel", "jumlah": 5}).status_code == 404
    assert client.put("/api/stok/masuk/APL-1012", json={"buah": "Apel", "jumlah": 0}).status_code == 422


# ---------------------------------------------------------------- hapus batch

def test_hapus_lunak(client, db):
    assert client.delete("/api/stok/masuk/AGR-1003").json() == {"ok": True}
    assert "AGR-1003" not in [b["id"] for b in client.get("/api/stok/masuk").json()]
    assert client.get("/api/stok/masuk/AGR-1003").status_code == 404
    assert client.delete("/api/stok/masuk/AGR-1003").status_code == 404
    assert client.put("/api/stok/masuk/AGR-1003", json={"buah": "Anggur", "jumlah": 5}).status_code == 404
    row = db.get(Batch, "AGR-1003")
    assert row is not None and row.deleted_at is not None                       # masih ada di database
    assert db.scalar(select(func.count()).select_from(Scan).where(Scan.batch_id == "AGR-1003")) > 0


def test_batch_terhapus_hilang_dari_stok_keluar_dan_tidak_bisa_dikeluarkan(client):
    assert len(client.get("/api/stok/keluar").json()) == 2          # AGR-1003 (4 kg) dan APL-1012 (5 kg)
    client.delete("/api/stok/masuk/AGR-1003")
    keluar = client.get("/api/stok/keluar").json()
    assert [(k["buah"], k["jumlah"]) for k in keluar] == [("Apel", 5.0)]
    r = client.post("/api/stok/keluar", json={"buah": "Anggur", "jumlah": 1, "alasan": "Terjual"})
    assert r.status_code == 400 and r.json()["detail"] == "Stok Anggur hanya tersisa 0 kg"


# ---------------------------------------------------------------- stok keluar

def test_keluar_fifo_lintas_batch(client, db):
    baru = client.post("/api/stok/masuk", json={"buah": "Anggur", "jumlah": 10}).json()["id"]
    r = client.post("/api/stok/keluar", json={"buah": "Anggur", "jumlah": 10, "alasan": "Terjual"})
    assert r.status_code == 201
    assert r.json()["diambil"] == [{"batch": "AGR-1003", "jumlah": 8.0}, {"batch": baru, "jumlah": 2.0}]
    assert batch_by_id(client, "AGR-1003")["sisa"] == 0.0 and batch_by_id(client, baru)["sisa"] == 8.0
    rows = db.scalars(select(StockOut).where(StockOut.gid == r.json()["gid"])).all()
    assert len(rows) == 2 and {x.alasan for x in rows} == {"Terjual"}
    terbaru = client.get("/api/stok/keluar").json()[0]
    assert terbaru == {**terbaru, "gid": r.json()["gid"], "buah": "Anggur", "jumlah": 10.0, "alasan": "Terjual"}
    assert len(client.get("/api/stok/keluar").json()) == 3


def test_keluar_mengambil_dari_yang_tertua_bukan_dari_id(client):
    a = client.post("/api/stok/masuk", json={"buah": "Apel", "jumlah": 5}).json()["id"]      # APL-1013, paling baru
    client.post("/api/stok/keluar", json={"buah": "Apel", "jumlah": 3, "alasan": "Terjual"})
    assert batch_by_id(client, "APL-1012")["sisa"] == 22.0 and batch_by_id(client, a)["sisa"] == 5.0


def test_keluar_melebihi_stok_ditolak_dan_tidak_menyimpan_apa_pun(client, db):
    sebelum = db.scalar(select(func.count()).select_from(StockOut))
    r = client.post("/api/stok/keluar", json={"buah": "Apel", "jumlah": 25.1, "alasan": "Terjual"})
    assert r.status_code == 400 and r.json()["detail"] == "Stok Apel hanya tersisa 25 kg"
    assert db.scalar(select(func.count()).select_from(StockOut)) == sebelum


def test_keluar_tepat_sebesar_sisa_lalu_habis(client):
    assert client.post("/api/stok/keluar", json={"buah": "Apel", "jumlah": 25, "alasan": "Terbuang"}).status_code == 201
    assert batch_by_id(client, "APL-1012")["sisa"] == 0.0
    r = client.post("/api/stok/keluar", json={"buah": "Apel", "jumlah": 0.1, "alasan": "Terbuang"})
    assert r.status_code == 400 and r.json()["detail"] == "Stok Apel hanya tersisa 0 kg"


def test_keluar_desimal_tidak_menimbulkan_selisih(client):
    for _ in range(3):
        assert client.post("/api/stok/keluar", json={"buah": "Jeruk", "jumlah": 0.1, "alasan": "Terjual"}).status_code == 201
    assert batch_by_id(client, "JRK-1009")["sisa"] == 34.7
    assert client.post("/api/stok/keluar", json={"buah": "Jeruk", "jumlah": 34.7, "alasan": "Terjual"}).status_code == 201
    assert batch_by_id(client, "JRK-1009")["sisa"] == 0.0


def test_keluar_melewati_batch_yang_sisanya_nol(client):
    client.post("/api/stok/keluar", json={"buah": "Anggur", "jumlah": 8, "alasan": "Terjual"})      # AGR-1003 habis
    baru = client.post("/api/stok/masuk", json={"buah": "Anggur", "jumlah": 5}).json()["id"]
    r = client.post("/api/stok/keluar", json={"buah": "Anggur", "jumlah": 2, "alasan": "Terjual"})
    assert r.json()["diambil"] == [{"batch": baru, "jumlah": 2.0}]


@pytest.mark.parametrize("badan", [
    {"buah": "Apel", "jumlah": 0, "alasan": "Terjual"},
    {"buah": "Apel", "jumlah": -1, "alasan": "Terjual"},
    {"buah": "Apel", "jumlah": 1, "alasan": "Dicuri"},
    {"buah": "Apel", "jumlah": 1},
    {"buah": "Mangga", "jumlah": 1, "alasan": "Terjual"},
    {"buah": "Apel", "jumlah": "x", "alasan": "Terjual"},
])
def test_keluar_validasi(client, badan):
    assert client.post("/api/stok/keluar", json=badan).status_code == 422


def test_stok_keluar_tercatat_siapa_pelakunya(client, db):
    gid = client.post("/api/stok/keluar", json={"buah": "Jeruk", "jumlah": 1, "alasan": "Terjual"}).json()["gid"]
    pelaku = db.scalar(select(StockOut.created_by).where(StockOut.gid == gid))
    assert pelaku == db.scalar(select(User.id).where(User.username == "uji"))


# ---------------------------------------------------------------- balapan (hanya di PostgreSQL)

@pytest.mark.skipif(not PG, reason="uji konkurensi butuh PostgreSQL (set TEST_DATABASE_URL)")
def test_keluar_bersamaan_tidak_membuat_stok_minus(engine):
    Sesi = sessionmaker(bind=engine, expire_on_commit=False)
    with Sesi() as s:
        seed(s, reset=True)
        user = User(nama="x", username="x", email="x@x.id", role="admin", password_hash="h")
        s.add(user)
        s.commit()
        uid = user.id
    hasil, kunci = [], threading.Lock()

    def kerja():
        with Sesi() as s:
            try:
                svc.catat_keluar(s, s.get(User, uid), "Apel", Decimal("5"), "Terjual")      # sisa Apel 25 kg
                ok = True
            except svc.StokError:
                ok = False
        with kunci:
            hasil.append(ok)

    threads = [threading.Thread(target=kerja) for _ in range(10)]          # 10 x 5 kg, stok hanya cukup 5 kali
    [t.start() for t in threads]
    [t.join() for t in threads]
    with Sesi() as s:
        total_keluar = s.scalar(select(func.sum(StockOut.qty_kg)).where(StockOut.batch_id == "APL-1012"))
    assert hasil.count(True) == 5 and hasil.count(False) == 5
    assert total_keluar == Decimal("30.0")                                   # 5 (seed) + 25, tepat habis


@pytest.mark.skipif(not PG, reason="uji konkurensi butuh PostgreSQL (set TEST_DATABASE_URL)")
def test_nomor_batch_unik_saat_dibuat_bersamaan(engine):
    Sesi = sessionmaker(bind=engine, expire_on_commit=False)
    with Sesi() as s:
        seed(s, reset=True)
        user = User(nama="x", username="x", email="x@x.id", role="admin", password_hash="h")
        s.add(user)
        s.commit()
        uid = user.id
    ids, kunci = [], threading.Lock()

    def kerja():
        with Sesi() as s:
            bid = svc.buat_batch(s, s.get(User, uid), "Apel", Decimal("1"), None)
        with kunci:
            ids.append(bid)

    threads = [threading.Thread(target=kerja) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(set(ids)) == 12
    assert sorted(ids)[0] == "APL-1013" and sorted(ids)[-1] == "APL-1024"
