const $ = id => document.getElementById(id);
renderTopbar('stok');

const MODE = document.body.dataset.page;                       // 'masuk' | 'keluar'
const params = new URLSearchParams(location.search);
const editId = params.get('edit');
const ulang = params.get('ulang');                             // kembali dari "Foto Ulang"
const pindai = params.get('pindai');                           // scan ulang kiriman yang sudah ada (id kiriman)
const MIN_FOTO = 1;                                            // foto minimal
const MAX_FOTO = 24;                                           // foto (lapis) maksimal per kiriman
const MAX_MB = 10;

let files = [], alasan = 'Terjual', busy = false, tersedia = {}, batchPindai = null, TEKS_SIMPAN = 'Simpan';

function setErr(field, msg) {
  const e = $('err-' + field);
  if (e) e.textContent = msg || '';
  const input = $(field);
  if (input) input.classList.toggle('bad', !!msg);
}

/* ---------- Waktu otomatis ---------- */
function tick() { $('waktu').textContent = 'Otomatis : ' + fmtSekarang(); }
tick();
const timer = setInterval(tick, 30000);

/* ---------- Angka dengan panah ---------- */
document.querySelectorAll('[data-step]').forEach(b => b.addEventListener('click', () => {
  const v = Math.max(0, (Number($('jumlah').value) || 0) + Number(b.dataset.step));
  $('jumlah').value = v || '';
  setErr('jumlah', '');
  if (MODE === 'keluar') updateHint();
}));

/* ---------- Petunjuk di bawah kolom buah ---------- */
function updateHint() {
  const h = $('hintBuah');
  const v = $('buah').value;
  if (MODE === 'keluar') {
    if (!v) { h.hidden = true; return; }
    h.hidden = false;
    h.className = 'hint';
    h.textContent = `Stok tersedia: ${kgFmt(tersedia[v] || 0)} kg. Dikurangi dari kiriman terlama dulu.`;
    return;
  }
  if (pindai && batchPindai) {
    h.hidden = false;
    h.className = 'hint';
    h.textContent = `Foto semua lapis yang masih ada (satu foto = satu lapis). Pindai terakhir: ${batchPindai.lapisTerakhir || 0} lapis.`;
    return;
  }
  if (editId) {
    h.hidden = false;
    h.className = 'hint';
    h.textContent = 'Jenis buah tidak bisa diubah. Kalau salah jenis, hapus kiriman ini lalu catat ulang.';
  } else {
    h.hidden = true;
  }
}

/* ---------- Satu kotak unggah, boleh banyak foto (stok masuk) ---------- */
const DOC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></svg>';
const CEK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>';

function renderThumbs() {
  $('fileList').innerHTML = files.map((f, i) =>
    `<div class="frow"><span class="fic">${DOC}</span>` +
    `<span class="ftxt"><b title="${esc(f.name)}">${esc(f.name)}</b><small>${(f.size / 1048576).toFixed(1)}MB | Siap</small></span>` +
    `<span class="fok">${CEK}</span>` +
    `<button type="button" class="fx" data-rm="${i}" aria-label="Hapus ${esc(f.name)}">✕</button></div>`).join('');
}

function tambahFoto(list) {
  const errs = [];
  [...list].forEach(file => {
    if (files.length >= MAX_FOTO) { if (!errs.includes(`Maksimal ${MAX_FOTO} foto`)) errs.push(`Maksimal ${MAX_FOTO} foto`); return; }
    if (!/^image\/(jpeg|png)$/.test(file.type)) { errs.push(`${file.name}: format harus JPG atau PNG`); return; }
    if (file.size > MAX_MB * 1024 * 1024) { errs.push(`${file.name}: ukuran lebih dari ${MAX_MB}MB`); return; }
    files.push({ file, name: file.name, size: file.size, url: URL.createObjectURL(file) });
  });
  $('err-foto').textContent = errs.join('. ');
  renderThumbs();
}

