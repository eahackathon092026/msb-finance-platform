"""Test cho transaction-service."""
import main
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)


def tx(amount, direction="OUT", date="20260815", time="143000", **kw):
    row = {
        "transaction_id": kw.get("tid", 1), "customer_id": 100001, "account_id": 5001,
        "direction": direction, "amount": str(amount), "balance_after": "50000000",
        "currency": "VND", "beneficiary_id": kw.get("ben", 300001),
        "beneficiary_bank_code": "VCB", "beneficiary_account_masked": "0301 ****",
        "transaction_type": "FT", "category": kw.get("cat", "FOOD"),
        "transaction_description": kw.get("desc", "THANH TOAN"), "channel": "MOBILE",
        "transaction_date": date, "transaction_time": time, "status": "POSTED",
        "risk_decision_id": None, "is_fraud": "Y", "fraud_case_id": "F01",
    }
    return row


# ---------------------------------------------------------------------------
# Cột kiểm thử nội bộ không được rò ra API
# ---------------------------------------------------------------------------
def test_payload_loai_bo_co_gian_lan():
    """is_fraud và fraud_case_id là đáp án của bộ kiểm thử. Lọt ra API thì vừa lộ
    nhãn cho bên ngoài, vừa có nguy cơ chui vào prompt LLM."""
    out = main._tx_payload(tx(1_000_000))
    assert "is_fraud" not in out and "fraud_case_id" not in out


def test_payload_mask_sdt_trong_noi_dung_ck():
    out = main._tx_payload(tx(1_000_000, desc="CHUYEN TIEN LH 0912345678"))
    assert "0912345678" not in out["description"]


def test_payload_cast_tien_tu_varchar_sang_so():
    """Cột tiền để varchar theo core T24; API phải trả số để agent tính được."""
    out = main._tx_payload(tx(1_500_000))
    assert out["amount"] == 1_500_000.0
    assert isinstance(out["amount"], float)


def test_signed_amount_theo_chieu_tien():
    assert main._tx_payload(tx(500_000, "OUT"))["signed_amount"] == -500_000
    assert main._tx_payload(tx(500_000, "IN"))["signed_amount"] == 500_000


# ---------------------------------------------------------------------------
# Thống kê
# ---------------------------------------------------------------------------
def test_percentile_noi_suy_tuyen_tinh():
    vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert main._percentile(vals, 0.0) == 1
    assert main._percentile(vals, 1.0) == 10
    assert main._percentile(vals, 0.5) == pytest.approx(5.5)


def test_percentile_chiu_duoc_danh_sach_rong_va_mot_phan_tu():
    assert main._percentile([], 0.9) == 0.0
    assert main._percentile([42], 0.9) == 42


def test_monthly_summary_tach_thu_chi_va_xep_hang_nhom(monkeypatch):
    rows = (
        [tx(20_000_000, "IN", "20260805", cat="OTHER")]
        + [tx(3_000_000, "OUT", "20260810", cat="SHOPPING")] * 2
        + [tx(500_000, "OUT", "20260812", cat="FOOD")] * 4
    )
    monkeypatch.setattr(main, "query", lambda *a, **k: rows)
    monkeypatch.setattr(main, "query_one", lambda *a, **k: {"x": 1})
    body = client.get("/transactions/100001/monthly-summary").json()
    thang = body["summary"][0]
    assert thang["income"] == 20_000_000
    assert thang["expense"] == 8_000_000
    assert thang["net"] == 12_000_000
    assert thang["top_categories"][0] == {
        "category": "SHOPPING", "amount": 6_000_000, "rank": 1}


def test_du_bao_loai_thang_cut(monkeypatch):
    """Tháng đầu cửa sổ bị cắt giữa chừng và tháng hiện tại chưa hết; tính cả hai
    vào trung bình có thể biến một khách đang dư tiền thành dự báo âm."""
    ky = main.now_vn().strftime("%Y%m")
    monkeypatch.setattr(main, "query_one", lambda *a, **k: {"x": 1})
    monkeypatch.setattr(main, "monthly_summary", lambda cid, months=6: {"summary": [
        {"period": "202604", "month": "2026-04", "income": 5, "expense": 90, "net": -85,
         "count": 1, "top_categories": []},
        {"period": "202605", "month": "2026-05", "income": 30, "expense": 20, "net": 10,
         "count": 1, "top_categories": []},
        {"period": "202606", "month": "2026-06", "income": 30, "expense": 18, "net": 12,
         "count": 1, "top_categories": []},
        {"period": "202607", "month": "2026-07", "income": 30, "expense": 22, "net": 8,
         "count": 1, "top_categories": []},
        {"period": ky, "month": "hien-tai", "income": 2, "expense": 70, "net": -68,
         "count": 1, "top_categories": []},
    ]})
    body = client.get("/transactions/100001/cashflow-forecast").json()
    assert body["avg_monthly_net"] > 0, "tháng cụt vẫn đang kéo dự báo xuống âm"
    assert "2026-04" in body["months_excluded_incomplete"]
    assert "hien-tai" in body["months_excluded_incomplete"]
    assert body["months_used"] == ["2026-05", "2026-06", "2026-07"]


def test_baseline_metrics_bao_loi_khi_khong_du_du_lieu(monkeypatch):
    monkeypatch.setattr(main, "query", lambda *a, **k: [])
    assert client.get("/transactions/100001/baseline-metrics").status_code == 404


def test_baseline_metrics_tra_du_18_chi_so(monkeypatch):
    rows = [tx(1_000_000 * i, date=f"202608{10+i:02d}", time=f"{8+i:02d}3000",
               tid=i, ben=300000 + (i % 3)) for i in range(1, 12)]
    monkeypatch.setattr(main, "query", lambda sql, p=None: rows if "OUT" in sql else [])
    body = client.get("/transactions/100001/baseline-metrics").json()
    m = body["metrics"]
    for col in ("out_median", "out_p90", "out_p99", "out_max", "monthly_out_avg",
                "monthly_in_avg", "known_beneficiaries", "new_benef_per_30d",
                "share_to_new_benef", "active_hours", "night_tx_ratio",
                "weekend_tx_ratio", "tx_per_week", "max_tx_per_day",
                "max_cum_to_one_benef_14d", "balance_median", "max_drain_ratio_90d"):
        assert col in m, f"thiếu chỉ số {col}"
    assert len(m["active_hours"]) == 24
    assert m["out_max"] >= m["out_p99"] >= m["out_p90"] >= m["out_median"]


def test_health_va_agent_tools():
    assert client.get("/health").json()["status"] == "ok"
    names = {t["name"] for t in client.get("/agent/tools").json()["tools"]}
    assert {"get_monthly_summary", "get_baseline_metrics", "generate_recommendations"} <= names


def test_openapi_hop_le():
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "transaction-service"
    assert {"transaction", "insight", "product", "baseline"} <= {
        t["name"] for t in spec["tags"]}
