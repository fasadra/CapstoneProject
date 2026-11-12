import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .routers import auth, dashboard, stok
from .security import secret_is_weak

# Kunci contoh/terlalu pendek membuat cookie sesi bisa dipalsukan.
if secret_is_weak():
    if settings.cookie_secure:     # cookie_secure = tanda mode produksi (HTTPS)
        raise RuntimeError("SECRET_KEY lemah. Buat dengan: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
    logging.getLogger("uvicorn.error").warning(
        "SECRET_KEY masih nilai contoh / kurang dari 32 karakter. Aman untuk uji lokal, "
        "tapi ganti di file .env sebelum dipakai sungguhan.")

app = FastAPI(title="FreshSense AI API", version="0.2.0")


class NoCacheStatic(StaticFiles):
    """File frontend selalu divalidasi ulang ke server (ETag), jadi perubahan JS/HTML langsung terpakai
    dan browser tidak menyimpan salinan lama berjam-jam. Kalau file tidak berubah, server cukup menjawab 304."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


@app.get("/api/health", tags=["sistem"])
def health(db: Session = Depends(get_db)):
    """Cek bahwa server hidup dan database bisa dijangkau."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database tidak dapat dijangkau")
    return {"status": "ok", "db": True}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/landing.html")


# Router fitur. Semua harus didaftarkan SEBELUM mount statis di bawah.
app.include_router(auth.router)          # Tahap 3: akun
app.include_router(stok.router)          # Tahap 4a: stok masuk & keluar
app.include_router(dashboard.router)     # Tahap 4b: dashboard, analisis, laporan, notifikasi

# Sajikan frontend (HTML/CSS/JS/gambar) dari folder yang sama dengan API -> tidak perlu CORS.
_frontend = Path(settings.frontend_dir).resolve()
if _frontend.is_dir():
    app.mount("/", NoCacheStatic(directory=_frontend, html=True), name="frontend")
