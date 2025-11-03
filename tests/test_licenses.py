import os
import tempfile
from contextlib import contextmanager

from fastapi.testclient import TestClient

os.environ["LICENSE_DB_SEED"] = "false"


@contextmanager
def temp_db():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.db")
        os.environ["LICENSE_DB_PATH"] = db_path
        yield db_path


def make_app_with_seed():
    from app.main import app
    from app.db import initialize_database

    initialize_database([{"tool": "cad_tool", "total": 2, "commit_qty": 1, "max_overage": 1}])
    return app


def test_borrow_and_return():
    with temp_db():
        app = make_app_with_seed()
        client = TestClient(app)

        # initial status
        r = client.get("/licenses/cad_tool/status")
        assert r.status_code == 200
        assert r.json()["available"] == 2

        # borrow first
        r = client.post("/licenses/borrow", json={"tool": "cad_tool", "user": "alice"})
        assert r.status_code == 200
        borrow_id = r.json()["id"]

        r = client.get("/licenses/cad_tool/status")
        assert r.json()["available"] == 1

        # borrow second
        r2 = client.post("/licenses/borrow", json={"tool": "cad_tool", "user": "bob"})
        assert r2.status_code == 200

        # third should fail
        r3 = client.post("/licenses/borrow", json={"tool": "cad_tool", "user": "carol"})
        assert r3.status_code == 409

        # return one
        rr = client.post("/licenses/return", json={"id": borrow_id})
        assert rr.status_code == 200

        # now one available again
        r = client.get("/licenses/cad_tool/status")
        assert r.json()["available"] == 1


def test_metrics_endpoint_present():
    with temp_db():
        app = make_app_with_seed()
        client = TestClient(app)
        # hit an endpoint to generate metrics
        client.get("/licenses/cad_tool/status")
        m = client.get("/metrics")
        assert m.status_code == 200
        assert b"license_borrow_attempts_total" in m.content


