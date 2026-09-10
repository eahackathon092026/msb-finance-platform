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


def test_get_transactions():
    resp = client.get("/transactions/C001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] == "C001"
    assert body["count"] == len(body["transactions"])
    assert body["count"] > 0


def test_transactions_not_found():
    resp = client.get("/transactions/UNKNOWN")
    assert resp.status_code == 404


def test_monthly_summary():
    resp = client.get("/transactions/C001/monthly-summary")
    assert resp.status_code == 200
    summary = resp.json()["summary"]
    assert len(summary) >= 1
    first = summary[0]
    assert first["net"] == first["income"] - first["expense"]


def test_cashflow_forecast():
    resp = client.get("/transactions/C001/cashflow-forecast")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["forecast"]) == 3
    assert "avg_monthly_net" in body
