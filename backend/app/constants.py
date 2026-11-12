"""Konstanta domain FreshSense AI. Satu sumber kebenaran untuk daftar buah, kelas, dan alasan."""

# Buah yang didukung (keputusan: Apel, Jeruk, Anggur).
FRUITS = ("Apel", "Jeruk", "Anggur")
KODE = {"Apel": "APL", "Jeruk": "JRK", "Anggur": "AGR"}
LATIN = {
    "Apel": "Malus domestica",
    "Jeruk": "Citrus × sinensis",
    "Anggur": "Vitis vinifera",
}

# Kelas hasil klasifikasi (urutan sama dengan komposisi [segar, kurang, busuk] di frontend).
KELAS_SEGAR, KELAS_KURANG, KELAS_BUSUK = 0, 1, 2
KELAS_NAMA = ("Segar", "Kurang segar", "Busuk")

# Alasan stok keluar.
ALASAN = ("Terjual", "Terbuang")

# Peran pengguna.
ROLES = ("admin", "staf")

# Ambang notifikasi bawaan (persen). Nilai aktif disimpan di tabel `settings`.
DEFAULT_SETTINGS = {
    "notif_kurang": "30",   # notifikasi bila kurang segar >= 30%
    "notif_busuk": "20",    # notifikasi bila busuk >= 20%
}


def sql_in(values) -> str:
    """Bentuk daftar nilai untuk CHECK ... IN (...)."""
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)
