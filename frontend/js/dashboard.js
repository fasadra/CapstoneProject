const $ = id => document.getElementById(id);
renderTopbar('dashboard');
let period = 'minggu';

const ICON = {
  up:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/></svg>',
  down:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 7 9 13 13 9 21 17"/><polyline points="15 17 21 17 21 11"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
  warn:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17.5v.01"/></svg>',
};

function setToday() {
  const hari = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
  const bulan = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
  const d = new Date();
  $('today').textContent = `${hari[d.getDay()]}, ${d.getDate()} ${bulan[d.getMonth()]} ${d.getFullYear()}`;
}

/* ---------- Kartu ringkasan ---------- */
// goodWhenUp: true kalau naik = kabar baik (Segar), false kalau naik = kabar buruk (Kurang segar, Busuk)
function renderTrend(el, t, goodWhenUp) {
  if (t === null || t === undefined) {
    el.className = 'trend neutral';
    el.innerHTML = '<span>Belum ada pembanding</span>';
    return;
  }
  if (t === 0) {
    el.className = 'trend neutral';
    el.innerHTML = '<span>Sama seperti kemarin</span>';
    return;
  }
  const naik = t > 0;
  el.className = 'trend ' + (naik === goodWhenUp ? 'good' : 'bad');
  el.innerHTML = (naik ? ICON.up : ICON.down) + `<span>${Math.abs(t)}% dari kemarin</span>`;
}

async function loadSummary() {
  try {
    const s = await API.getSummary();
    $('totalScan').textContent = Number(s.scanHariIni).toLocaleString('id-ID');
    const ids = [['pctSegar', 'trendSegar', true], ['pctKurang', 'trendKurang', false], ['pctBusuk', 'trendBusuk', false]];
    ids.forEach(([pid, tid, good], i) => {
      $(pid).textContent = s.persen ? s.persen[i] + '%' : '-';
      if (!s.persen) { $(tid).className = 'trend neutral'; $(tid).innerHTML = '<span>Belum ada stok terpindai</span>'; }
      else renderTrend($(tid), s.trend[i], good);
    });
  } catch (e) {
    console.error(e);
    ['trendSegar', 'trendKurang', 'trendBusuk'].forEach(id => {
      $(id).className = 'trend neutral';
      $(id).innerHTML = '<span>Gagal memuat data</span>';
    });
  }
}

/* ---------- Notifikasi ---------- */
// Teks singkat di dashboard (tanpa perkiraan kg, sesuai desain)
const notifDash = n => n.type === 'busuk'
  ? `${n.buah} mulai busuk ${n.persen}%, pisahkan dan buang.`
  : `${n.buah} kurang segar ${n.persen}%, pisahkan.`;
async function loadTodo() {
  const box = $('todo');
  try {
    const list = await API.getNotifications();
    if (!list.length) { box.innerHTML = '<li class="empty">Tidak ada notifikasi.</li>'; return; }
    box.innerHTML = list.slice(0, 3).map(n =>
      `<li><span class="ic ${n.type === 'busuk' ? 'red' : 'yellow'}">${n.type === 'busuk' ? ICON.trash : ICON.warn}</span><span>${esc(notifDash(n, true))}</span></li>`
    ).join('');
  } catch (e) {
    console.error(e);
    box.innerHTML = '<li class="empty">Gagal memuat data.</li>';
  }
}

/* ---------- Daftar stok masuk ---------- */
async function loadStock() {
  const body = $('stockBody');
  try {
    const rows = await API.getRecentStock(5);
    if (!rows.length) { body.innerHTML = '<tr><td colspan="4" class="empty">Belum ada stok masuk.</td></tr>'; return; }
    body.innerHTML = rows.map(r => `
      <tr>
        <td>${esc(r.buah)}</td>
        <td>${kgFmt(r.kg)} kg</td>
        <td>${compPills(r.komposisi)}</td>
        <td>${fmtTanggal(r.masukPada)}</td>
      </tr>`).join('');
  } catch (e) {
    console.error(e);
    body.innerHTML = '<tr><td colspan="4" class="empty">Gagal memuat data.</td></tr>';
  }
}

/* ---------- Analisis (Minggu Ini / Bulan Ini) ---------- */
const BARS = [['Segar', 'segar'], ['Kurang Segar', 'kurang'], ['Busuk', 'busuk']];

async function loadAnalysis() {
  const box = $('bars');
  try {
    const d = await API.getAnalysis(period);
    box.innerHTML = BARS.map(([label, cls], i) => `
      <div>
        <div class="bar-head"><b>${label}</b><span>${Number(d.scan[i]).toLocaleString('id-ID')} scan</span></div>
        <div class="bar"><span class="${cls}" style="width:${d.persen[i]}%">${d.persen[i]}%</span></div>
      </div>`).join('');
  } catch (e) {
    console.error(e);
    box.innerHTML = '<p class="empty">Gagal memuat data.</p>';
  }
}

document.querySelectorAll('.period button').forEach(btn => {
  btn.addEventListener('click', () => {
    period = btn.dataset.period;
    document.querySelectorAll('.period button').forEach(b => {
      const aktif = b === btn;
      b.classList.toggle('on', aktif);
      b.setAttribute('aria-pressed', aktif);
    });
    loadAnalysis();
  });
});

function loadAll() { loadSummary(); loadTodo(); loadStock(); loadAnalysis(); refreshBell(); }

function start() {
  setToday();
  loadAll();
  // Segarkan otomatis tiap 30 detik (selama tab terbuka)
  setInterval(() => { if (!document.hidden) loadAll(); }, 30000);
}

if (LOGGED_IN) {
  start();
  // Sapaan memakai nama pengguna yang sedang login
  ME.then(u => { const h = document.querySelector('h1'); if (u && h) h.textContent = 'Halo, ' + u.nama; });
}