/* ---------- Simpan ---------- */
function bacaJumlah() {
  const v = Number($('jumlah').value);
  if (!$('jumlah').value || !isFinite(v) || v <= 0) return null;
  return Math.round(v * 10) / 10;
}

async function simpanMasuk() {
  const buah = $('buah').value;
  const jumlah = pindai && batchPindai ? batchPindai.sisa : bacaJumlah();
  let ok = true;
  setErr('buah', ''); setErr('jumlah', '');
  $('err-foto').textContent = '';

  if (!API.SUPPORTED.includes(buah)) { setErr('buah', 'Pilih jenis buah dulu'); ok = false; }
  if (jumlah === null) { setErr('jumlah', 'Isi jumlah dalam kg'); ok = false; }

  if (!editId && files.length < MIN_FOTO) { $('err-foto').textContent = 'Unggah minimal satu foto'; ok = false; }
  if (!ok) return;

  busy = true; $('simpan').disabled = true; $('simpan').textContent = 'Memproses...';
  try {
    if (editId) {
      await API.updateBatch(editId, { buah, jumlah });
      flash(`Kiriman ${editId} diperbarui.`);
      location.href = 'stok.html';
      return;
    }
    const hasil = await API.classify(files.map(f => f.file), buah);
    const draft = { buah, jumlah, hasil };
    if (pindai && batchPindai) {                      // hasil ini akan disimpan sebagai putaran baru kiriman yang ada
      draft.pindaiId = pindai;
      draft.sebelumnya = batchPindai.komposisi;
      draft.lapisSebelumnya = batchPindai.lapisTerakhir;
    }
    sessionStorage.setItem('fs_draft', JSON.stringify(draft));
    location.href = 'klasifikasi-hasil.html';
  } catch (e) {
    toast(e.message, true);
    busy = false; $('simpan').disabled = false; $('simpan').textContent = TEKS_SIMPAN;
  }
}

async function simpanKeluar() {
  const buah = $('buah').value, jumlah = bacaJumlah();
  let ok = true;
  setErr('buah', ''); setErr('jumlah', ''); setErr('alasan', '');
  if (!buah) { setErr('buah', 'Pilih jenis buah dulu'); ok = false; }
  if (jumlah === null) { setErr('jumlah', 'Isi jumlah dalam kg'); ok = false; }
  else if (buah && jumlah > (tersedia[buah] || 0)) { setErr('jumlah', `Melebihi stok tersedia (${kgFmt(tersedia[buah] || 0)} kg)`); ok = false; }
  if (!alasan) { setErr('alasan', 'Pilih alasan keluar'); ok = false; }
  if (!ok) return;

  busy = true; $('simpan').disabled = true;
  try {
    await API.addStockOut({ buah, jumlah, alasan });
    flash(`${kgFmt(jumlah)} kg ${buah} dicatat ${alasan.toLowerCase()}.`);
    location.href = 'stok.html?tab=keluar';
  } catch (e) {
    toast(e.message, true);
    busy = false; $('simpan').disabled = false;
  }
}

