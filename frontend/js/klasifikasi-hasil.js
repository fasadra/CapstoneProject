const $ = id => document.getElementById(id);
renderTopbar('stok');

const COL = ['#78BE78', '#FFC800', '#C1192E'];
const svg = p => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const IC_OK = svg('<path d="M5 13l4 4L19 7"/>');
const IC_WARN = svg('<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17.5v.01"/>');
const IC_BIN = svg('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>');

let draft = null, ph = 0, hl = -1;     // hl = kelas yang disorot (-1 = semua)

function kosong() {
  $('main').innerHTML =
    '<div class="empty-card"><p>Belum ada hasil klasifikasi. Catat stok masuk dulu untuk melihat hasilnya.</p>' +
    '<a class="pill-btn pill-maroon" href="stok-masuk-baru.html">Catat Stok Masuk</a></div>';
}

function donut(c) {
  const C = 2 * Math.PI * 40;
  let off = 0, s = '';
  c.forEach((p, i) => {
    if (!p) return;
    const len = Math.max(p / 100 * C - 1.5, 0.5);
    const dim = hl !== -1 && hl !== i;
    s += `<circle cx="50" cy="50" r="40" fill="none" stroke="${COL[i]}" stroke-width="19" stroke-dasharray="${len.toFixed(2)} ${C.toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90 50 50)" opacity="${dim ? 0.25 : 1}"/>`;
    off += p / 100 * C;
  });
  return `<svg viewBox="0 0 100 100" role="img" aria-label="Segar ${c[0]}%, kurang segar ${c[1]}%, busuk ${c[2]}%">${s}</svg>`;
}

function tampil() {
  const { buah, jumlah, hasil } = draft;
  const pindai = !!draft.pindaiId;
  const t = hasil.total, fotos = hasil.fotos || [];
  const c = t.c;
  const latin = (API.FRUITS.find(f => f.nama === buah) || {}).latin || '';
  const f = fotos[ph] || {};
  const adaBox = fotos.some(x => x.kotak && x.kotak.length);
  const d = dom(c);
  const label = c[d] >= 50 ? 'mayoritas' : 'terbanyak';

  const box = (f.kotak || []).filter(k => hl === -1 || k.k === hl).map(k =>
    `<i style="left:${k.x * 100}%;top:${k.y * 100}%;width:${k.w * 100}%;height:${k.h * 100}%;border-color:${COL[k.k]}"></i>`).join('');

  const legenda = KELAS.map((n, i) => {
    const isi = `<i class="dot" style="background:${COL[i]}"></i><b>${n}</b><span class="v">: ${c[i]}%</span>`;
    return adaBox
      ? `<button type="button" class="lgrow${hl === i ? ' on' : ''}" data-hl="${i}" aria-pressed="${hl === i}">${isi}</button>`
      : `<div class="lgrow">${isi}</div>`;
  }).join('');

  const poin = [`<li>${IC_OK}<span>Status : ${KELAS[d]} (${label} ${c[d]}%)</span></li>`];
  if (c[1] > 0) poin.push(`<li class="ic-warn">${IC_WARN}<span style="color:#111">${c[1]}% buah kurang segar, jual lebih dulu atau beri diskon</span></li>`);
  if (c[2] > 0) poin.push(`<li class="ic-bin">${IC_BIN}<span style="color:#111">${c[2]}% buah busuk perlu dibuang</span></li>`);

  let alert = '';
  if (c[1] > 0 || c[2] > 0) {
    const bagian = [c[2] > 0 ? `busuk (${c[2]}%)` : '', c[1] > 0 ? `kurang segar (${c[1]}%)` : ''].filter(Boolean).join(' dan ');
    alert = `<p class="al">Pisahkan buah ${bagian} ke wadah terpisah, lalu tekan "Foto Ulang" untuk memastikan hasilnya.</p>`;
  }

  $('main').innerHTML = `
    <div class="res-wrap">
      <div class="res-in">
        <div>
          <div class="photo">
            ${f.url ? `<img src="${f.url}" alt="Foto ${ph + 1} ${esc(buah)}">` : '<div class="noimg">Tidak ada foto</div>'}
            ${box ? `<div class="boxes">${box}</div>` : ''}
          </div>
          <div class="pcap">
            ${fotos.map((_, i) => `<button type="button" class="pn${ph === i ? ' on' : ''}" data-ph="${i}" aria-label="Foto ${i + 1}">${i + 1}</button>`).join('')}
            <b>Foto ${ph + 1} dari ${fotos.length} : ${f.n || 0} buah</b>
          </div>
        </div>
        <div class="info">
          <h1>${esc(buah)}</h1>
          <p class="latin">${esc(latin)}</p>
          ${pindai ? `<p class="latin">Pindai ulang kiriman ${esc(draft.pindaiId)}</p>` : ''}
          <p class="jml">${pindai ? 'Sisa stok (kg)' : 'Jumlah (kg)'} : <span>${kgFmt(jumlah)} kg</span></p>
          <h2>Status</h2>
          <div class="comp-block"><div class="donut">${donut(c)}</div><div class="leg">${legenda}</div></div>
          <p class="note"><span class="star">*</span>Dari ${t.n} buah yang terlihat di ${fotos.length} foto.${adaBox ? ' Klik kelas untuk menyorotnya di foto.' : ''}</p>
          ${pindai && draft.sebelumnya ? `<p class="note">Pindai sebelumnya (${draft.lapisSebelumnya || 0} lapis): ${KELAS.map((n, i) => `${n} ${draft.sebelumnya[i]}%`).join(', ')}.</p>` : ''}
          <h2>Hasil Analisis</h2>
          <ul class="points">${poin.join('')}</ul>
          <h2>Petunjuk Penyimpanan</h2>
          <p class="tip">Simpan yang segar di lemari es agar tahan lebih lama. Buah kurang segar sebaiknya dijual dalam satu atau dua hari.</p>
          ${alert}
        </div>
      </div>
      <div class="res-actions">
        <a class="pill-btn pill-ghost" href="${pindai ? 'stok-masuk-baru.html?pindai=' + encodeURIComponent(draft.pindaiId) : 'stok-masuk-baru.html?ulang=1'}">Foto Ulang</a>
        <button id="simpan" class="pill-btn pill-white" type="button">Simpan</button>
      </div>
    </div>`;
}

