const $ = id => document.getElementById(id);
renderTopbar('stok');

const svg = p => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const IC = {
  in:   svg('<path d="M17 7 7 17M7 8v9h9"/>'),
  out:  svg('<path d="M7 17 17 7M8 7h9v9"/>'),
  scan: svg('<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="3"/>'),
};

function baris(e) {
  let judul, kanan;
  if (e.k === 'in')  { judul = `Masuk ${kgFmt(e.q)} kg`; kanan = `<b class="sisa">Sisa ${kgFmt(e.sisa)} kg</b>`; }
  if (e.k === 'out') { judul = `${esc(e.r)} ${kgFmt(e.q)} kg`; kanan = `<b class="sisa">Sisa ${kgFmt(e.sisa)} kg</b>`; }
  if (e.k === 'scan') { judul = 'Pindai kesegaran' + (e.lapis ? ` <span style="font-weight:400;color:#777">· ${e.lapis} lapis, ${e.n} buah</span>` : ''); kanan = compPills(e.c); }
  return `<li><span class="tl-ic ${e.k}">${IC[e.k]}</span><div class="tl-text"><b>${judul}</b>${fmtTanggal(e.t)}</div>${kanan}</li>`;
}

function tampil(b) {
  $('main').innerHTML = `
    <section class="detail-card">
      <a class="pill-btn pill-white back" href="stok.html">${svg('<path d="M15 6l-6 6 6 6"/>')} Kembali</a>
      <div class="d-head">
        <div><h1>${esc(b.buah)}</h1><p class="latin">${esc(b.latin)}</p></div>
        ${compPills(b.komposisi, true)}
      </div>
      ${b.sisa > 0
        ? `<div style="display:flex;justify-content:flex-end;margin:0 0 14px"><a class="pill-btn pill-maroon" href="stok-masuk-baru.html?pindai=${encodeURIComponent(b.id)}">Pindai Ulang</a></div>`
        : ''}
      <div class="sum three">
        <div class="sum-card"><span class="l">Total Masuk</span><span class="v">${kgFmt(b.jumlah)} kg</span></div>
        <div class="sum-card"><span class="l">Total Keluar</span><span class="v">${kgFmt(b.keluar)} kg</span></div>
        <div class="sum-card"><span class="l">Sisa saat ini</span><span class="v">${kgFmt(b.sisa)} kg</span></div>
      </div>
      <div class="hist">
        <h2>Riwayat Batch <span style="font-weight:400;color:#777">${esc(b.id)}</span></h2>
        <ul class="tl">${b.riwayat.map(baris).join('')}</ul>
      </div>
    </section>`;
}

(async () => {
  const id = new URLSearchParams(location.search).get('id');
  let b = null;
  try { b = id ? await API.getBatch(id) : null; } catch (e) { toast(e.message, true); }
  if (!b) {
    $('main').innerHTML = '<div class="empty-card"><p>Kiriman tidak ditemukan.</p><a class="pill-btn pill-maroon" href="stok.html">Kembali ke Stok</a></div>';
    return;
  }
  tampil(b);
})();