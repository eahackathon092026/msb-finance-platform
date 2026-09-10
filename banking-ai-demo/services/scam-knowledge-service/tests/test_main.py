from fastapi.testclient import TestClient

from main import app, SERVICE_NAME, SCAM_SCENARIOS

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": SERVICE_NAME}


def test_info():
    resp = client.get("/info")
    assert resp.status_code == 200
    assert resp.json()["service"] == SERVICE_NAME


def test_list_scams():
    resp = client.get("/scams")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(SCAM_SCENARIOS)
    assert body["count"] >= 10


def test_match_scam_positive():
    payload = {
        "text": "Khách hàng nhận cuộc gọi yêu cầu chuyển tiền vào tài khoản an toàn"
    }
    resp = client.post("/scams/match", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is True
    assert body["scenario"] == "fake_authority_safe_account"
    assert body["risk_level"] == "HIGH"
    assert len(body["recommended_questions"]) >= 1


def test_match_scam_negative():
    resp = client.post("/scams/match", json={"text": "hôm nay trời đẹp quá"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is False
