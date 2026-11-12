const $ = id => document.getElementById(id);
renderTopbar('stok');

const AB = { Terjual: 'badge-terjual', Terbuang: 'badge-terbuang' };
const FILTERS = { masuk: ['Semua', 'Segar', 'Kurang Segar', 'Busuk'], keluar: ['Semua', 'Terjual', 'Terbuang'] };
const svg = p => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const ICO = {
  edit:  svg('<path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4"/>'),
  trash: svg('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>'),
};

let tab = new URLSearchParams(location.search).get('tab') === 'keluar' ? 'keluar' : 'masuk';
let flt = 'Semua', page = 1, perPage = 5, rows = [];

const total = (arr, k) => arr.reduce((s, r) => s + r[k], 0);

// Filter Segar / Kurang Segar / Busuk memakai kelas yang paling dominan
function filtered() {
  if (flt === 'Semua') return rows;
  return tab === 'masuk'
    ? rows.filter(r => r.komposisi && KELAS[dom(r.komposisi)] === flt)
    : rows.filter(r => r.alasan === flt);
}

/* ---------- Kartu ringkasan ---------- */
function renderCards() {
  const card = (l, v, cls = '') => `<div class="sum-card"><span class="l">${l}</span><span class="v ${cls}">${v}</span></div>`;
  if (tab === 'masuk') {
    // "Segar saat masuk" = bagian segar dari komposisi awal, dibobot jumlah kg masuk (hanya yang sudah dipindai)
    const scanned = rows.filter(r => r.komposisiAwal);
    const kgScan = total(scanned, 'jumlah');
    const kgSegar = scanned.reduce((a, r) => a + r.jumlah * r.komposisiAwal[0] / 100, 0);
    $('sum').innerHTML =
      card('Total Masuk', `${kgFmt(total(rows, 'jumlah'))} kg`) +
      card('Sisa Buah Di Toko', `${kgFmt(total(rows, 'sisa'))} kg`) +
      card('Segar saat masuk', kgScan ? Math.round(kgSegar / kgScan * 100) + '%' : '-', 'green');
  } else {
    const by = a => total(rows.filter(r => r.alasan === a), 'jumlah');
    $('sum').innerHTML =
      card('Total Keluar', `${kgFmt(total(rows, 'jumlah'))} kg`) +
      card('Terjual', `${kgFmt(by('Terjual'))} kg`) +
      card('Terbuang', `${kgFmt(by('Terbuang'))} kg`);
  }
}

function renderChips() {
  // Tab Stok Masuk tidak memakai filter (Semua / Segar / Kurang Segar / Busuk)
  $('chips').hidden = tab === 'masuk';
  if (tab === 'masuk') { $('chips').innerHTML = ''; return; }
  $('chips').innerHTML = FILTERS[tab].map(f =>
    `<button type="button" class="fchip${f === flt ? ' on' : ''}" data-f="${f}">${f}</button>`).join('');
}

/* ---------- Tabel ---------- */
function renderTable() {
  const data = filtered();
  const pages = Math.max(1, Math.ceil(data.length / perPage));
  if (page > pages) page = pages;
  const slice = data.slice((page - 1) * perPage, page * perPage);

  let head, cols, body;
  if (tab === 'masuk') {
    cols = [17, 12, 18, 25, 16, 12];
    head = ['Buah', 'Jumlah', 'Sisa saat ini', 'Status', 'Waktu', 'Aksi'];
    body = slice.map(r => `
      <tr>
        <td><a class="fruit-link" href="stok-detail.html?id=${encodeURIComponent(r.id)}">${esc(r.buah)}</a><span class="sub">${esc(r.id)}</span></td>
        <td>${kgFmt(r.jumlah)} kg</td>
        <td>${kgFmt(r.sisa)} kg</td>
        <td>${compPills(r.komposisi)}</td>
        <td>${fmtTanggal(r.masukPada)}</td>
        <td>
          <a class="icon-btn blue" href="stok-masuk-baru.html?edit=${encodeURIComponent(r.id)}" aria-label="Ubah ${esc(r.buah)} ${esc(r.id)}">${ICO.edit}</a>
          <button type="button" class="icon-btn red" data-del="${esc(r.id)}" aria-label="Hapus ${esc(r.buah)} ${esc(r.id)}">${ICO.trash}</button>
        </td>
      </tr>`).join('');
  } else {
    cols = [47, 16, 23, 14];
    head = ['Buah', 'Jumlah', 'Status', 'Waktu'];
    body = slice.map(r => `
      <tr>
        <td>${esc(r.buah)}</td>
        <td>${kgFmt(r.jumlah)} kg</td>
        <td><span class="badge ${AB[r.alasan] || 'badge-belum'}">${esc(r.alasan)}</span></td>
        <td>${fmtTanggal(r.waktu)}</td>
      </tr>`).join('');
  }
  if (!slice.length) body = `<tr><td class="empty" colspan="${head.length}">${tab === 'masuk' ? 'Belum ada stok masuk.' : 'Belum ada stok keluar.'}</td></tr>`;

  $('tbl').innerHTML =
    `<table class="dt"><colgroup>${cols.map(c => `<col style="width:${c}%">`).join('')}</colgroup>` +
    `<thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>`;

  renderPager(pages);
}