/* ---------- Mulai ---------- */
async function init() {
  if (MODE === 'masuk') {
    $('buah').innerHTML = '<option value="" disabled selected>Pilih Buah</option>' +
      API.FRUITS.map(f => `<option value="${esc(f.nama)}">${esc(f.nama)}</option>`).join('');
    if (pindai) {
      const b = await API.getBatch(pindai);
      if (!b) { toast('Kiriman tidak ditemukan.', true); setTimeout(() => { location.href = 'stok.html'; }, 1200); return; }
      if (b.sisa <= 0) { toast('Stok kiriman ini sudah habis, tidak perlu dipindai ulang.', true); setTimeout(() => { location.href = `stok-detail.html?id=${encodeURIComponent(b.id)}`; }, 1500); return; }
      const scans = b.riwayat.filter(e => e.k === 'scan');
      batchPindai = { id: b.id, sisa: b.sisa, komposisi: b.komposisi, lapisTerakhir: scans.length ? scans[scans.length - 1].lapis : 0 };
      $('judul').textContent = `Pindai Ulang ${b.id}`;
      $('buah').value = b.buah;
      $('buah').disabled = true;
      $('jumlah').closest('.field2').style.display = 'none';      // jumlah tidak diubah saat pindai ulang
      $('waktu').previousElementSibling.firstChild.textContent = 'Waktu Pindai';
      document.querySelector('.form-actions a').href = `stok-detail.html?id=${encodeURIComponent(b.id)}`;
      TEKS_SIMPAN = 'Pindai';
      $('simpan').textContent = TEKS_SIMPAN;
    } else if (editId) {
      const b = await API.getBatch(editId);
      if (!b) { toast('Kiriman tidak ditemukan.', true); setTimeout(() => { location.href = 'stok.html'; }, 1200); return; }
      $('judul').textContent = 'Ubah Stok Masuk';
      $('buah').value = b.buah;
      $('buah').disabled = true;                 // jenis buah tidak bisa diubah
      $('jumlah').value = b.jumlah;
      clearInterval(timer);
      $('waktu').textContent = 'Masuk : ' + fmtTanggal(b.masukPada);
      $('fotoBox').hidden = true;
    } else if (ulang) {
      // Kembali dari halaman hasil lewat "Foto Ulang": isian dipertahankan, foto dikosongkan
      try {
        const d = JSON.parse(sessionStorage.getItem('fs_draft'));
        if (d) { $('buah').value = d.buah; $('jumlah').value = d.jumlah; }
      } catch (e) { /* abaikan */ }
    }
    updateHint();
  } else {
    let rows;
    try { rows = await API.getStockIn(); } catch (e) { toast(e.message, true); return; }
    rows.forEach(r => { tersedia[r.buah] = Math.round(((tersedia[r.buah] || 0) + r.sisa) * 10) / 10; });
    const opsi = Object.keys(tersedia).filter(k => tersedia[k] > 0);
    $('buah').innerHTML = '<option value="" disabled selected>Pilih Buah</option>' +
      opsi.map(k => `<option value="${esc(k)}">${esc(k)} (${kgFmt(tersedia[k])} kg)</option>`).join('');
  }
}

if (MODE === 'masuk') {
  $('buah').addEventListener('change', () => { setErr('buah', ''); updateHint(); });
  $('jumlah').addEventListener('input', () => setErr('jumlah', ''));

  const input = $('fotoInput'), drop = $('drop');
  input.addEventListener('change', () => { tambahFoto(input.files); input.value = ''; });   // kosongkan agar bisa pilih lagi
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, () => drop.classList.remove('drag')));
  drop.addEventListener('drop', e => { e.preventDefault(); tambahFoto(e.dataTransfer.files); });
  $('fileList').addEventListener('click', e => {
    const b = e.target.closest('[data-rm]');
    if (!b) return;
    const i = Number(b.dataset.rm);
    URL.revokeObjectURL(files[i].url);
    files.splice(i, 1);
    $('err-foto').textContent = '';
    renderThumbs();
  });
} else {
  $('buah').addEventListener('change', () => { setErr('buah', ''); updateHint(); });
  $('jumlah').addEventListener('input', () => setErr('jumlah', ''));
  $('alasan').addEventListener('click', e => {
    const b = e.target.closest('[data-a]');
    if (!b) return;
    alasan = b.dataset.a;
    setErr('alasan', '');
    $('alasan').querySelectorAll('.rchip').forEach(x => {
      const on = x === b;
      x.classList.toggle('on', on);
      x.setAttribute('aria-pressed', on);
    });
  });
}
$('simpan').addEventListener('click', () => { if (!busy) (MODE === 'masuk' ? simpanMasuk() : simpanKeluar()); });

init().catch(e => toast(e.message, true));