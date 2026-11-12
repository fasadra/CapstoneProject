"""Pengujian memakai SQLite di memori (cepat, tanpa Postgres).
Untuk menguji ke PostgreSQL sungguhan:  TEST_DATABASE_URL=postgresql+psycopg://... pytest
"""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import make_engine
from app.models import Base

TEST_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


@pytest.fixture()
def engine():
    if TEST_URL.startswith("sqlite"):
        # satu koneksi bersama agar database memori tidak hilang antar sesi
        from sqlalchemy import create_engine, event
        eng = create_engine(TEST_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(eng, "connect")
        def _fk(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    else:
        eng = make_engine(TEST_URL)
        with eng.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        yield session
