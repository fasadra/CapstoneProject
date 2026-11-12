from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Nilai dibaca dari environment, lalu dari file .env (di backend/ atau di root proyek).
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://freshsense:freshsense@localhost:5432/freshsense"
    frontend_dir: str = "../frontend"
    secret_key: str = "ganti-di-env"   # kunci penandatangan cookie sesi (WAJIB diganti, lihat .env.example)
    timezone: str = "Asia/Jakarta"      # zona waktu tampilan; database selalu menyimpan UTC

    # --- Sesi login (Tahap 3) ---
    cookie_name: str = "fs_session"
    session_hours: int = 12             # lama sesi sejak login
    cookie_secure: bool = False         # isi true saat memakai HTTPS (produksi)


settings = Settings()
