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


def test_create_and_get_action():
    payload = {
        "customer_id": "C001",
        "transaction_id": "T001",
        "action": "HOLD",
        "reason": "High scam risk",
    }
    resp = client.post("/actions", json=payload)
    assert resp.status_code == 200
    assert resp.json()["action"] == "HOLD"

    resp = client.get("/actions/C001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert any(a["transaction_id"] == "T001" for a in body["actions"])


def test_invalid_action_rejected():
    payload = {
        "customer_id": "C001",
        "transaction_id": "T999",
        "action": "NOT_A_REAL_ACTION",
    }
    resp = client.post("/actions", json=payload)
    assert resp.status_code == 400


def test_create_feedback():
    payload = {
        "case_id": "CASE001",
        "result": "CONFIRMED_SCAM",
        "note": "Customer confirmed scam attempt",
    }
    resp = client.post("/feedback", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == "CASE001"
    assert body["result"] == "CONFIRMED_SCAM"
