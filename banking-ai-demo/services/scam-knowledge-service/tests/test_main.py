"""Test cho scam-knowledge-service — trọng tâm là khớp kịch bản."""
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


def scenario(sid, name, action, priority, signal, ask="Y"):
    return {
        "scenario_id": sid, "scenario_name": name, "group_code": "G1",
        "pattern": "SINGLE", "agent_can_ask": ask, "signal_pattern": signal,
        "questions": {"SALARY": [f"Câu hỏi cho người đi làm ({sid})"],
                      "HNW": [f"Câu hỏi cho khách ưu tiên ({sid})"],
                      "SENIOR": [f"Câu hỏi cho người cao tuổi ({sid})"]},
        "options": ["Có", "Không"], "advice_title": f"Khuyến cáo {sid}",
        "advice_body": "Nội dung khuyến cáo.", "recommended_action": action,
        "priority": priority, "status": "ACTIVE",
    }


CONG_AN = scenario("S01", "Giả danh công an", "cancel", 1, {
    "keywords": ["cong an", "tai khoan an toan", "dieu tra"],
    "new_beneficiary": True, "min_drain_ratio": 0.7,
})
DEEPFAKE = scenario("S03", "Deepfake người thân", "hold", 2, {
    "keywords": ["gap", "con trai", "tai nan"],
    "new_beneficiary": True, "min_amount": 20_000_000,
    "session_flags": ["on_call"],
})
TAKEOVER = scenario("S09", "Chiếm quyền thiết bị", "hold", 0, {
    "session_flags": ["screen_sharing", "remote_app"],
}, ask="N")


# ---------------------------------------------------------------------------
# Khớp từ khóa
# ---------------------------------------------------------------------------
def test_bo_dau_de_khop_ca_hai_cach_go():
    assert main._strip_accents("Công An") == "cong an"


def test_khop_theo_ranh_gioi_tu_khong_theo_chuoi_con():
    """'gap' từng khớp ngay trong 'NANG CAP BAO MAT', kéo một vụ moi OTP sang nhầm
    kịch bản deepfake — sai kịch bản thì câu hỏi đưa cho khách cũng sai chủ đề."""
    assert main._contains_phrase("nang cap bao mat tai khoan", "gap") is False
    assert main._contains_phrase("chuyen gap cho con", "gap") is True
    assert main._contains_phrase("cong an yeu cau", "cong an") is True


def test_khop_cum_tu_nhieu_tieng():
    assert main._contains_phrase("chuyen vao tai khoan an toan", "tai khoan an toan")


# ---------------------------------------------------------------------------
# Chấm độ khớp
# ---------------------------------------------------------------------------
def req(**kw):
    return main.MatchRequest(**kw)


def test_tu_khoa_trong_noi_dung_lam_tang_diem_khop():
    co, hits = main._match_score(CONG_AN["signal_pattern"],
                                 req(memo="chuyen vao tai khoan an toan theo yeu cau cong an"))
    khong, _ = main._match_score(CONG_AN["signal_pattern"], req(memo="tra tien dien"))
    assert co > khong
    assert any("từ khóa" in h for h in hits)


def test_co_phien_nang_hon_tu_khoa_don_le():
    """Cờ chiếm quyền thiết bị là bằng chứng kỹ thuật, đáng tin hơn nội dung khách gõ."""
    diem, _ = main._match_score(TAKEOVER["signal_pattern"],
                                req(session_flags={"screen_sharing": True, "remote_app": True}))
    assert diem >= 12


def test_khong_dau_hieu_nao_thi_khong_khop(monkeypatch):
    monkeypatch.setattr(main, "query", lambda *a, **k: [CONG_AN, DEEPFAKE])
    body = client.post("/scams/match", json={"memo": "tra tien dien hang thang"}).json()
    assert body["matched"] is False and body["scenario"] is None