document.addEventListener('click', async e => {
  const p = e.target.closest('[data-ph]');
  if (p) { ph = Number(p.dataset.ph); tampil(); return; }
  const h = e.target.closest('[data-hl]');
  if (h) { const i = Number(h.dataset.hl); hl = hl === i ? -1 : i; tampil(); return; }
  if (e.target.closest('#simpan')) {
    const btn = $('simpan');
    btn.disabled = true;
    try {
      // Satu foto = satu lapis. Hasil tiap foto dikirim apa adanya; server menyimpannya sebagai putaran pertama.
      const lapis = (draft.hasil.fotos || []).map(f => ({ hitung: f.hitung, kotak: f.kotak || [] }));
      if (draft.pindaiId) {                       // scan ulang: jadi putaran baru kiriman yang sudah ada
        const r = await API.pindaiUlang(draft.pindaiId, lapis);
        sessionStorage.removeItem('fs_draft');
        flash(`Hasil pindai ${draft.pindaiId} tersimpan (putaran ${r.putaran}, ${r.lapis} lapis).`);
        location.href = `stok-detail.html?id=${encodeURIComponent(draft.pindaiId)}`;
        return;
      }
      const { id } = await API.addBatch({ buah: draft.buah, jumlah: draft.jumlah, lapis });
      sessionStorage.removeItem('fs_draft');
      flash(`Kiriman ${id} berhasil disimpan.`);
      location.href = 'stok.html';
    } catch (err) {
      toast(err.message, true);
      btn.disabled = false;
    }
  }
});

try { draft = JSON.parse(sessionStorage.getItem('fs_draft')); } catch (e) { /* abaikan */ }
if (draft && draft.buah && draft.hasil && draft.hasil.total) tampil(); else kosong();