"""transaction-service

Demo service quản lý lịch sử transaction.
Hỗ trợ categorize, monthly aggregate, cashflow forecast.
Dữ liệu mock in-memory, không dùng DB.
"""
from collections import defaultdict

from fastapi import FastAPI, HTTPException

SERVICE_NAME = "transaction-service"

app = FastAPI(title=SERVICE_NAME, version="0.1.0")

# ---------------------------------------------------------------------------
# Mock data: transactions theo customer
# amount > 0 = tiền vào (income), amount < 0 = tiền ra (expense)
# ---------------------------------------------------------------------------
TRANSACTIONS = {
    "C001": [
        {"txn_id": "T001", "date": "2025-07-05", "amount": 20000000, "category": "salary"},
        {"txn_id": "T002", "date": "2025-07-08", "amount": -3500000, "category": "shopping"},
        {"txn_id": "T003", "date": "2025-07-15", "amount": -1200000, "category": "food"},
        {"txn_id": "T004", "date": "2025-08-05", "amount": 20000000, "category": "salary"},
        {"txn_id": "T005", "date": "2025-08-12", "amount": -5000000, "category": "transfer"},
        {"txn_id": "T006", "date": "2025-08-20", "amount": -2000000, "category": "bill"},
    ],
    "C002": [
        {"txn_id": "T101", "date": "2025-08-01", "amount": 120000000, "category": "revenue"},
        {"txn_id": "T102", "date": "2025-08-10", "amount": -40000000, "category": "supplier"},
        {"txn_id": "T103", "date": "2025-08-25", "amount": -15000000, "category": "payroll"},
    ],
}


def _txns_or_404(customer_id: str):
    txns = TRANSACTIONS.get(customer_id)
    if txns is None:
        raise HTTPException(status_code=404, detail=f"no transactions for {customer_id}")
    return txns


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
        "description": "Quản lý lịch sử transaction demo: categorize, monthly summary "
        "và cashflow forecast đơn giản.",
        "endpoints": [
            "GET /transactions/{customer_id}",
            "GET /transactions/{customer_id}/monthly-summary",
            "GET /transactions/{customer_id}/cashflow-forecast",
        ],
    }


# ---------------------------------------------------------------------------
# Demo endpoints
# ---------------------------------------------------------------------------
@app.get("/transactions/{customer_id}")
def get_transactions(customer_id: str):
    txns = _txns_or_404(customer_id)
    return {"customer_id": customer_id, "count": len(txns), "transactions": txns}


@app.get("/transactions/{customer_id}/monthly-summary")
def monthly_summary(customer_id: str):
    txns = _txns_or_404(customer_id)
    months = defaultdict(lambda: {"income": 0, "expense": 0, "count": 0})
    for t in txns:
        month = t["date"][:7]  # YYYY-MM
        bucket = months[month]
        bucket["count"] += 1
        if t["amount"] >= 0:
            bucket["income"] += t["amount"]
        else:
            bucket["expense"] += -t["amount"]
    summary = [
        {
            "month": month,
            "income": data["income"],
            "expense": data["expense"],
            "net": data["income"] - data["expense"],
            "count": data["count"],
        }
        for month, data in sorted(months.items())
    ]
    return {"customer_id": customer_id, "summary": summary}


@app.get("/transactions/{customer_id}/cashflow-forecast")
def cashflow_forecast(customer_id: str):
    """Forecast đơn giản: trung bình net theo tháng, dự báo 3 tháng kế tiếp."""
    txns = _txns_or_404(customer_id)
    net_by_month = defaultdict(int)
    for t in txns:
        net_by_month[t["date"][:7]] += t["amount"]

    months = sorted(net_by_month)
    avg_net = sum(net_by_month.values()) // len(months) if months else 0

    last_month = months[-1] if months else "2025-08"
    year, mon = (int(x) for x in last_month.split("-"))
    forecast = []
    for _ in range(3):
        mon += 1
        if mon > 12:
            mon = 1
            year += 1
        forecast.append({"month": f"{year:04d}-{mon:02d}", "projected_net": avg_net})

    return {
        "customer_id": customer_id,
        "avg_monthly_net": avg_net,
        "forecast": forecast,
    }
