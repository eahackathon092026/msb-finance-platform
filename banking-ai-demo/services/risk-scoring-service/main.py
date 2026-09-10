"""risk-scoring-service

Tính risk score deterministic từ 0-100 dựa trên các risk factor.
Không dùng ML, chỉ cộng điểm theo rule cố định (dễ test, dễ reproduce).
"""
from pydantic import BaseModel

from fastapi import FastAPI

SERVICE_NAME = "risk-scoring-service"

app = FastAPI(title=SERVICE_NAME, version="0.1.0")

# ---------------------------------------------------------------------------
# Rule demo: điểm cộng cho từng factor khi factor = True.
# large_amount kích hoạt khi amount >= LARGE_AMOUNT_THRESHOLD.
# ---------------------------------------------------------------------------
FACTOR_WEIGHTS = {
    "new_beneficiary": 20,
    "unusual_time": 15,
    "device_changed": 10,
    "geo_anomaly": 40,
    "velocity_high": 15,
    "large_amount": 20,
}
LARGE_AMOUNT_THRESHOLD = 100_000_000


class RiskRequest(BaseModel):
    customer_id: str
    amount: float = 0
    new_beneficiary: bool = False
    unusual_time: bool = False
    device_changed: bool = False
    geo_anomaly: bool = False
    velocity_high: bool = False


def _level(score: int) -> str:
    if score <= 29:
        return "LOW"
    if score <= 59:
        return "MEDIUM"
    if score <= 79:
        return "HIGH"
    return "CRITICAL"


# ---------------------------------------------------------------------------
# Common endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/info")
def info():
    return {
        "service": SERVICE_NAME,
        "description": "Tính risk score deterministic 0-100 từ ~6 risk factors. "
        "Rule: 0-29 LOW, 30-59 MEDIUM, 60-79 HIGH, 80-100 CRITICAL.",
        "endpoints": ["POST /risk-score"],
        "factor_weights": FACTOR_WEIGHTS,
    }


# ---------------------------------------------------------------------------
# Demo endpoint
# ---------------------------------------------------------------------------
@app.post("/risk-score")
def risk_score(req: RiskRequest):
    active = {
        "new_beneficiary": req.new_beneficiary,
        "unusual_time": req.unusual_time,
        "device_changed": req.device_changed,
        "geo_anomaly": req.geo_anomaly,
        "velocity_high": req.velocity_high,
        "large_amount": req.amount >= LARGE_AMOUNT_THRESHOLD,
    }

    factors = [
        {"name": name, "score": FACTOR_WEIGHTS[name]}
        for name, triggered in active.items()
        if triggered
    ]
    score = min(100, sum(f["score"] for f in factors))

    return {
        "customer_id": req.customer_id,
        "score": score,
        "level": _level(score),
        "factors": factors,
    }
