from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app

pytestmark = pytest.mark.skipif(not Path(settings.frontend_dir).is_dir(), reason="folder frontend tidak ditemukan")


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_file_frontend_wajib_divalidasi_ulang(client):
    for path in ("/login.html", "/js/login.js", "/css/base.css"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-cache"


def test_file_tidak_berubah_dijawab_304_tanpa_isi(client):
    etag = client.get("/js/login.js").headers["etag"]
    r = client.get("/js/login.js", headers={"If-None-Match": etag})
    assert r.status_code == 304 and r.content == b""
    assert r.headers["cache-control"] == "no-cache"
