# Tahap 4a — Stok masuk dan keluar

## Letak file (timpa / tambah)

| File | Aksi |
|---|---|
| `backend/app/models.py` | timpa (kolom `keyakinan` boleh kosong) |
| `backend/app/main.py` | timpa (mendaftarkan router stok) |
| `backend/app/schemas_stok.py` | baru |
| `backend/app/services/__init__.py`, `waktu.py`, `stok.py` | baru (folder `services` baru) |
| `backend/app/routers/stok.py` | baru |
| `backend/alembic/versions/0002_keyakinan_boleh_kosong.py` | baru (migrasi) |
| `backend/tests/test_stok.py` | baru |

## Langkah

1. Salin isi zip ke folder proyek (yang berisi `backend/`), pilih Replace bila ditanya.
2. Docker menyala (`docker compose ps` -> healthy). Terminal di `backend` dengan `(.venv)` aktif.
3. **Migrasi:** `alembic upgrade head` -> harus muncul `Running upgrade 0001 -> 0002`.
4. Tes: `python -m pytest -q` -> `146 passed, 2 skipped` (2 yang dilewati hanya jalan di PostgreSQL uji).
5. Jalankan server: `uvicorn app.main:app --reload` (bila sudah jalan, tunggu ia memuat ulang).
6. Browser tab 1: http://127.0.0.1:8000/ dan login. Tab 2: http://127.0.0.1:8000/docs (bagian "stok").

## Uji di /docs (klik endpoint -> Try it out -> isi -> Execute)

1. GET /api/stok/masuk -> 3 batch: AGR-1003 sisa 8, JRK-1009 sisa 35, APL-1012 sisa 25.
2. POST /api/stok/masuk, body:
   {"buah":"Anggur","jumlah":10,"lapis":[{"hitung":[6,3,1]},{"hitung":[8,2,0]}]}
   -> {"id":"AGR-1004"}
3. POST /api/stok/keluar, body: {"buah":"Anggur","jumlah":10,"alasan":"Terjual"}
   -> diambil: AGR-1003 8 kg lalu AGR-1004 2 kg
4. GET /api/stok/keluar -> baris Anggur 10 kg (Terjual) paling atas
5. POST /api/stok/keluar, body: {"buah":"Apel","jumlah":30,"alasan":"Terjual"} -> 400 "Stok Apel hanya tersisa 25 kg"
6. PUT /api/stok/masuk/AGR-1003, body: {"buah":"Anggur","jumlah":3} -> 400 (di bawah yang sudah keluar)
7. DELETE /api/stok/masuk/AGR-1004 -> {"ok":true}; GET daftar tidak lagi memuatnya
8. Database: docker exec -it freshsense-db psql -U freshsense -d freshsense -c "SELECT id, jumlah_kg, deleted_at FROM batches ORDER BY id;"
   AGR-1004 tetap ada dengan deleted_at terisi.

## Aturan

- Stok keluar mengambil dari kiriman TERTUA dulu (FIFO) dalam satu transaksi; baris batch dikunci sebelum sisa dihitung.
- Stok keluar tidak boleh melebihi sisa; jumlah batch tidak boleh diturunkan di bawah yang sudah keluar.
- Jenis buah sebuah kiriman tidak bisa diubah (nomor batch dan hasil scan terikat pada jenisnya).
- Hapus = hapus lunak: hilang dari daftar dan dari daftar stok keluar, tetapi barisnya tetap ada di database.
- Foto belum disimpan; hanya hasil klasifikasi per lapis (putaran 1). `keyakinan` kosong sampai model asli dipasang.
