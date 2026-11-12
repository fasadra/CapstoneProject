const form = document.getElementById('loginForm');
const f = {
  email: document.getElementById('email'),
  password: document.getElementById('password'),
};

// Kembalikan pesan error, atau '' kalau valid
const rules = {
  email: v => !v ? 'Isi email dulu'
    : !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? 'Format email belum benar' : '',
  password: v => !v ? 'Isi kata sandi dulu' : '',
};

function check(name) {
  const msg = rules[name](f[name].value.trim());
  document.getElementById(name + '-err').textContent = msg;
  f[name].classList.toggle('invalid', !!msg);
  f[name].setAttribute('aria-invalid', !!msg);
  return !msg;
}

Object.keys(f).forEach(name => {
  f[name].addEventListener('blur', () => check(name));
  f[name].addEventListener('input', () => {
    if (f[name].classList.contains('invalid')) check(name);
  });
});

// Tombol lihat/sembunyikan kata sandi
document.querySelectorAll('[data-toggle]').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.toggle);
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.querySelector('.eye').classList.toggle('hidden', !show);
    btn.querySelector('.eye-off').classList.toggle('hidden', show);
    btn.setAttribute('aria-label', show ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi');
  });
});

// Kirim form ke server
const status = document.getElementById('status');
const submitBtn = form.querySelector('button[type="submit"]');
let busy = false;

function tampilStatus(pesan, galat) {
  status.textContent = pesan;
  status.style.color = galat ? '#B3261E' : '';
}

form.addEventListener('submit', async e => {
  e.preventDefault();
  if (busy) return;
  const valid = Object.keys(f).map(check).every(Boolean);
  if (!valid) {
    form.querySelector('.invalid')?.focus();
    return;
  }

  busy = true;
  submitBtn.disabled = true;
  tampilStatus('Memeriksa...', false);
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: f.email.value.trim(), password: f.password.value }),
    });
    const data = await res.json().catch(() => null);
    if (res.ok) {
      localStorage.setItem('fs_login', '1');          // petunjuk saja; sesi sebenarnya di cookie server
      window.location.href = 'dashboard.html';
      return;
    }
    tampilStatus(typeof data?.detail === 'string' ? data.detail : 'Gagal masuk. Coba lagi.', true);
  } catch (err) {
    tampilStatus('Tidak dapat terhubung ke server.', true);
  }
  busy = false;
  submitBtn.disabled = false;
});
