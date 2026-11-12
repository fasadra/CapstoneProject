# Tahap 3 — Akun (daftar, masuk, keluar, profil, ganti sandi)

## Letak file (timpa yang lama / tambah yang baru)

Salin isi zip ke folder proyek (yang berisi `backend/` dan `frontend/`), pilih "Replace" bila ditanya.

| File | Aksi |
|---|---|
| `backend/requirements.txt` | timpa (menambah argon2-cffi, itsdangerous) |
| `backend/app/config.py` | timpa |
| `backend/app/main.py` | timpa |
| `backend/app/security.py` | baru |
| `backend/app/schemas.py` | baru |
| `backend/app/deps.py` | baru |
| `backend/app/ratelimit.py` | baru |
| `backend/app/routers/__init__.py`, `auth.py` | baru (folder `routers` baru) |
| `backend/tests/test_auth.py` | baru |
| `frontend/js/api.js`, `common.js`, `dashboard.js`, `login.js`, `register.js` | timpa |
| `.env.example` | timpa (hanya contoh; file `.env`-mu sendiri tidak disentuh) |

## Langkah

1. `cd backend`, aktifkan `.venv`, lalu `pip install -r requirements.txt`.
2. Buat kunci rahasia: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   Tempel hasilnya di file `.env` (folder induk) pada baris `SECRET_KEY=`.
3. Tidak ada migrasi baru (tabel `users` sudah ada sejak Tahap 2).
4. Jalankan `uvicorn app.main:app --reload`, lalu buka http://localhost:8000/ (jangan buka file HTML langsung).
5. Tes otomatis: `python -m pytest -q` -> 94 passed.

## Endpoint baru

POST /api/auth/register · POST /api/auth/login · POST /api/auth/logout · GET /api/me
GET/PUT /api/profil · POST /api/profil/sandi   (lihat http://localhost:8000/docs)

## Aturan

- Akun pertama yang mendaftar = Admin, berikutnya = Staf.
- Sandi disimpan sebagai hash argon2. Sesi = cookie HttpOnly bertanda tangan, berlaku 12 jam.
- 5 kali salah sandi dari alamat yang sama untuk email yang sama = diblokir 15 menit.
- Ganti sandi mengeluarkan sesi di perangkat lain.
