"""customer-profile-service

Demo service quản lý customer profile.
Mô phỏng behavior baseline, persona, beneficiaries, digital twin features.
Dữ liệu mock in-memory, không dùng DB.
"""
from fastapi import FastAPI, HTTPException

SERVICE_NAME = "customer-profile-service"

app = FastAPI(title=SERVICE_NAME, version="0.1.0")

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
CUSTOMERS = {
    "C001": {
        "customer_id": "C001",
        "persona": "salary_customer",
        "behavior_baseline": {
            "avg_monthly_spend": 15000000,
            "avg_transaction_count": 45,
        },
        "beneficiaries": ["B001", "B002"],
        "digital_twin_features": {
            "risk_tolerance": "medium",
            "usual_login_hours": ["08:00-10:00", "19:00-22:00"],
        },
    },
    "C002": {
        "customer_id": "C002",
        "persona": "business_owner",
        "behavior_baseline": {
            "avg_monthly_spend": 85000000,
            "avg_transaction_count": 180,
        },
        "beneficiaries": ["B010", "B011", "B012"],
        "digital_twin_features": {
            "risk_tolerance": "high",
            "usual_login_hours": ["07:00-09:00", "12:00-14:00", "20:00-23:00"],
        },
    },
}


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
        "description": "Quản lý customer profile demo: persona, behavior baseline, "
        "beneficiaries và digital twin features.",
        "endpoints": [
            "GET /customers/{customer_id}",
            "GET /customers/{customer_id}/baseline",
        ],
    }


# ---------------------------------------------------------------------------
# Demo endpoints
# ---------------------------------------------------------------------------
@app.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"customer {customer_id} not found")
    return customer


@app.get("/customers/{customer_id}/baseline")
def get_baseline(customer_id: str):
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"customer {customer_id} not found")
    return {
        "customer_id": customer_id,
        "persona": customer["persona"],
        "behavior_baseline": customer["behavior_baseline"],
    }
