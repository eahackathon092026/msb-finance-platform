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


def test_risk_score_example():
    payload = {
        "customer_id": "C001",
        "amount": 50000000,
        "new_beneficiary": True,
        "unusual_time": True,
        "device_changed": False,
        "geo_anomaly": True,
        "velocity_high": False,
    }
    resp = client.post("/risk-score", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 75
    assert body["level"] == "HIGH"
    names = {f["name"] for f in body["factors"]}
    assert names == {"new_beneficiary", "unusual_time", "geo_anomaly"}


def test_risk_score_low():
    resp = client.post("/risk-score", json={"customer_id": "C001", "amount": 1000})
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 0
    assert body["level"] == "LOW"


def test_risk_score_capped_at_100():
    payload = {
        "customer_id": "C002",
        "amount": 200000000,
        "new_beneficiary": True,
        "unusual_time": True,
        "device_changed": True,
        "geo_anomaly": True,
        "velocity_high": True,
    }
    resp = client.post("/risk-score", json=payload)
    body = resp.json()
    assert body["score"] == 100
    assert body["level"] == "CRITICAL"
