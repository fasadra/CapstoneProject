const form = document.getElementById('registerForm');
const f = {
  email: document.getElementById('email'),
  password: document.getElementById('password'),
  confirm: document.getElementById('confirm'),
};

// Kembalikan pesan error, atau '' kalau valid
const rules = {
  email: v => !v ? 'Isi email dulu'
    : !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? 'Format email belum benar' : '',
  password: v => !v ? 'Isi kata sandi dulu'
    : v.length < 8 ? 'Kata sandi minimal 8 karakter' : '',
  confirm: v => !v ? 'Ulangi kata sandi'
    : v !== f.password.value ? 'Kata sandi tidak cocok' : '',
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
    if (name === 'password' && f.confirm.value) check('confirm');
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
  tampilStatus('Membuat akun...', false);
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: f.email.value.trim(), password: f.password.value }),
    });
    const data = await res.json().catch(() => null);
    if (res.status === 201) {
      tampilStatus('Akun berhasil dibuat. Mengarahkan ke halaman masuk...', false);
      setTimeout(() => { window.location.href = 'login.html'; }, 1500);
      return;
    }
    if (res.status === 409) {                         // email sudah terdaftar -> tandai di kolom email
      tampilStatus('', false);
      document.getElementById('email-err').textContent = data?.detail || 'Email sudah terdaftar';
      f.email.classList.add('invalid');
      f.email.setAttribute('aria-invalid', 'true');
      f.email.focus();
    } else {
      tampilStatus(typeof data?.detail === 'string' ? data.detail : 'Data belum benar. Periksa isian lalu coba lagi.', true);
    }
  } catch (err) {
    tampilStatus('Tidak dapat terhubung ke server.', true);
  }
  busy = false;
  submitBtn.disabled = false;
});
