import os
import tempfile

from fastapi.testclient import TestClient


def test_root_html_and_static_accessible():
    # use an isolated db to avoid cross-test interference
    with tempfile.TemporaryDirectory() as td:
        os.environ["LICENSE_DB_SEED"] = "true"
        os.environ["LICENSE_DB_PATH"] = os.path.join(td, "webtest.db")

        from app.main import app

        client = TestClient(app)

        r = client.get("/")
        assert r.status_code == 200
        assert "Cloud License Server" in r.text
        assert "Matthias Holetzko" in r.text

        css = client.get("/static/style.css")
        assert css.status_code == 200
        assert "--mb-black" in css.text

        js = client.get("/static/app.js")
        assert js.status_code == 200
        assert "borrow" in js.text

        # borrows endpoint exists
        be = client.get("/borrows")
        assert be.status_code == 200


