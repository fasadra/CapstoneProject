// Penanda login hanya PETUNJUK agar halaman tidak berkedip. Pengamanan sebenarnya ada di server
// (cookie sesi HttpOnly). Kalau belum ada penanda, langsung ke halaman masuk.
const LOGGED_IN = localStorage.getItem('fs_login') === '1';
if (!LOGGED_IN) window.location.replace('login.html');

// Tanya server apakah sesi masih berlaku. ME = Promise berisi data pengguna (atau null).
function sesiBerakhir() {
  localStorage.removeItem('fs_login');
  window.location.replace('login.html');
}
const ME = LOGGED_IN
  ? fetch('/api/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(r => { if (r.status === 401) { sesiBerakhir(); return null; } return r.ok ? r.json() : null; })
      .catch(() => null)          // server tidak terjangkau: jangan paksa keluar
  : Promise.resolve(null);

// Pelindung teks dari data luar (penting saat nanti data datang dari backend)
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const pad2 = n => String(n).padStart(2, '0');

// "2026-10-02T08:00:00" atau Date -> "2 Okt, 08.00"
function fmtTanggal(iso) {
  const d = new Date(iso);
  const bln = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
  return `${d.getDate()} ${bln[d.getMonth()]}, ${pad2(d.getHours())}.${pad2(d.getMinutes())}`;
}
// -> "09 Oktober 2026"
function fmtTanggalPanjang(iso) {
  const d = new Date(iso);
  const bln = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
  return `${pad2(d.getDate())} ${bln[d.getMonth()]} ${d.getFullYear()}`;
}
function fmtSekarang() { return fmtTanggal(new Date()); }
const sameDay = (a, b) => a.toDateString() === b.toDateString();

// "10 menit lalu", "1 jam lalu", atau tanggal panjang kalau bukan hari ini
function waktuRelatif(iso) {
  const d = new Date(), t = new Date(iso);
  if (!sameDay(d, t)) return fmtTanggalPanjang(iso);
  const m = Math.max(0, Math.floor((d - t) / 60000));
  if (m < 1) return 'baru saja';
  if (m < 60) return `${m} menit lalu`;
  return `${Math.floor(m / 60)} jam lalu`;
}

/* ---------- Komposisi tiga kelas ---------- */
const KELAS = ['Segar', 'Kurang Segar', 'Busuk'];
const KELAS_CLS = ['s', 'k', 'b'];
const kgFmt = n => (Math.round(n * 10) / 10).toLocaleString('id-ID', { maximumFractionDigits: 1 });

// Kelas yang paling banyak: 0 = segar, 1 = kurang segar, 2 = busuk
function dom(c) { return c[0] >= c[1] && c[0] >= c[2] ? 0 : c[1] >= c[2] ? 1 : 2; }

// Pil komposisi (kelas 0% tidak ditampilkan)
function compPills(c, besar) {
  if (!c) return '<span class="badge badge-belum">Belum dipindai</span>';
  const label = `Segar ${c[0]}%, kurang segar ${c[1]}%, busuk ${c[2]}%`;
  return `<span class="comp${besar ? ' lg' : ''}" role="img" aria-label="${label}">` +
    c.map((p, i) => p > 0 ? `<i class="${KELAS_CLS[i]}" style="--w:${56 + p}">${p}%</i>` : '').join('') + '</span>';
}

// Teks notifikasi. withKg = tampilkan perkiraan kg (dipakai di dashboard)
function notifText(n, withKg) {
  const kg = withKg ? ` (${kgFmt(n.kg)}kg)` : '';
  return n.type === 'busuk'
    ? `${n.buah} ${withKg ? 'mulai ' : ''}busuk ${n.persen}%${kg}, pisahkan dan buang.`
    : `${n.buah} kurang segar ${n.persen}%${kg}, pisahkan.`;
}

/* ---------- Pesan singkat ---------- */
function toast(msg, isErr) {
  const t = document.createElement('div');
  t.className = 'toast' + (isErr ? ' err' : '');
  t.setAttribute('role', 'status');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3400);
}
function flash(msg) { sessionStorage.setItem('fs_flash', msg); }
function showFlash() {
  const m = sessionStorage.getItem('fs_flash');
  if (m) { sessionStorage.removeItem('fs_flash'); toast(m); }
}

