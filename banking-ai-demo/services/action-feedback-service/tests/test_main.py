"""Test cho action-feedback-service."""
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)

DECISION = "11111111-2222-3333-4444-555555555555"
CASE = {
    "case_id": "CASE-2026-0001", "decision_id": DECISION, "customer_id": 100008,
    "scenario_id": "S01", "status": "OPEN", "narrative": "Tóm tắt case.",
    "callback_phone_masked": "09** *** 678", "created_at": None, "closed_at": None,
}


# ---------------------------------------------------------------------------
# Hành động
# ---------------------------------------------------------------------------
def test_hanh_dong_khong_hop_le_bi_tu_choi():
    r = client.post("/actions", json={
        "customer_id": 100008, "action": "DELETE_EVERYTHING"})
    assert r.status_code == 400


def test_hanh_dong_hop_le_duoc_chap_nhan(monkeypatch):
    monkeypatch.setattr(main, "query_one", lambda *a, **k: None)
    monkeypatch.setattr(main, "execute_returning",
                        lambda *a, **k: {"notification_id": 7, "decision_id": None})
    body = client.post("/actions", json={
        "customer_id": 100008, "action": "ALERT", "reason": "Canh bao thu"}).json()
    assert body["action"] == "ALERT"


def test_ly_do_hanh_dong_duoc_mask_sdt(monkeypatch):
    monkeypatch.setattr(main, "query_one", lambda *a, **k: None)
    monkeypatch.setattr(main, "execute_returning",
                        lambda *a, **k: {"notification_id": 7, "decision_id": None})
    body = client.post("/actions", json={
        "customer_id": 100008, "action": "ALERT",
        "reason": "Khach bao so 0912345678 goi den"}).json()
    assert "0912345678" not in body["reason"]


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------
def test_mo_case_lan_hai_tra_case_cu_thay_vi_bao_loi(monkeypatch):
    """Quan hệ với risk_decision là 1-1. Agent gọi lại sau timeout không nên
    nhận lỗi trùng khóa — nếu không, mọi luồng retry đều gãy."""
    monkeypatch.setattr(main, "query_one", lambda *a, **k: dict(CASE))
    body = client.post("/cases", json={
        "decision_id": DECISION, "customer_id": 100008}).json()
    assert body["already_existed"] is True
    assert body["case_id"] == "CASE-2026-0001"


def test_dong_case_gian_lan_tu_sinh_feedback_ops(monkeypatch):
    """Kết luận của đội vận hành là nhãn huấn luyện đáng tin nhất hệ thống có."""
    monkeypatch.setattr(main, "query_one", lambda *a, **k: dict(CASE))
    ghi = {}

    def fake_returning(sql, params=None):
        if "UPDATE guardian_case" in sql:
            return {**CASE, "status": "CLOSED_FRAUD"}
        ghi["feedback"] = params
        return {"feedback_id": 1, "decision_id": DECISION, "label": params[2],
                "source": params[3]}

    monkeypatch.setattr(main, "execute_returning", fake_returning)
    body = client.patch("/cases/CASE-2026-0001", json={"status": "CLOSED_FRAUD"}).json()
    assert body["feedback"]["label"] == "fraud"
    assert body["feedback"]["source"] == "ops"


def test_dong_case_hop_le_sinh_nhan_legit(monkeypatch):
    monkeypatch.setattr(main, "query_one", lambda *a, **k: dict(CASE))
    monkeypatch.setattr(main, "execute_returning", lambda sql, params=None: (
        {**CASE, "status": "CLOSED_LEGIT"} if "UPDATE guardian_case" in sql
        else {"feedback_id": 2, "decision_id": DECISION,
              "label": params[2], "source": params[3]}))
    body = client.patch("/cases/CASE-2026-0001", json={"status": "CLOSED_LEGIT"}).json()
    assert body["feedback"]["label"] == "legit"


def test_case_khong_ton_tai_tra_404(monkeypatch):
    monkeypatch.setattr(main, "query_one", lambda *a, **k: None)
    assert client.get("/cases/CASE-2026-9999").status_code == 404


# ---------------------------------------------------------------------------
# Nhật ký LLM
# ---------------------------------------------------------------------------
def test_ghi_trace_mask_pii_con_sot_trong_prompt(monkeypatch):
    ghi = {}

    def fake(sql, params=None):
        ghi["params"] = params
        return {"trace_id": 1, "decision_id": None, "prompt_masked": params[5]}

    monkeypatch.setattr(main, "execute_returning", fake)
    client.post("/llm-traces", json={
        "agent": "shield_explain", "model": "claude-sonnet-5",
        "prompt_key": "shield_explain@v3",
        "prompt_masked": "Khach hang so 0912345678 chuyen tien",
        "status": "ok", "latency_ms": 800})
    assert "0912345678" not in ghi["params"][5]


def test_thong_ke_tinh_ca_luot_that_bai(monkeypatch):
    """Bản ghi timeout và error phải được đếm, nếu không tỷ lệ fallback bị tô hồng."""
    monkeypatch.setattr(main, "query", lambda *a, **k: [
        {"agent": "shield_explain", "status": "ok", "n": 8, "avg_latency_ms": 900},
        {"agent": "shield_explain", "status": "timeout", "n": 2, "avg_latency_ms": 3000},
    ])
    body = client.get("/llm-traces/stats").json()
    assert body["total_calls"] == 10
    assert body["fallback_rate"] == 0.2


def test_health_va_agent_tools():
    assert client.get("/health").json()["status"] == "ok"
    names = {t["name"] for t in client.get("/agent/tools").json()["tools"]}
    assert {"record_action", "submit_feedback", "apply_feedback", "log_llm_call"} <= names


def test_info_liet_ke_hanh_dong_cho_phep():
    assert set(client.get("/info").json()["allowed_actions"]) == main.ALLOWED_ACTIONS


def test_openapi_hop_le():
    spec = client.get("/openapi.json").json()
    assert "/feedback/apply" in spec["paths"]
    assert {"case", "feedback", "audit", "notification"} <= {
        t["name"] for t in spec["tags"]}
