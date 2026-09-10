"""action-feedback-service

Ghi nhận action và feedback cho case demo.
Lưu in-memory (reset khi restart), không dùng DB.
"""
from datetime import datetime, timezone

from pydantic import BaseModel

from fastapi import FastAPI, HTTPException

SERVICE_NAME = "action-feedback-service"

app = FastAPI(title=SERVICE_NAME, version="0.1.0")

ALLOWED_ACTIONS = {"CANCEL", "HOLD", "CONTACT", "CASE_OPEN", "ALERT"}

# In-memory store
ACTIONS: list[dict] = []
FEEDBACKS: list[dict] = []


class ActionRequest(BaseModel):
    customer_id: str
    transaction_id: str
    action: str
    reason: str = ""


class FeedbackRequest(BaseModel):
    case_id: str
    result: str
    note: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        "description": "Ghi nhận action (CANCEL/HOLD/CONTACT/CASE_OPEN/ALERT) và feedback, "
        "lưu in-memory cho demo.",
        "endpoints": [
            "POST /actions",
            "GET /actions/{customer_id}",
            "POST /feedback",
        ],
        "allowed_actions": sorted(ALLOWED_ACTIONS),
    }


# ---------------------------------------------------------------------------
# Demo endpoints
# ---------------------------------------------------------------------------
@app.post("/actions")
def create_action(req: ActionRequest):
    if req.action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"action must be one of {sorted(ALLOWED_ACTIONS)}",
        )
    record = {
        "id": len(ACTIONS) + 1,
        "customer_id": req.customer_id,
        "transaction_id": req.transaction_id,
        "action": req.action,
        "reason": req.reason,
        "created_at": _now(),
    }
    ACTIONS.append(record)
    return record


@app.get("/actions/{customer_id}")
def get_actions(customer_id: str):
    items = [a for a in ACTIONS if a["customer_id"] == customer_id]
    return {"customer_id": customer_id, "count": len(items), "actions": items}


@app.post("/feedback")
def create_feedback(req: FeedbackRequest):
    record = {
        "id": len(FEEDBACKS) + 1,
        "case_id": req.case_id,
        "result": req.result,
        "note": req.note,
        "created_at": _now(),
    }
    FEEDBACKS.append(record)
    return record
