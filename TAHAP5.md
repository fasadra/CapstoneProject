# Tahap 5 — Website tersambung ke database

Tidak ada file backend yang berubah. Semua halaman kini membaca dan menulis lewat API; data lama di browser tidak dipakai lagi.

## Letak file (timpa)

| File | Perubahan |
|---|---|
| `frontend/js/api.js` | Ditulis ulang: semua fungsi memanggil backend (hanya `classify` yang masih simulasi sampai Tahap 6) |
| `frontend/js/stok-form.js` | Nama buah jadi pilihan Apel / Jeruk / Anggur; jenis buah terkunci saat ubah; maksimal 24 foto per kiriman |
| `frontend/stok-masuk-baru.html` | Kolom nama buah diganti kotak pilihan |
| `frontend/js/klasifikasi-hasil.js` | Menyimpan hasil tiap foto sebagai lapis (satu foto = satu lapis) |
| `frontend/js/stok.js` | Teks konfirmasi hapus disesuaikan (hapus lunak) |

File lain (common.js, dashboard.js, login.js, register.js, dst.) tetap dari Tahap 3.

## Langkah

1. Salin isi zip ke folder proyek (yang berisi `frontend/`), pilih Replace.
2. Server berjalan (`uvicorn app.main:app --reload`), Docker menyala.
3. Buka http://127.0.0.1:8000/ , tekan Ctrl+Shift+R, login.
4. Coba alur di bawah.

## Alur uji di website

1. Dashboard: angka, notifikasi, stok terbaru, dan analisis berasal dari database.
2. Stok > Stok Masuk: tiga batch contoh tampil. Klik satu untuk melihat riwayat (masuk, pindai, keluar).
3. Catat Stok Masuk: pilih buah, isi kg, unggah foto (satu foto = satu lapis), Simpan, lihat hasil, Simpan. Batch baru muncul di daftar.
4. Ubah stok masuk (ikon pensil): jenis buah terkunci; jumlah tidak boleh di bawah yang sudah keluar.
5. Catat Stok Keluar: diambil dari kiriman terlama dulu. Lihat sisa tiap batch di daftar.
6. Hapus batch: hilang dari daftar, laporan, dan notifikasi.
7. Laporan (minggu / bulan / pilih tanggal) dan Notifikasi (klik = ditandai dibaca).

Untuk kembali ke data contoh: `python seed.py --reset` di folder backend.
