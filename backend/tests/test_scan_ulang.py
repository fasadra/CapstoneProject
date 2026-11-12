"""Pengujian scan ulang / putaran baru (Tahap 6A)."""
import os
import threading
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import HasilScan, Scan, User
from app.security import hash_password, make_session_token
from app.services import stok as svc
from seed import seed

HASH = hash_password("SandiBagus123")
PG = not os.environ.get("TEST_DATABASE_URL", "sqlite://").startswith("sqlite")


@pytest.fixture()
def client(db):
    """Data contoh: AGR-1003 (putaran 1 dan 2), JRK-1009 (putaran 1), APL-1012 (putaran 1 dan 2)."""
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
    return {"lapis": [{"hitung": list(h)} for h in hitung]}


def batch(c, bid):
    return next(b for b in c.get("/api/stok/masuk").json() if b["id"] == bid)


def notif_ids(c):
    return [n["id"] for n in c.get("/api/notifications").json()]


def test_wajib_login(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        assert TestClient(app).post("/api/stok/masuk/AGR-1003/scan", json=lapis([1, 0, 0])).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_pindai_ulang_membuat_putaran_baru(client, db):
    r = client.post("/api/stok/masuk/AGR-1003/scan", json=lapis([9, 1, 0], [8, 2, 0]))
    assert r.status_code == 201
    assert r.json() == {"putaran": 3, "lapis": 2, "lapisSebelumnya": 4,
                        "komposisi": [85, 15, 0], "komposisiSebelumnya": [61, 31, 8]}
    b = batch(client, "AGR-1003")
    assert b["komposisi"] == [85, 15, 0] and b["komposisiAwal"] == [70, 20, 10]       # awal tidak berubah
    rows = db.scalars(select(Scan).where(Scan.batch_id == "AGR-1003", Scan.putaran == 3).order_by(Scan.lapis_ke)).all()
    assert [(s.lapis_ke, len(s.hasil)) for s in rows] == [(1, 10), (2, 10)]
    assert all(h.buah == "Anggur" and h.keyakinan is None for s in rows for h in s.hasil)


def test_riwayat_menampilkan_putaran_baru(client):
    client.post("/api/stok/masuk/AGR-1003/scan", json=lapis([9, 1, 0], [8, 2, 0]))
    d = client.get("/api/stok/masuk/AGR-1003").json()
    assert [e["k"] for e in d["riwayat"]] == ["in", "scan", "out", "scan", "scan"]
    terakhir = d["riwayat"][-1]
    assert (terakhir["putaran"], terakhir["lapis"], terakhir["n"], terakhir["c"]) == (3, 2, 20, [85, 15, 0])


def test_putaran_berturut_turut(client):
    for harapan in (3, 4, 5):
        r = client.post("/api/stok/masuk/AGR-1003/scan", json=lapis([5, 0, 0]))
        assert r.json()["putaran"] == harapan
    assert client.post("/api/stok/masuk/AGR-1003/scan", json=lapis([5, 0, 0])).json()["lapisSebelumnya"] == 1


def test_pindai_pertama_kali_untuk_kiriman_tanpa_scan(client):
    bid = client.post("/api/stok/masuk", json={"buah": "Jeruk", "jumlah": 4}).json()["id"]
    assert batch(client, bid)["komposisi"] is None
    r = client.post(f"/api/stok/masuk/{bid}/scan", json=lapis([3, 1, 0]))
    assert r.json() == {"putaran": 1, "lapis": 1, "lapisSebelumnya": None,
                        "komposisi": [75, 25, 0], "komposisiSebelumnya": None}
    assert batch(client, bid)["komposisi"] == batch(client, bid)["komposisiAwal"] == [75, 25, 0]


def test_notifikasi_mengikuti_scan_terbaru(client):
    assert notif_ids(client) == ["AGR-1003|kurang|2", "APL-1012|busuk|2"]
    client.post("/api/notifications/baca-semua")
    # kondisi membaik -> notifikasi AGR hilang
    client.post("/api/stok/masuk/AGR-1003/scan", json=lapis([10, 0, 0]))
    assert notif_ids(client) == ["APL-1012|busuk|2"]
    # kondisi memburuk -> notifikasi baru (putaran baru) dan BELUM dibaca
    client.post("/api/stok/masuk/AGR-1003/scan", json=lapis([2, 4, 4]))
    data = {n["id"]: n for n in client.get("/api/notifications").json()}
    assert set(data) == {"AGR-1003|busuk|4", "AGR-1003|kurang|4", "APL-1012|busuk|2"}
    assert data["AGR-1003|busuk|4"]["dibaca"] is False and data["APL-1012|busuk|2"]["dibaca"] is True
    assert (data["AGR-1003|busuk|4"]["persen"], data["AGR-1003|busuk|4"]["kg"]) == (40, 3.2)       # sisa 8 kg x 40%


def test_stok_habis_tidak_bisa_dipindai(client):
    assert client.post("/api/stok/keluar", json={"buah": "Apel", "jumlah": 25, "alasan": "Terjual"}).status_code == 201
    r = client.post("/api/stok/masuk/APL-1012/scan", json=lapis([5, 0, 0]))
    assert r.status_code == 400 and r.json()["detail"] == "Stok kiriman ini sudah habis, tidak perlu dipindai ulang"


def test_tidak_ditemukan_atau_dihapus(client):
    assert client.post("/api/stok/masuk/XXX-0000/scan", json=lapis([1, 0, 0])).status_code == 404
    client.delete("/api/stok/masuk/JRK-1009")
    assert client.post("/api/stok/masuk/JRK-1009/scan", json=lapis([1, 0, 0])).status_code == 404


def test_kotak_menyimpan_bbox_dan_keyakinan(client, db):
    kotak = [{"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4, "k": 1, "keyakinan": 0.8}]
    r = client.post("/api/stok/masuk/JRK-1009/scan", json={"lapis": [{"hitung": [0, 1, 0], "kotak": kotak}]})
    assert r.status_code == 201
    h = db.scalar(select(HasilScan).join(Scan).where(Scan.batch_id == "JRK-1009", Scan.putaran == 2))
    assert (h.kelas, h.keyakinan, h.bbox) == (1, 0.8, [0.1, 0.2, 0.3, 0.4])


@pytest.mark.parametrize("badan", [
    {}, {"lapis": []}, {"lapis": [{"hitung": [0, 0, 0]}]}, {"lapis": [{"hitung": [1, 2]}]},
    {"lapis": [{"hitung": [-1, 2, 1]}]}, {"lapis": [{"hitung": [501, 0, 0]}]},
    {"lapis": [{"hitung": [1, 1, 0], "kotak": [{"x": 0, "y": 0, "w": 1, "h": 1, "k": 0}]}]},
    {"lapis": [{"hitung": [1, 0, 0]}] * 201},
])
def test_validasi(client, badan):
    sebelum = client.get("/api/stok/masuk/AGR-1003").json()["riwayat"]
    assert client.post("/api/stok/masuk/AGR-1003/scan", json=badan).status_code == 422
    assert client.get("/api/stok/masuk/AGR-1003").json()["riwayat"] == sebelum        # tidak ada yang tersimpan


def test_jumlah_scan_hari_ini_dan_analisis_ikut_bertambah(client):
    s0 = client.get("/api/dashboard/summary").json()["scanHariIni"]
    a0 = sum(client.get("/api/analisis", params={"period": "minggu"}).json()["scan"])
    client.post("/api/stok/masuk/AGR-1003/scan", json=lapis([9, 1, 0], [8, 2, 0], [7, 3, 0]))
    assert client.get("/api/dashboard/summary").json()["scanHariIni"] == s0 + 3
    assert sum(client.get("/api/analisis", params={"period": "minggu"}).json()["scan"]) == a0 + 3


@pytest.mark.skipif(not PG, reason="uji konkurensi butuh PostgreSQL (set TEST_DATABASE_URL)")
def test_pindai_bersamaan_mendapat_putaran_berbeda(engine):
    Sesi = sessionmaker(bind=engine, expire_on_commit=False)
    with Sesi() as s:
        seed(s, reset=True)
        user = User(nama="x", username="x", email="x@x.id", role="admin", password_hash="h")
        s.add(user)
        s.commit()
        uid = user.id
    from app.schemas_stok import LapisIn
    hasil, kunci = [], threading.Lock()

    def kerja():
        with Sesi() as s:
            try:
                r = svc.pindai_ulang(s, s.get(User, uid), "AGR-1003", [LapisIn(hitung=[5, 0, 0])])
                ok = r["putaran"]
            except Exception as e:                                           # noqa: BLE001
                ok = repr(e)
        with kunci:
            hasil.append(ok)

    threads = [threading.Thread(target=kerja) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(hasil) == [3, 4, 5, 6, 7, 8]