def test_khop_dung_kich_ban_theo_tu_khoa(monkeypatch):
    monkeypatch.setattr(main, "query", lambda *a, **k: [CONG_AN, DEEPFAKE])
    body = client.post("/scams/match", json={
        "memo": "chuyen tien theo yeu cau co quan dieu tra cong an",
        "persona": "SENIOR", "is_new_beneficiary": True, "drain_ratio": 0.9,
    }).json()
    assert body["scenario"]["scenario_id"] == "S01"
    assert body["scenario"]["recommended_action"] == "cancel"


def test_cau_hoi_duoc_chon_theo_phan_khuc(monkeypatch):
    monkeypatch.setattr(main, "query", lambda *a, **k: [CONG_AN])
    for persona in ("SALARY", "HNW", "SENIOR"):
        body = client.post("/scams/match", json={
            "memo": "cong an dieu tra", "persona": persona,
            "is_new_beneficiary": True, "drain_ratio": 0.8,
        }).json()
        assert persona.lower() in body["scenario"]["question"].lower() or \
               body["scenario"]["question"].endswith(f"({CONG_AN['scenario_id']})")


def test_do_tin_cay_nam_trong_khoang_0_1(monkeypatch):
    monkeypatch.setattr(main, "query", lambda *a, **k: [CONG_AN, DEEPFAKE])
    body = client.post("/scams/match", json={
        "memo": "cong an dieu tra tai khoan an toan",
        "is_new_beneficiary": True, "drain_ratio": 0.95,
    }).json()
    assert 0.0 <= body["scenario"]["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Kịch bản chiếm quyền thiết bị: không được hỏi khách
# ---------------------------------------------------------------------------
def test_kich_ban_chiem_thiet_bi_khong_hoi_khach(monkeypatch):
    """Khi kẻ gian đang điều khiển máy thì chính nó sẽ là người trả lời câu hỏi."""
    monkeypatch.setattr(main, "query_one", lambda *a, **k: TAKEOVER)
    body = client.get("/scams/S09/questions?persona=HNW").json()
    assert body["agent_can_ask"] == "N"
    assert "khóa giao dịch ngay" in body["note"]


def test_kich_ban_thuong_thi_duoc_hoi(monkeypatch):
    monkeypatch.setattr(main, "query_one", lambda *a, **k: CONG_AN)
    body = client.get("/scams/S01/questions?persona=SENIOR").json()
    assert body["agent_can_ask"] == "Y"
    assert body["questions"]


def test_kich_ban_khong_ton_tai_tra_404(monkeypatch):
    monkeypatch.setattr(main, "query_one", lambda *a, **k: None)
    assert client.get("/scams/S99").status_code == 404


# ---------------------------------------------------------------------------
# Bộ kiểm thử fraud case
# ---------------------------------------------------------------------------
def test_tu_ket_luan_dat_truot_theo_khoang_ky_vong(monkeypatch):
    case = {"fraud_case_id": "F01", "expected_score_min": 78,
            "expected_score_max": 100, "expected_level": "intervene"}
    monkeypatch.setattr(main, "query_one", lambda *a, **k: case)
    monkeypatch.setattr(main, "execute_returning",
                        lambda *a, **k: {**case, "last_test_at": "2026-09-15T10:00:00Z"})
    assert client.post("/fraud-cases/F01/test-result", json={"score": 93}).json()["passed"] == "Y"
    assert client.post("/fraud-cases/F01/test-result", json={"score": 50}).json()["passed"] == "N"


def test_health_va_agent_tools():
    assert client.get("/health").json()["status"] == "ok"
    names = {t["name"] for t in client.get("/agent/tools").json()["tools"]}
    assert {"match_scam", "get_questions", "list_scams"} <= names


def test_openapi_hop_le():
    spec = client.get("/openapi.json").json()
    assert "/scams/match" in spec["paths"]
    assert {"playbook", "internal"} <= {t["name"] for t in spec["tags"]}
