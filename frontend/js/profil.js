const $ = id => document.getElementById(id);
renderTopbar('profil');

const MODE = document.body.dataset.page;      // 'profil' | 'sandi'
let busy = false;

function setErr(field, msg) {
  $('err-' + field).textContent = msg || '';
  $(field).classList.toggle('bad', !!msg);
}
function kembali() {
  if (document.referrer && history.length > 1) history.back();
  else location.href = 'dashboard.html';
}
$('batal').addEventListener('click', kembali);

/* ---------- Profil ---------- */
async function initProfil() {
  const p = await API.getProfile();
  ['nama', 'username', 'email', 'telepon', 'role'].forEach(k => { $(k).value = p[k] || ''; });

  $('simpan').addEventListener('click', async () => {
    if (busy) return;
    const v = { nama: $('nama').value.trim(), username: $('username').value.trim(), email: $('email').value.trim(), telepon: $('telepon').value.trim() };
    const aturan = {
      nama: v.nama ? '' : 'Isi nama dulu',
      username: /^[A-Za-z0-9_.]{3,20}$/.test(v.username) ? '' : 'Username 3 sampai 20 karakter (huruf, angka, titik, garis bawah)',
      email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.email) ? '' : 'Format email belum benar',
      telepon: /^\+?[0-9\s-]{8,16}$/.test(v.telepon) ? '' : 'Nomor telepon belum benar',
    };
    let ok = true;
    Object.keys(aturan).forEach(k => { setErr(k, aturan[k]); if (aturan[k]) ok = false; });
    if (!ok) { document.querySelector('.in2.bad')?.focus(); return; }

    busy = true;
    try {
      await API.saveProfile(v);
      toast('Profil berhasil disimpan.');
    } catch (e) {
      toast(e.message, true);
    }
    busy = false;
  });
  ['nama', 'username', 'email', 'telepon'].forEach(k => $(k).addEventListener('input', () => setErr(k, '')));
}

/* ---------- Ubah kata sandi ---------- */
function tambahMata(box) {
  const input = box.querySelector('input');
  const lihat = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>';
  const tutup = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.9 17.9A10.1 10.1 0 0 1 12 19c-6.5 0-10-7-10-7a18 18 0 0 1 4.1-5M9.9 5.1A9.7 9.7 0 0 1 12 5c6.5 0 10 7 10 7a18 18 0 0 1-2.2 3.2M1 1l22 22M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'toggle'; b.innerHTML = tutup;
  b.setAttribute('aria-label', 'Tampilkan kata sandi');
  b.addEventListener('click', () => {
    const tampil = input.type === 'password';
    input.type = tampil ? 'text' : 'password';
    b.innerHTML = tampil ? lihat : tutup;
    b.setAttribute('aria-label', tampil ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi');
  });
  box.appendChild(b);
}

function initSandi() {
  document.querySelectorAll('.pw').forEach(tambahMata);
  ['lama', 'baru', 'konfirmasi'].forEach(k => $(k).addEventListener('input', () => setErr(k, '')));

  $('simpan').addEventListener('click', async () => {
    if (busy) return;
    const lama = $('lama').value, baru = $('baru').value, konf = $('konfirmasi').value;
    const aturan = {
      lama: lama ? '' : 'Isi kata sandi lama',
      baru: !baru ? 'Isi kata sandi baru' : baru.length < 8 ? 'Kata sandi minimal 8 karakter' : baru === lama ? 'Kata sandi baru harus berbeda dari yang lama' : '',
      konfirmasi: !konf ? 'Ulangi kata sandi baru' : konf !== baru ? 'Kata sandi tidak cocok' : '',
    };
    let ok = true;
    Object.keys(aturan).forEach(k => { setErr(k, aturan[k]); if (aturan[k]) ok = false; });
    if (!ok) { document.querySelector('.in2.bad')?.focus(); return; }

    busy = true; $('simpan').disabled = true;
    try {
      await API.changePassword(lama, baru);
      flash('Kata sandi berhasil diubah.');
      location.href = 'profil.html';
    } catch (e) {
      setErr('lama', e.message || 'Kata sandi lama salah');
      busy = false; $('simpan').disabled = false;
    }
  });
}

if (MODE === 'profil') initProfil(); else initSandi();