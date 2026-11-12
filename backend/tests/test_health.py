from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": True}


def test_health_503_bila_database_mati(client):
    class Rusak:
        def execute(self, *a, **k):
            raise RuntimeError("db mati")

    app.dependency_overrides[get_db] = lambda: Rusak()
    r = client.get("/api/health")
    assert r.status_code == 503


def test_root_mengarah_ke_landing(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/landing.html"


@pytest.mark.skipif(not Path(settings.frontend_dir).is_dir(), reason="folder frontend tidak ditemukan")
@pytest.mark.parametrize("path", ["/landing.html", "/dashboard.html", "/js/api.js", "/css/base.css"])
def test_frontend_disajikan(client, path):
    assert client.get(path).status_code == 200
