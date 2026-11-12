const $ = id => document.getElementById(id);
renderTopbar('laporan');

const BLN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
const ymd = d => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const tgl = s => { const d = new Date(s + 'T00:00:00'); return `${d.getDate()} ${BLN[d.getMonth()]}`; };

let periode = 'minggu';           // 'minggu' | 'bulan' | 'custom'
let custom = null;                // { from, to } (YYYY-MM-DD)
let rows = [], ringkas = null, page = 1, perPage = 5;

function setButtons() {
  const kelas = p => 'pill-btn ' + (periode === p ? 'pill-white' : 'pill-line');
  $('pMinggu').className = kelas('minggu');
  $('pBulan').className = kelas('bulan');
  $('pTanggal').className = kelas('custom');
  $('pMinggu').setAttribute('aria-pressed', periode === 'minggu');
  $('pBulan').setAttribute('aria-pressed', periode === 'bulan');
  $('pTanggal').setAttribute('aria-pressed', periode === 'custom');
  $('tglTxt').textContent = periode === 'custom' ? `${tgl(custom.from)} – ${tgl(custom.to)} ${custom.to.slice(0, 4)}` : 'Pilih Tanggal';
}

function renderCards() {
  const c = (l, v) => `<div class="sum-card"><span class="l">${l}</span><span class="v">${kgFmt(v)} kg</span></div>`;
  $('sum').className = 'sum';
  $('sum').innerHTML = c('Total Masuk', ringkas.masuk) + c('Terjual', ringkas.terjual) + c('Terbuang', ringkas.terbuang);
}

function renderTable() {
  const pages = Math.max(1, Math.ceil(rows.length / perPage));
  if (page > pages) page = pages;
  const slice = rows.slice((page - 1) * perPage, page * perPage);
  const cols = [32, 17, 17, 17, 17];
  const head = ['Buah', 'Masuk', 'Terjual', 'Terbuang', 'Sisa'];
  const body = slice.length
    ? slice.map(r => `
      <tr>
        <td>${esc(r.buah)}</td>
        <td>${kgFmt(r.masuk)} kg</td>
        <td>${kgFmt(r.terjual)} kg</td>
        <td>${kgFmt(r.terbuang)} kg</td>
        <td>${kgFmt(r.sisa)} kg</td>
      </tr>`).join('')
    : `<tr><td class="empty" colspan="${head.length}">Tidak ada data pada periode ini.</td></tr>`;

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

async function load() {
  try {
    const r = await API.getReport(periode === 'custom' ? custom : periode);
    rows = r.rows;
    ringkas = r.ringkas;
    renderCards();
    renderTable();
  } catch (e) {
    console.error(e);
    $('tbl').innerHTML = '<p class="empty-note">Gagal memuat data.</p>';
  }
}

function setPeriode(p) { periode = p; page = 1; setButtons(); load(); }
$('pMinggu').addEventListener('click', () => setPeriode('minggu'));
$('pBulan').addEventListener('click', () => setPeriode('bulan'));

/* ---------- Pilih tanggal ---------- */
const pop = $('pop'), tBtn = $('pTanggal');
function openPop() {
  const hariIni = new Date(), awal = new Date();
  awal.setDate(awal.getDate() - 6);
  $('dari').max = $('sampai').max = ymd(hariIni);
  $('dari').value = custom ? custom.from : ymd(awal);
  $('sampai').value = custom ? custom.to : ymd(hariIni);
  pop.hidden = false;
  tBtn.setAttribute('aria-expanded', 'true');
  $('dari').focus();
}
function closePop() {
  pop.hidden = true;
  tBtn.setAttribute('aria-expanded', 'false');
  $('err-tgl').textContent = '';
}
tBtn.addEventListener('click', () => (pop.hidden ? openPop() : closePop()));
document.addEventListener('click', e => { if (!pop.hidden && !e.target.closest('.pop-wrap')) closePop(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !pop.hidden) { closePop(); tBtn.focus(); } });
$('batalTgl').addEventListener('click', closePop);
$('terapkan').addEventListener('click', () => {
  const a = $('dari').value, b = $('sampai').value;
  if (!a || !b) { $('err-tgl').textContent = 'Isi tanggal mulai dan tanggal akhir'; return; }
  if (a > b) { $('err-tgl').textContent = 'Tanggal mulai tidak boleh setelah tanggal akhir'; return; }
  custom = { from: a, to: b };
  closePop();
  setPeriode('custom');
});

/* ---------- Unduh CSV ---------- */
$('dlBtn').addEventListener('click', () => {
  const head = ['Buah', 'Masuk (kg)', 'Terjual (kg)', 'Terbuang (kg)', 'Sisa (kg)'];
  const lines = rows.map(r => [r.buah, r.masuk, r.terjual, r.terbuang, r.sisa]);
  const csv = '\ufeff' + [head, ...lines].map(l => l.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\r\n');
  const nama = periode === 'custom' ? `${custom.from}_sd_${custom.to}` : (periode === 'minggu' ? 'minggu-ini' : 'bulan-ini');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  a.download = `laporan-stok-${nama}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
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

setButtons();
load();