/* ---------- Angka di ikon lonceng = notifikasi yang belum dibaca ---------- */
async function refreshBell() {
  const el = document.getElementById('notifCount');
  if (!el) return;
  try {
    const list = await API.getNotifications();
    const belum = list.filter(n => !n.dibaca).length;
    el.textContent = belum > 9 ? '9+' : belum;
    el.hidden = belum === 0;
  } catch (e) {
    el.hidden = true;
  }
}

async function logout() {
  if (!confirm('Yakin ingin keluar?')) return;
  try { await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }); }
  catch (e) { /* tetap keluar di sisi browser */ }
  localStorage.removeItem('fs_login');
  sessionStorage.clear();
  window.location.href = 'landing.html';
}

/* ---------- Menu profil (klik ikon orang) ---------- */
function setupProfileMenu() {
  const btn = document.querySelector('a[aria-label="Profil"]');
  if (!btn || btn.dataset.menu) return;
  btn.dataset.menu = '1';

  const wrap = document.createElement('span');
  wrap.className = 'profile-wrap';
  btn.parentNode.insertBefore(wrap, btn);
  wrap.appendChild(btn);

  const menu = document.createElement('div');
  menu.className = 'menu';
  menu.hidden = true;
  menu.setAttribute('role', 'menu');
  menu.innerHTML =
    '<a role="menuitem" href="profil.html">Profil</a>' +
    '<a role="menuitem" href="profil-sandi.html">Ubah Kata Sandi</a>' +
    '<hr><button type="button" role="menuitem" class="danger">Keluar</button>';
  wrap.appendChild(menu);

  btn.setAttribute('aria-haspopup', 'menu');
  btn.setAttribute('aria-expanded', 'false');
  const close = () => { menu.hidden = true; btn.setAttribute('aria-expanded', 'false'); };

  btn.addEventListener('click', e => {
    e.preventDefault();
    const buka = menu.hidden;
    menu.hidden = !buka;
    btn.setAttribute('aria-expanded', String(buka));
  });
  document.addEventListener('click', e => { if (!wrap.contains(e.target)) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  menu.querySelector('button').addEventListener('click', logout);
}

/* ---------- Navbar atas (dipakai semua halaman setelah login) ---------- */
const FS_ICONS = {
  bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg>',
};

// active: 'dashboard' | 'stok' | 'laporan' | 'notif' | 'profil'
function renderTopbar(active) {
  const el = document.getElementById('topbar');
  if (!el) return;
  const link = (key, href, label) =>
    `<a href="${href}"${active === key ? ' class="active" aria-current="page"' : ''}>${label}</a>`;
  el.className = 'topbar';
  el.innerHTML =
    '<a class="brand" href="dashboard.html" aria-label="FRESHSENSE AI, ke dashboard"><img src="img/logofreshsenseai.png" alt=""><span>FRESHSENSE AI</span></a>' +
    '<div class="topbar-right">' +
      '<nav class="nav-pill" aria-label="Menu utama">' +
        link('dashboard', 'dashboard.html', 'Dashboard') +
        link('stok', 'stok.html', 'Stok') +
        link('laporan', 'laporan.html', 'Laporan') +
      '</nav>' +
      `<a class="round-btn${active === 'notif' ? ' is-active' : ''}" href="notifikasi.html" aria-label="Notifikasi"${active === 'notif' ? ' aria-current="page"' : ''}>${FS_ICONS.bell}<span id="notifCount" class="notif-count" hidden></span></a>` +
      `<a class="round-btn${active === 'profil' ? ' is-active' : ''}" href="profil.html" aria-label="Profil">${FS_ICONS.user}</a>` +
    '</div>';
  setupProfileMenu();
  refreshBell();
}

showFlash();