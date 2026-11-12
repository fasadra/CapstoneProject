# Tahap 4b — Dashboard, analisis, laporan, notifikasi

## Letak file (timpa / tambah)

| File | Aksi |
|---|---|
| `backend/app/main.py` | timpa (mendaftarkan router dashboard) |
| `backend/app/routers/dashboard.py` | baru |
| `backend/app/routers/stok.py` | timpa (daftar stok masuk kini punya `?limit=`) |
| `backend/app/services/analitik.py` | baru |
| `backend/app/services/stok.py` | timpa (parameter `limit`; sudah memuat perbaikan 409 sebelumnya) |
| `backend/app/services/waktu.py` | timpa (batas hari menurut WIB) |
| `backend/app/schemas_dash.py` | baru |
| `backend/tests/test_dashboard.py` | baru |

Tidak ada migrasi baru dan tidak ada paket baru.

## Langkah

1. Salin isi zip ke folder proyek (yang berisi `backend/`), pilih Replace bila ditanya.
2. Terminal di `backend`, `(.venv)` aktif: `python -m pytest -q` -> `186 passed, 2 skipped`.
3. Server `uvicorn app.main:app --reload` (tunggu memuat ulang bila sudah jalan).
4. Browser: tab 1 http://127.0.0.1:8000/ (login), tab 2 http://127.0.0.1:8000/docs (bagian "dashboard").

## Endpoint

GET /api/dashboard/summary · GET /api/analisis?period=minggu|bulan
GET /api/laporan?periode=minggu|bulan  atau  ?from=YYYY-MM-DD&to=YYYY-MM-DD
GET /api/notifications · POST /api/notifications/{id}/baca · POST /api/notifications/baca-semua
GET /api/stok/masuk?limit=5

## Aturan

- Komposisi sebuah batch = hasil scan pada putaran terbaru (semua lapis digabung).
- Persen seluruh stok dibobot sisa kg tiap batch; hanya batch yang masih ada stok dan sudah dipindai.
- "Scan hari ini" menghitung jumlah scan (lapis) hari ini menurut WIB.
- Notifikasi: kurang segar >= 30% atau busuk >= 20% pada scan terakhir batch yang masih ada stoknya
  (ambang bisa diubah lewat tabel `settings`: notif_kurang, notif_busuk). Stok habis atau batch dihapus = notifikasi hilang.
  Scan baru = notifikasi baru (belum dibaca). Status dibaca terpisah untuk tiap pengguna.
- Laporan: sisa = stok pada akhir rentang; rentang maksimal 366 hari; hari mengikuti WIB.
