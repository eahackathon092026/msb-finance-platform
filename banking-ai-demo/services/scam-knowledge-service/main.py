"""scam-knowledge-service

Lookup các pattern / kịch bản scam phổ biến tại Việt Nam.
Hardcode ~10 scenario, match theo keyword (không dùng LLM).
"""
from pydantic import BaseModel

from fastapi import FastAPI

SERVICE_NAME = "scam-knowledge-service"

app = FastAPI(title=SERVICE_NAME, version="0.1.0")

# ---------------------------------------------------------------------------
# 10 kịch bản scam phổ biến. keywords ở dạng lowercase để match không phân biệt hoa thường.
# ---------------------------------------------------------------------------
SCAM_SCENARIOS = [
    {
        "scenario": "fake_authority_safe_account",
        "title": "Giả danh công an/viện kiểm sát yêu cầu chuyển tiền vào 'tài khoản an toàn'",
        "risk_level": "HIGH",
        "keywords": ["công an", "viện kiểm sát", "tài khoản an toàn", "chuyển tiền", "điều tra"],
        "recommended_questions": [
            "Ai là người yêu cầu chuyển tiền?",
            "Có yêu cầu giữ bí mật hay không?",
        ],
    },
    {
        "scenario": "fake_bank_otp",
        "title": "Giả danh ngân hàng yêu cầu cung cấp OTP / mật khẩu",
        "risk_level": "CRITICAL",
        "keywords": ["otp", "mã xác thực", "mật khẩu", "nhân viên ngân hàng", "khóa tài khoản"],
        "recommended_questions": [
            "Họ có yêu cầu bạn đọc mã OTP không?",
            "Bạn có bấm vào đường link lạ nào không?",
        ],
    },
    {
        "scenario": "lucky_prize",
        "title": "Trúng thưởng / quà tặng yêu cầu đóng phí nhận thưởng",
        "risk_level": "MEDIUM",
        "keywords": ["trúng thưởng", "quà tặng", "phí nhận thưởng", "may mắn"],
        "recommended_questions": [
            "Bạn có tham gia chương trình này trước đó không?",
            "Họ yêu cầu đóng phí trước khi nhận thưởng?",
        ],
    },
    {
        "scenario": "online_job_task",
        "title": "Việc làm online, làm nhiệm vụ nạp tiền để nhận hoa hồng",
        "risk_level": "HIGH",
        "keywords": ["việc làm online", "nhiệm vụ", "hoa hồng", "nạp tiền", "đơn hàng"],
        "recommended_questions": [
            "Bạn phải nạp tiền để làm nhiệm vụ?",
            "Hoa hồng cam kết có bất thường cao không?",
        ],
    },
    {
        "scenario": "romance_scam",
        "title": "Lừa đảo tình cảm, gửi quà từ nước ngoài yêu cầu đóng phí hải quan",
        "risk_level": "HIGH",
        "keywords": ["người yêu", "gửi quà", "nước ngoài", "phí hải quan", "kết bạn"],
        "recommended_questions": [
            "Bạn đã gặp mặt trực tiếp người này chưa?",
            "Họ có yêu cầu đóng phí để nhận quà không?",
        ],
    },
    {
        "scenario": "fake_investment",
        "title": "Kêu gọi đầu tư sàn/tiền ảo cam kết lợi nhuận cao",
        "risk_level": "HIGH",
        "keywords": ["đầu tư", "sàn", "tiền ảo", "lợi nhuận cao", "cam kết lãi"],
        "recommended_questions": [
            "Sàn đầu tư này có được cấp phép không?",
            "Lợi nhuận cam kết có phi thực tế không?",
        ],
    },
    {
        "scenario": "fake_relative_accident",
        "title": "Giả danh người thân gặp tai nạn cần chuyển tiền gấp",
        "risk_level": "HIGH",
        "keywords": ["người thân", "tai nạn", "cấp cứu", "chuyển tiền gấp", "bệnh viện"],
        "recommended_questions": [
            "Bạn đã gọi lại trực tiếp cho người thân chưa?",
            "Yêu cầu chuyển tiền có gấp gáp bất thường không?",
        ],
    },
    {
        "scenario": "fake_delivery",
        "title": "Giả danh shipper/giao hàng yêu cầu thanh toán đơn lạ",
        "risk_level": "MEDIUM",
        "keywords": ["shipper", "giao hàng", "đơn hàng", "thanh toán", "chuyển khoản ship"],
        "recommended_questions": [
            "Bạn có đặt đơn hàng này không?",
            "Họ yêu cầu chuyển khoản trước khi giao?",
        ],
    },
    {
        "scenario": "phishing_link",
        "title": "Gửi link giả mạo yêu cầu đăng nhập/nhập thông tin",
        "risk_level": "CRITICAL",
        "keywords": ["đường link", "đăng nhập", "website", "cập nhật thông tin", "bấm vào link"],
        "recommended_questions": [
            "Đường link có đúng tên miền chính thức không?",
            "Bạn có nhập thông tin đăng nhập vào link đó không?",
        ],
    },
    {
        "scenario": "debt_collection_threat",
        "title": "Đe dọa đòi nợ / bôi nhọ yêu cầu chuyển tiền",
        "risk_level": "MEDIUM",
        "keywords": ["đòi nợ", "đe dọa", "bôi nhọ", "khủng bố tinh thần"],
        "recommended_questions": [
            "Khoản nợ này có thật không?",
            "Họ có dùng lời lẽ đe dọa không?",
        ],
    },
]


class MatchRequest(BaseModel):
    text: str


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
        "description": "Lookup kịch bản scam phổ biến tại VN và match theo keyword.",
        "endpoints": ["GET /scams", "POST /scams/match"],
        "scenario_count": len(SCAM_SCENARIOS),
    }


# ---------------------------------------------------------------------------
# Demo endpoints
# ---------------------------------------------------------------------------
@app.get("/scams")
def list_scams():
    return {
        "count": len(SCAM_SCENARIOS),
        "scams": [
            {
                "scenario": s["scenario"],
                "title": s["title"],
                "risk_level": s["risk_level"],
                "keywords": s["keywords"],
            }
            for s in SCAM_SCENARIOS
        ],
    }


@app.post("/scams/match")
def match_scam(req: MatchRequest):
    text = req.text.lower()
    best = None
    best_hits = 0
    for scenario in SCAM_SCENARIOS:
        hits = sum(1 for kw in scenario["keywords"] if kw in text)
        if hits > best_hits:
            best_hits = hits
            best = scenario

    if best is None:
        return {"matched": False, "scenario": None, "risk_level": None, "recommended_questions": []}

    return {
        "matched": True,
        "scenario": best["scenario"],
        "risk_level": best["risk_level"],
        "matched_keyword_count": best_hits,
        "recommended_questions": best["recommended_questions"],
    }
