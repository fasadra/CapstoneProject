# Tahap 6A — Scan ulang (putaran baru)

Satu zip ini berisi backend LENGKAP terbaru (pengganti `backend-terkini.zip` dan semua perbaikan sebelumnya) dan 4 file frontend.

## Letak file

| Bagian | Aksi |
|---|---|
| `backend/` (seluruh folder) | timpa. Tidak menyentuh `.venv`, `.env`, database, maupun akunmu |
| `frontend/js/api.js` | timpa (menambah `pindaiUlang`) |
| `frontend/js/stok-detail.js` | timpa (tombol "Pindai Ulang", info lapis di riwayat) |
| `frontend/js/stok-form.js` | timpa (mode `?pindai=ID`) |
| `frontend/js/klasifikasi-hasil.js` | timpa (menyimpan hasil sebagai putaran baru) |

Tidak ada migrasi baru dan tidak ada paket baru.

## Langkah

1. Salin `backend` dan `frontend` dari zip ke folder proyek (Replace).
2. Tes: `python -m pytest -q` (folder backend, `(.venv)` aktif) -> `204 passed, 3 skipped`.
3. Jalankan server, buka http://127.0.0.1:8000/ , Ctrl+Shift+R, login.

## Uji di website

1. Stok > klik kiriman (mis. AGR-1003): ada tombol **Pindai Ulang** (hanya bila stok masih ada). Riwayat memuat jumlah lapis dan buah tiap pindai.
2. Pindai Ulang: judul "Pindai Ulang AGR-1003", jenis buah terkunci, kolom jumlah tidak ada. Foto semua lapis yang masih ada (satu foto = satu lapis), tekan **Pindai**.
3. Halaman hasil menampilkan komposisi baru dan komposisi pindai sebelumnya. **Simpan** -> kembali ke detail kiriman dengan putaran baru di riwayat.
4. Dashboard, Notifikasi, dan daftar Stok langsung mengikuti komposisi terbaru.

## Endpoint baru

POST /api/stok/masuk/{id}/scan  body: {"lapis":[{"hitung":[segar,kurang,busuk]}, ...]}
-> {"putaran":3,"lapis":2,"lapisSebelumnya":4,"komposisi":[..],"komposisiSebelumnya":[..]}

## Aturan

- Pindai ulang hanya untuk kiriman yang stoknya masih ada.
- Setiap pindai menjadi putaran baru (2, 3, ...). Komposisi terkini = putaran terbaru; komposisi awal tetap putaran 1.
- Notifikasi dihitung dari putaran terbaru: kondisi membaik = notifikasi hilang; memburuk = notifikasi baru (belum dibaca).
- Hasil klasifikasi masih simulasi (acak) sampai Tahap 6B.
