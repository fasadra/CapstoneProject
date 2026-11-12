"""Pengujian akun: daftar, masuk, keluar, sesi, profil, ganti sandi, pembatas percobaan."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import User
from app.ratelimit import limiter
from app.routers.auth import buat_username
from app.security import make_session_token, secret_is_weak

PW = "SandiBagus123"


@pytest.fixture()
def client(db):
    limiter.clear()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.clear()


def daftar(c, email="budi@toko.id", password=PW):
    return c.post("/api/auth/register", json={"email": email, "password": password})


def masuk(c, email="budi@toko.id", password=PW):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def akun_login(client, email="budi@toko.id"):
    daftar(client, email)
    assert masuk(client, email).status_code == 200
    return client


# ---------------------------------------------------------------- daftar

def test_akun_pertama_admin_berikutnya_staf(client):
    r1 = daftar(client, "a@toko.id")
    r2 = daftar(client, "b@toko.id")
    assert r1.status_code == 201 and r1.json()["role"] == "Admin"
    assert r2.status_code == 201 and r2.json()["role"] == "Staf"


def test_email_ganda_ditolak_tanpa_peduli_huruf_besar(client):
    assert daftar(client, "budi@toko.id").status_code == 201
    r = daftar(client, "  BUDI@Toko.ID ")
    assert r.status_code == 409
    assert r.json()["detail"] == "Email sudah terdaftar"


@pytest.mark.parametrize("email,pw", [
    ("bukan-email", PW), ("a@b", PW), ("budi@toko.id", "pendek"), ("budi@toko.id", "x" * 129),
])
def test_validasi_daftar(client, email, pw):
    assert daftar(client, email, pw).status_code == 422


def test_sandi_disimpan_sebagai_hash_argon2(client, db):
    daftar(client)
    u = db.scalar(select(User))
    assert u.password_hash.startswith("$argon2")
    assert PW not in u.password_hash


def test_username_dan_nama_awal_dari_email(client, db):
    daftar(client, "Budi.Santoso@toko.id")
    u = db.scalar(select(User))
    assert u.username == "budi.santoso" and u.nama == "Budi Santoso"


def test_username_unik_dan_valid(db):
    import re
    for i in range(3):
        name = buat_username(db, "budi@toko.id")
        db.add(User(nama="x", username=name, email=f"e{i}@x.id", password_hash="h"))
        db.flush()
    names = list(db.scalars(select(User.username)))
    assert len(set(names)) == 3
    assert all(re.fullmatch(r"[A-Za-z0-9_.]{3,20}", n) for n in names)
    assert re.fullmatch(r"[A-Za-z0-9_.]{3,20}", buat_username(db, "a@x.id"))
    assert re.fullmatch(r"[A-Za-z0-9_.]{3,20}", buat_username(db, "!!!!!@x.id"))


# ---------------------------------------------------------------- masuk / sesi

def test_login_sukses_set_cookie_aman_dan_me_bisa_dibaca(client):
    daftar(client)
    r = masuk(client)
    assert r.status_code == 200
    assert r.json()["email"] == "budi@toko.id" and r.json()["role"] == "Admin"
    sc = r.headers["set-cookie"].lower()
    assert settings.cookie_name in sc and "httponly" in sc and "samesite=lax" in sc
    me = client.get("/api/me")
    assert me.status_code == 200 and me.json()["username"] == "budi"
    assert "password" not in me.text and "hash" not in me.text


def test_tanpa_login_ditolak(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/profil").status_code == 401
    assert client.put("/api/profil", json={}).status_code == 401
    assert client.post("/api/profil/sandi", json={"lama": "a", "baru": "b" * 8}).status_code == 401


def test_login_gagal_pesan_sama_untuk_email_tak_ada_dan_sandi_salah(client):
    daftar(client)
    salah = masuk(client, password="SandiSalah999")
    tak_ada = masuk(client, email="hantu@toko.id")
    assert salah.status_code == tak_ada.status_code == 401
    assert salah.json() == tak_ada.json() == {"detail": "Email atau kata sandi salah"}
    assert "set-cookie" not in salah.headers


def test_login_email_tidak_peduli_huruf_besar(client):
    daftar(client)
    assert masuk(client, email=" BUDI@TOKO.ID ").status_code == 200


def test_pembatas_percobaan_gagal(client):
    daftar(client)
    for _ in range(5):
        assert masuk(client, password="salah-salah").status_code == 401
    r = masuk(client, password="salah-salah")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert masuk(client).status_code == 429              # sandi benar pun ditahan selama diblokir
    assert masuk(client, email="lain@toko.id").status_code == 401   # email lain tidak ikut terblokir


def test_login_sukses_mereset_hitungan_gagal(client):
    daftar(client)
    for _ in range(4):
        masuk(client, password="salah-salah")
    assert masuk(client).status_code == 200
    for _ in range(4):
        assert masuk(client, password="salah-salah").status_code == 401


def test_logout_menghapus_sesi(client):
    akun_login(client)
    assert client.get("/api/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_cookie_palsu_rusak_atau_kedaluwarsa_ditolak(client, db, monkeypatch):
    akun_login(client)
    u = db.scalar(select(User))
    token = make_session_token(u.id, u.password_hash)

    client.cookies.set(settings.cookie_name, "sampah.bukan.token")
    assert client.get("/api/me").status_code == 401

    monkeypatch.setattr(settings, "secret_key", "kunci-lain-" * 5)   # ditandatangani kunci berbeda
    client.cookies.set(settings.cookie_name, token)
    assert client.get("/api/me").status_code == 401
    monkeypatch.undo()

    client.cookies.set(settings.cookie_name, token)
    assert client.get("/api/me").status_code == 200
    monkeypatch.setattr(settings, "session_hours", -1)               # semua token dianggap kedaluwarsa
    assert client.get("/api/me").status_code == 401


def test_token_pengguna_terhapus_ditolak(client, db):
    akun_login(client)
    db.delete(db.scalar(select(User)))
    db.commit()
    assert client.get("/api/me").status_code == 401


# ---------------------------------------------------------------- profil

PROFIL = {"nama": "Budi Santoso", "username": "budi.s", "email": "budi.baru@toko.id", "telepon": "0812-3456-7890"}


def test_ubah_profil(client):
    akun_login(client)
    r = client.put("/api/profil", json=PROFIL)
    assert r.status_code == 200
    assert r.json() == {**PROFIL, "role": "Admin"}
    assert client.get("/api/profil").json() == {**PROFIL, "role": "Admin"}
    # email baru dipakai untuk masuk
    client.post("/api/auth/logout")
    assert masuk(client, email="budi.baru@toko.id").status_code == 200


def test_role_tidak_bisa_diubah_lewat_profil(client):
    daftar(client, "pertama@toko.id")
    daftar(client, "staf@toko.id")
    c = TestClient(app)
    masuk(c, "staf@toko.id")
    r = c.put("/api/profil", json={**PROFIL, "role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "Staf"


def test_profil_bentrok_email_atau_username(client):
    daftar(client, "pertama@toko.id")
    akun_login(client, "kedua@toko.id")
    r = client.put("/api/profil", json={**PROFIL, "email": "pertama@toko.id"})
    assert r.status_code == 409 and "Email" in r.json()["detail"]
    r = client.put("/api/profil", json={**PROFIL, "username": "PERTAMA"})
    assert r.status_code == 409 and "Username" in r.json()["detail"]


def test_profil_boleh_menyimpan_data_sendiri_tanpa_bentrok(client):
    akun_login(client)
    assert client.put("/api/profil", json=PROFIL).status_code == 200
    assert client.put("/api/profil", json=PROFIL).status_code == 200


@pytest.mark.parametrize("ubah", [
    {"username": "ab"}, {"username": "ada spasi"}, {"username": "x" * 21},
    {"email": "salah"}, {"telepon": "123"}, {"telepon": "abc12345678"}, {"nama": ""},
])
def test_validasi_profil(client, ubah):
    akun_login(client)
    assert client.put("/api/profil", json={**PROFIL, **ubah}).status_code == 422


# ---------------------------------------------------------------- ganti sandi

def test_ganti_sandi_sukses(client):
    akun_login(client)
    r = client.post("/api/profil/sandi", json={"lama": PW, "baru": "SandiBaru456"})
    assert r.status_code == 200
    assert client.get("/api/me").status_code == 200          # sesi ini tetap sah
    client.post("/api/auth/logout")
    assert masuk(client, password=PW).status_code == 401
    assert masuk(client, password="SandiBaru456").status_code == 200


def test_ganti_sandi_mengeluarkan_sesi_lain(client):
    akun_login(client)
    perangkat_lain = TestClient(app)
    assert masuk(perangkat_lain).status_code == 200
    assert perangkat_lain.get("/api/me").status_code == 200
    client.post("/api/profil/sandi", json={"lama": PW, "baru": "SandiBaru456"})
    assert perangkat_lain.get("/api/me").status_code == 401


def test_ganti_sandi_ditolak(client):
    akun_login(client)
    salah = client.post("/api/profil/sandi", json={"lama": "salah-banget", "baru": "SandiBaru456"})
    assert salah.status_code == 400 and salah.json()["detail"] == "Kata sandi lama salah"   # 400, bukan 401
    sama = client.post("/api/profil/sandi", json={"lama": PW, "baru": PW})
    assert sama.status_code == 400
    pendek = client.post("/api/profil/sandi", json={"lama": PW, "baru": "pendek"})
    assert pendek.status_code == 422
    assert client.get("/api/me").status_code == 200


def test_ganti_sandi_dibatasi_percobaan_gagal(client):
    akun_login(client)
    for _ in range(5):
        assert client.post("/api/profil/sandi", json={"lama": "salah-salah", "baru": "SandiBaru456"}).status_code == 400
    assert client.post("/api/profil/sandi", json={"lama": PW, "baru": "SandiBaru456"}).status_code == 429


# ---------------------------------------------------------------- kunci rahasia

def test_deteksi_kunci_lemah(monkeypatch):
    for lemah in ("ganti-di-env", "ganti-dengan-nilai-acak", "pendek"):
        monkeypatch.setattr(settings, "secret_key", lemah)
        assert secret_is_weak()
    monkeypatch.setattr(settings, "secret_key", "x" * 48)
    assert not secret_is_weak()
