const $ = id => document.getElementById(id);
renderTopbar('notif');

const svg = p => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const ICO = {
  busuk:  svg('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>'),
  kurang: svg('<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17.5v.01"/>'),
};
const FILTERS = ['Semua', 'Belum Dibaca', 'Kurang Segar', 'Busuk'];
let flt = 'Semua', list = [];

function tampil() {
  const data = list.filter(n =>
    flt === 'Semua' ||
    (flt === 'Belum Dibaca' && !n.dibaca) ||
    (flt === 'Kurang Segar' && n.type === 'kurang') ||
    (flt === 'Busuk' && n.type === 'busuk'));

  $('chips').innerHTML = FILTERS.map(f =>
    `<button type="button" class="fchip${f === flt ? ' on' : ''}" data-f="${f}">${f}</button>`).join('');

  if (!data.length) {
    $('list').innerHTML = `<p class="empty-note">${flt === 'Semua' ? 'Belum ada notifikasi.' : 'Tidak ada notifikasi di kategori ini.'}</p>`;
    return;
  }
  const hariIni = new Date();
  const kelompok = n => (sameDay(new Date(n.waktu), hariIni) ? 'Hari Ini' : 'Sebelumnya');

  $('list').innerHTML = ['Hari Ini', 'Sebelumnya'].map(g => {
    const items = data.filter(n => kelompok(n) === g);
    if (!items.length) return '';
    return `<section class="ngroup"><h2>${g}</h2>` + items.map(n => `
      <a class="nrow${n.dibaca ? '' : ' unread'}" href="stok-detail.html?id=${encodeURIComponent(n.batch)}" data-id="${esc(n.id)}">
        <span class="nic ${n.type}">${ICO[n.type]}</span>
        <span class="ntxt"><b>${esc(notifText(n, false))}</b><span>${waktuRelatif(n.waktu)}</span></span>
        ${n.dibaca ? '' : '<span class="udot"></span><span class="sr-only">Belum dibaca</span>'}
      </a>`).join('') + '</section>';
  }).join('');
}

async function load() {
  try {
    list = await API.getNotifications();
    tampil();
  } catch (e) {
    console.error(e);
    $('list').innerHTML = '<p class="empty-note">Gagal memuat notifikasi.</p>';
  }
}

$('chips').addEventListener('click', e => {
  const b = e.target.closest('[data-f]');
  if (!b) return;
  flt = b.dataset.f;
  tampil();
});

// Klik notifikasi: tandai dibaca, lalu buka detail kiriman
$('list').addEventListener('click', e => {
  const a = e.target.closest('[data-id]');
  if (a) API.markRead(a.dataset.id);
});

$('readAll').addEventListener('click', async () => {
  try {
    await API.markAllRead();
    toast('Semua notifikasi ditandai dibaca.');
    await load();
    refreshBell();
  } catch (e) {
    toast(e.message, true);
  }
});

load();