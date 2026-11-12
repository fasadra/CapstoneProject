/*
  Lapisan data. Semua fungsi memanggil backend (FastAPI) lewat fetch; tidak ada lagi data di browser.
  Cookie login (HttpOnly) ikut terkirim otomatis. Kalau server menjawab 401, pengguna dikembalikan ke halaman masuk.
  Pesan kesalahan dari server menjadi Error.message, jadi halaman cukup menampilkannya dengan toast().

  Komposisi = [segar, kurang segar, busuk] dalam persen bulat, totalnya 100.
  Satu scan = satu foto satu lapis; semua lapis dalam sebuah kiriman difoto.
  Satu-satunya yang masih simulasi: classify() (hasil acak di browser) sampai model dipasang di Tahap 6.
*/
const API = (() => {
  // Sisa data lama dari versi simulasi (tidak dipakai lagi)
  try { ['fs_db_v3', 'fs_notif_read_v3', 'fs_profile'].forEach(k => localStorage.removeItem(k)); } catch (e) { /* abaikan */ }

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const enc = encodeURIComponent;

  // Jenis buah yang didukung (sama dengan yang diterima backend)
  const FRUITS = [
    { nama: 'Apel',   latin: 'Malus domestica',    kode: 'APL' },
    { nama: 'Jeruk',  latin: 'Citrus × sinensis',  kode: 'JRK' },
    { nama: 'Anggur', latin: 'Vitis vinifera',     kode: 'AGR' },
  ];
  const SUPPORTED = FRUITS.map(f => f.nama);

  function normFruit(text) {
    const t = String(text || '').trim().replace(/\s+/g, ' ');
    if (!t) return '';
    const f = FRUITS.find(x => x.nama.toLowerCase() === t.toLowerCase());
    return f ? f.nama : t.charAt(0).toUpperCase() + t.slice(1).toLowerCase();
  }

  function pct3(a) {
    const t = a[0] + a[1] + a[2];
    if (!t) return [0, 0, 0];
    const x = Math.round(a[0] / t * 100);
    let y = Math.round(a[1] / t * 100);
    if (x + y > 100) y = 100 - x;
    return [x, y, 100 - x - y];
  }

  /* ---------- Pembungkus fetch ---------- */
  function pesanError(data, status) {
    if (data && typeof data.detail === 'string') return data.detail;
    if (data && Array.isArray(data.detail) && data.detail[0] && data.detail[0].msg) {
      return String(data.detail[0].msg).replace(/^Value error, /, '');
    }
    return status >= 500 ? 'Terjadi kesalahan di server.' : 'Permintaan gagal.';
  }
  // notFoundNull: jawaban 404 dikembalikan sebagai null (bukan error)
  async function http(method, url, body, { notFoundNull = false } = {}) {
    let res;
    try {
      res = await fetch(url, {
        method, credentials: 'same-origin',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new Error('Tidak dapat terhubung ke server.');
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* tanpa isi */ }
    if (res.status === 401) {                       // sesi habis -> kembali ke halaman masuk
      localStorage.removeItem('fs_login');
      window.location.replace('login.html');
    }
    if (notFoundNull && res.status === 404) return null;
    if (!res.ok) throw new Error(pesanError(data, res.status));
    return data;
  }

  /* ---------- Stok masuk ---------- */

  // GET /api/stok/masuk  (terbaru di atas)
  // -> [{ id, buah, jumlah, sisa, komposisi, komposisiAwal, masukPada }]
  // komposisi = dari scan putaran terbaru, komposisiAwal = dari putaran pertama (null = belum dipindai)
  async function getStockIn() { return http('GET', '/api/stok/masuk'); }

  // GET /api/stok/masuk/:id -> ringkasan di atas + { latin, keluar, riwayat:[{ k:'in'|'out'|'scan', t, q, r, c, n, sisa }] }
  // null bila tidak ditemukan
  async function getBatch(id) { return http('GET', `/api/stok/masuk/${enc(id)}`, null, { notFoundNull: true }); }

  // POST /api/stok/masuk  { buah, jumlah, lapis: [{ hitung:[s,k,b], kotak:[{ x, y, w, h, k }] }] }
  // lapis = hasil klasifikasi tiap foto (satu foto = satu lapis). -> { id }
  async function addBatch({ buah, jumlah, lapis }) { return http('POST', '/api/stok/masuk', { buah, jumlah, lapis }); }

  // POST /api/stok/masuk/:id/scan  { lapis: [{ hitung:[s,k,b], kotak:[...] }] }
  // Scan ulang (QC berkala): semua lapis yang masih ada difoto lagi; menjadi putaran baru.
  // -> { putaran, lapis, lapisSebelumnya, komposisi, komposisiSebelumnya }
  async function pindaiUlang(id, lapis) {
    return http('POST', `/api/stok/masuk/${enc(id)}/scan`, { lapis });
  }

  // PUT /api/stok/masuk/:id  { buah, jumlah }   (jenis buah tidak bisa diubah)
  async function updateBatch(id, { buah, jumlah }) {
    await http('PUT', `/api/stok/masuk/${enc(id)}`, { buah, jumlah });
    return true;
  }

  // DELETE /api/stok/masuk/:id   (hapus lunak: hilang dari daftar, laporan, dan stok keluar)
  async function deleteBatch(id) {
    await http('DELETE', `/api/stok/masuk/${enc(id)}`);
    return true;
  }

  /* ---------- Stok keluar ---------- */

  // GET /api/stok/keluar  (terbaru di atas) -> [{ gid, buah, jumlah, alasan, waktu }]
  async function getStockOut() { return http('GET', '/api/stok/keluar'); }

  // POST /api/stok/keluar  { buah, jumlah, alasan: 'Terjual' | 'Terbuang' } -> { gid, diambil:[{ batch, jumlah }] }
  // Dikurangi dari kiriman TERLAMA dulu (FIFO), jadi buah lama dijual lebih dulu.
  async function addStockOut({ buah, jumlah, alasan }) { return http('POST', '/api/stok/keluar', { buah, jumlah, alasan }); }

  /* ---------- Klasifikasi ---------- */

  // Perkecil foto agar muat disimpan sementara
  function fileToDataUrl(file, max = 520) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onerror = () => reject(new Error('Gagal membaca file'));
      fr.onload = () => {
        const img = new Image();
        img.onerror = () => reject(new Error('File bukan gambar yang valid'));
        img.onload = () => {
          const s = Math.min(1, max / Math.max(img.width, img.height));
          const c = document.createElement('canvas');
          c.width = Math.round(img.width * s);
          c.height = Math.round(img.height * s);
          c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
          resolve(c.toDataURL('image/jpeg', 0.75));
        };
        img.src = fr.result;
      };
      fr.readAsDataURL(file);
    });
  }

  // POST /api/klasifikasi  (multipart: foto[] = satu atau lebih foto, buah)
  // -> { fotos: [{ lapisan, url, n, hitung:[s,k,b], c:[s,k,b], kotak:[{ x, y, w, h, k }] }],
  //      total: { n, hitung:[s,k,b], c:[s,k,b] } }
  // 'kotak' = kotak deteksi per buah (x, y, w, h dalam pecahan 0 sampai 1; k = 0 segar, 1 kurang, 2 busuk).
  // SEKARANG hasilnya ACAK (simulasi, dihitung di browser) dan kotak kosong. Tahap 6 menggantinya dengan
  // panggilan ke backend yang menjalankan model deteksi + klasifikasimu. Bentuk hasilnya tetap sama.
  async function classify(files, buah) {
    const fotos = [];
    for (let i = 0; i < files.length; i++) {
      const url = await fileToDataUrl(files[i]);
      const n = 10 + Math.floor(Math.random() * 7);
      const pB = 0.03 + Math.random() * 0.12, pS = 0.5 + Math.random() * 0.25;
      const h = [0, 0, 0];
      for (let a = 0; a < n; a++) { const r = Math.random(); h[r < pS ? 0 : r < 1 - pB ? 1 : 2]++; }
      fotos.push({ lapisan: `Foto ${i + 1}`, url, n, hitung: h, c: pct3(h), kotak: [] });
    }
    await sleep(900);
    const hitung = [0, 1, 2].map(i => fotos.reduce((a, f) => a + f.hitung[i], 0));
    return { fotos, total: { n: hitung[0] + hitung[1] + hitung[2], hitung, c: pct3(hitung) } };
  }

  /* ---------- Notifikasi ---------- */

  // GET /api/notifications  (terbaru di atas)
  // -> [{ id, batch, buah, type:'kurang'|'busuk', persen, kg, waktu, dibaca }]
  // Dibuat dari komposisi scan terakhir tiap kiriman yang MASIH ada stoknya (ambang ada di server).
  async function getNotifications() { return http('GET', '/api/notifications'); }

  // POST /api/notifications/:id/baca
  // keepalive: permintaan tetap terkirim walau halaman langsung berpindah (notifikasi adalah tautan).
  async function markRead(id) {
    try {
      await fetch(`/api/notifications/${enc(id)}/baca`, { method: 'POST', credentials: 'same-origin', keepalive: true });
    } catch (e) { /* abaikan: tanda dibaca bukan hal kritis */ }
  }

  // POST /api/notifications/baca-semua
  async function markAllRead() { await http('POST', '/api/notifications/baca-semua'); return true; }

  /* ---------- Laporan ---------- */

  // periode: 'minggu' (7 hari terakhir) | 'bulan' (30 hari terakhir) | { from: 'YYYY-MM-DD', to: 'YYYY-MM-DD' }
  // GET /api/laporan?periode=minggu   atau   ?from=...&to=...
  // -> { ringkas: { masuk, terjual, terbuang }, rows: [{ buah, masuk, terjual, terbuang, sisa }] }
  async function getReport(periode) {
    const q = periode && typeof periode === 'object'
      ? `from=${enc(periode.from)}&to=${enc(periode.to)}`
      : `periode=${periode === 'bulan' ? 'bulan' : 'minggu'}`;
    return http('GET', `/api/laporan?${q}`);
  }

  /* ---------- Dashboard ---------- */

  // GET /api/dashboard/summary
  // -> { scanHariIni, persen:[s,k,b] | null, trend:[..] }  (trend = selisih persen dari kemarin; null = belum ada pembanding)
  async function getSummary() { return http('GET', '/api/dashboard/summary'); }

  // GET /api/stok/masuk?limit=5
  async function getRecentStock(limit = 5) {
    const rows = await http('GET', `/api/stok/masuk?limit=${Number(limit) || 5}`);
    return rows.map(r => ({ buah: r.buah, kg: r.jumlah, komposisi: r.komposisi, masukPada: r.masukPada }));
  }

  // GET /api/analisis?period=minggu|bulan
  // persen = komposisi gabungan semua buah pada semua scan di periode; scan = jumlah scan (lapis) yang dominan segar/kurang/busuk
  async function getAnalysis(period) { return http('GET', `/api/analisis?period=${period === 'bulan' ? 'bulan' : 'minggu'}`); }

  /* ---------- Profil ---------- */

  // GET /api/profil
  async function getProfile() { return http('GET', '/api/profil'); }
  // PUT /api/profil  (role tidak bisa diubah dari sini)
  async function saveProfile(p) {
    return http('PUT', '/api/profil', { nama: p.nama, username: p.username, email: p.email, telepon: p.telepon });
  }
  // POST /api/profil/sandi  { lama, baru }
  // Kata sandi TIDAK disimpan di browser. Server memeriksa sandi lama dan menyimpan hash sandi baru.
  async function changePassword(lama, baru) { return http('POST', '/api/profil/sandi', { lama, baru }); }

  return {
    FRUITS, SUPPORTED, normFruit,
    getStockIn, getBatch, addBatch, pindaiUlang, updateBatch, deleteBatch,
    getStockOut, addStockOut, classify,
    getNotifications, markRead, markAllRead, getReport,
    getProfile, saveProfile, changePassword,
    getSummary, getRecentStock, getAnalysis,
  };
})();