function renderPager(pages) {
  let nums;
  if (pages <= 6) nums = Array.from({ length: pages }, (_, i) => i + 1);
  else if (page <= 3) nums = [1, 2, 3, 4, '…', pages];
  else if (page >= pages - 2) nums = [1, '…', pages - 3, pages - 2, pages - 1, pages];
  else nums = [1, '…', page - 1, page, page + 1, '…', pages];

  $('pager').innerHTML =
    `<button type="button" data-p="${page - 1}" ${page === 1 ? 'disabled' : ''} aria-label="Sebelumnya">‹</button>` +
    nums.map(n => n === '…'
      ? '<span>…</span>'
      : `<button type="button" data-p="${n}" class="${n === page ? 'cur' : ''}" ${n === page ? 'aria-current="page"' : ''}>${n}</button>`).join('') +
    `<button type="button" data-p="${page + 1}" ${page === pages ? 'disabled' : ''} aria-label="Berikutnya">›</button>` +
    `<select id="pp" aria-label="Baris per halaman">${[5, 10, 20].map(n => `<option value="${n}"${n === perPage ? ' selected' : ''}>${n} / page</option>`).join('')}</select>`;
}

function renderHeader() {
  const masuk = tab === 'masuk';
  $('tabMasuk').className = 'pill-btn ' + (masuk ? 'pill-white' : 'pill-line');
  $('tabKeluar').className = 'pill-btn ' + (masuk ? 'pill-line' : 'pill-white');
  $('tabMasuk').setAttribute('aria-pressed', masuk);
  $('tabKeluar').setAttribute('aria-pressed', !masuk);
  $('addTxt').textContent = masuk ? 'Catat Stok Masuk' : 'Catat Stok Keluar';
  $('addBtn').href = masuk ? 'stok-masuk-baru.html' : 'stok-keluar-baru.html';
}

function render() { renderHeader(); renderCards(); renderChips(); renderTable(); }

async function load() {
  try {
    rows = tab === 'masuk' ? await API.getStockIn() : await API.getStockOut();
    render();
  } catch (e) {
    console.error(e);
    $('tbl').innerHTML = '<p class="empty" style="padding:24px;text-align:center">Gagal memuat data.</p>';
  }
}

function setTab(t) {
  if (t === tab) return;
  tab = t; flt = 'Semua'; page = 1;
  try { history.replaceState(null, '', '?tab=' + t); } catch (e) { /* abaikan */ }
  load();
}

/* ---------- Unduh CSV ---------- */
function exportCsv() {
  const data = filtered();
  const head = tab === 'masuk'
    ? ['Buah', 'Kode', 'Jumlah (kg)', 'Sisa saat ini (kg)', 'Segar (%)', 'Kurang segar (%)', 'Busuk (%)', 'Waktu masuk']
    : ['Buah', 'Jumlah (kg)', 'Alasan', 'Waktu keluar'];
  const lines = data.map(r => tab === 'masuk'
    ? [r.buah, r.id, r.jumlah, r.sisa, ...(r.komposisi || ['', '', '']), fmtTanggal(r.masukPada)]
    : [r.buah, r.jumlah, r.alasan, fmtTanggal(r.waktu)]);
  const csv = '\ufeff' + [head, ...lines].map(l => l.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  a.download = `stok-${tab}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/* ---------- Event ---------- */
$('tabMasuk').addEventListener('click', () => setTab('masuk'));
$('tabKeluar').addEventListener('click', () => setTab('keluar'));
$('dlBtn').addEventListener('click', exportCsv);
$('chips').addEventListener('click', e => {
  const b = e.target.closest('[data-f]');
  if (!b) return;
  flt = b.dataset.f; page = 1;
  renderChips(); renderTable();
});
$('pager').addEventListener('click', e => {
  const b = e.target.closest('[data-p]');
  if (!b || b.disabled) return;
  page = Number(b.dataset.p);
  renderTable();
});
$('pager').addEventListener('change', e => {
  if (e.target.id === 'pp') { perPage = Number(e.target.value); page = 1; renderTable(); }
});
$('tbl').addEventListener('click', async e => {
  const b = e.target.closest('[data-del]');
  if (!b) return;
  const id = b.dataset.del;
  const r = rows.find(x => x.id === id);
  if (!r || !confirm(`Hapus ${r.buah} (${id})? Kiriman ini beserta riwayat scan dan stok keluarnya akan hilang dari daftar dan laporan.`)) return;
  try {
    await API.deleteBatch(id);
    toast(`Kiriman ${id} dihapus.`);
    await load();
  } catch (err) {
    toast(err.message, true);
  }
});

load();