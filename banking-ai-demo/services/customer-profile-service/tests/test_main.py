from fastapi.testclient import TestClient

from main import app, SERVICE_NAME

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": SERVICE_NAME}


def test_info():
    resp = client.get("/info")
    assert resp.status_code == 200
    assert resp.json()["service"] == SERVICE_NAME


def test_get_customer():
    resp = client.get("/customers/C001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] == "C001"
    assert body["persona"] == "salary_customer"
    assert "behavior_baseline" in body


def test_get_customer_not_found():
    resp = client.get("/customers/UNKNOWN")
    assert resp.status_code == 404


def test_get_baseline():
    resp = client.get("/customers/C001/baseline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] == "C001"
    assert body["behavior_baseline"]["avg_transaction_count"] == 45
