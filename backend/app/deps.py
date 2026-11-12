"""Dependency FastAPI: pengguna yang sedang login."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User
from .security import fingerprint_matches, read_session_token


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.cookie_name)
    parsed = read_session_token(token) if token else None
    user = db.get(User, parsed[0]) if parsed else None
    if user is None or not fingerprint_matches(parsed[1], user.password_hash):
        raise HTTPException(status_code=401, detail="Belum login atau sesi sudah berakhir")
    return user
