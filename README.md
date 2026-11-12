# FreshSense AI — Backend (Tahap 1–2)

Isi tahap ini: struktur proyek, database PostgreSQL (Docker), FastAPI yang menyajikan frontend,
skema database + migrasi Alembic, data contoh (Apel, Jeruk, Anggur), dan pengujian otomatis.
Halaman web **belum** memakai API (itu Tahap 4–5); frontend masih memakai `localStorage` seperti sekarang.

## Susunan folder

```
freshsense/
├── frontend/              <- isi folder "Capstone Project" milikmu (landing.html, css/, js/, img/, ...)
├── backend/
│   ├── app/               <- kode aplikasi (config, models, database, main)
│   ├── alembic/           <- migrasi database
│   ├── tests/             <- pengujian
│   ├── seed.py            <- data contoh
│   ├── requirements.txt
│   ├── alembic.ini
│   └── pytest.ini
├── docker-compose.yml     <- database Postgres
├── .env.example           <- salin jadi .env
├── .gitignore
└── README.md
```

## Menjalankan (dari awal)

Prasyarat: Python 3.12, Docker Desktop.

```bash
# 1. dari folder freshsense/
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
#    buka .env, ganti sandi (POSTGRES_PASSWORD) dan samakan di DATABASE_URL

# 2. nyalakan database
docker compose up -d

# 3. dari folder backend/
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. buat tabel + isi data contoh
alembic upgrade head
python seed.py

# 5. jalankan server
uvicorn app.main:app --reload
```

Buka http://localhost:8000 (halaman web), http://localhost:8000/docs (dokumentasi API),
http://localhost:8000/api/health (harus `{"status":"ok","db":true}`).

## Perintah yang sering dipakai

| Tujuan | Perintah (dari `backend/`) |
|---|---|
| Jalankan tes | `python -m pytest -q` |
| Tes ke Postgres asli | `TEST_DATABASE_URL=postgresql+psycopg://user:sandi@localhost:5432/freshsense_test python -m pytest -q` |
| Isi ulang data contoh | `python seed.py --reset` (menghapus data stok & scan) |
| Cek model dan migrasi sinkron | `alembic check` |
| Buat migrasi setelah mengubah `models.py` | `alembic revision --autogenerate -m "pesan"` lalu **baca** hasilnya, lalu `alembic upgrade head` |
| Mundurkan satu migrasi | `alembic downgrade -1` |

## Keputusan desain yang tertanam di skema

- Buah hanya **Apel, Jeruk, Anggur** (CHECK di `batches` dan `hasil_scan`).
- **Satu scan = satu foto = satu lapis.** `putaran` = satu kali pemotretan penuh semua lapis batch.
  Komposisi terkini batch = jumlah buah per kelas dari putaran terbaru; komposisi awal = putaran 1.
- Kelas: 0 segar, 1 kurang segar, 2 busuk.
- Waktu disimpan UTC (`timestamptz`); data contoh dihitung menurut jam WIB.
- Batch dihapus lunak (`deleted_at`); `stock_out` dan `scans` tidak ikut terhapus.
