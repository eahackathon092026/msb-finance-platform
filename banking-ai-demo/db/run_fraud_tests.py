#!/usr/bin/env python3
"""Chạy engine rủi ro trên toàn bộ 10 fraud case và ghi lại kết quả.

    python3 db/run_fraud_tests.py

Với mỗi case, script phát lại đúng giao dịch cuối cùng của case đó qua
`POST /transfer/precheck`, so điểm engine trả về với khoảng kỳ vọng ghi trong bảng
`fraud_case`, rồi gửi kết quả về `POST /fraud-cases/{id}/test-result`.

Hai điểm quan trọng khi phát lại:

  · Mốc thời gian phải là thời điểm giao dịch thật, không phải lúc chạy script.
    Yếu tố "ngữ cảnh gần đây" chỉ xét 60 phút trước giao dịch, nên chấm bằng giờ
    hiện tại sẽ bỏ sót sự kiện và cho điểm thấp giả.

  · Mỗi lần chạy tạo ra các dòng risk_decision mới. Đó là dụng ý: nhật ký chấm
    điểm cũng là bằng chứng kiểm toán, không ghi đè lên bản cũ.

Chạy trước mỗi lần demo. Case F02 là đối chứng hợp lệ — nó PHẢI cho ra `pass`;
nếu F02 bị chặn thì hệ thống đang cảnh báo sai, và đó là lỗi nặng hơn cả việc
bỏ lọt một vụ lừa đảo.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
import psycopg
from psycopg.rows import dict_row

VN = timezone(timedelta(hours=7))
DSN = os.getenv("DATABASE_URL") or (
    f"host={os.getenv('PGHOST', 'localhost')} port={os.getenv('PGPORT', '5432')} "
    f"user={os.getenv('PGUSER', 'postgres')} password={os.getenv('PGPASSWORD', '')} "
    f"dbname={os.getenv('PGDATABASE', 'guardian')}"
)
RISK_URL = os.getenv("RISK_SCORING_SERVICE_URL", "http://localhost:8083")
SCAM_URL = os.getenv("SCAM_KNOWLEDGE_SERVICE_URL", "http://localhost:8084")

GREEN, RED, YELLOW, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def fetch_cases() -> list[dict]:
    """Lấy từng case kèm giao dịch CUỐI của case — engine chỉ được đánh giá trên
    giao dịch cuối, vì các giao dịch trước đó là phần xây dựng ngữ cảnh."""
    with psycopg.connect(DSN, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT f.fraud_case_id, f.customer_id, f.scenario_id, f.description,
                   f.expected_level, f.expected_score_min, f.expected_score_max,
                   f.injection, f.demo_scene,
                   t.transaction_id, t.account_id, t.amount, t.transaction_date,
                   t.transaction_time, t.transaction_description,
                   b.beneficiary_bank_code, b.beneficiary_account_no
            FROM fraud_case f
            JOIN LATERAL (
              SELECT * FROM transaction_history th
              WHERE th.fraud_case_id = f.fraud_case_id AND th.direction = 'OUT'
              ORDER BY th.transaction_date DESC, th.transaction_time DESC LIMIT 1
            ) t ON TRUE
            LEFT JOIN beneficiary b ON b.beneficiary_id = t.beneficiary_id
            ORDER BY f.fraud_case_id
            """
        )
        return cur.fetchall()


def run() -> int:
    cases = fetch_cases()
    if not cases:
        print("Không tìm thấy fraud case nào — đã nạp db/seed.sql chưa?", file=sys.stderr)
        return 2

    print(f"\nChấm {len(cases)} fraud case qua {RISK_URL}\n")
    print(f"{'Case':<5} {'KB':<4} {'Điểm':>5} {'Kỳ vọng':>9}  {'Mức':<10} {'Mong đợi':<10} KQ")
    print("-" * 78)

    passed = failed = errored = 0
    details = []

    for c in cases:
        # Phát lại đúng thời điểm giao dịch để cửa sổ ngữ cảnh 60 phút có hiệu lực
        tx_at = datetime.strptime(
            c["transaction_date"] + c["transaction_time"], "%Y%m%d%H%M%S"
        ).replace(tzinfo=VN)
        payload = {
            "customer_id": c["customer_id"],
            "account_id": c["account_id"],
            "amount": float(c["amount"]),
            "beneficiary_bank_code": c["beneficiary_bank_code"] or "MSB",
            "beneficiary_account_no": c["beneficiary_account_no"] or "0000000000",
            "memo": c["transaction_description"] or "",
            "tx_time": tx_at.isoformat(),
            "session_flags": (c["injection"] or {}).get("session_flags") or {},
        }
        try:
            resp = httpx.post(f"{RISK_URL}/transfer/precheck", json=payload, timeout=30.0)
            resp.raise_for_status()
            result = resp.json()
        except httpx.HTTPError as exc:
            errored += 1
            print(f"{c['fraud_case_id']:<5} {c['scenario_id']:<4} {'LỖI':>5} "
                  f"{'':>9}  {'':<10} {'':<10} {RED}{type(exc).__name__}{OFF}")
            continue

        score, level = result["score"], result["level"]
        in_range = c["expected_score_min"] <= score <= c["expected_score_max"]
        level_ok = level == c["expected_level"]
        ok = in_range and level_ok
        passed += ok
        failed += not ok

        mark = f"{GREEN}ĐẠT{OFF}" if ok else f"{RED}TRƯỢT{OFF}"
        if not level_ok:
            mark += f" {DIM}(mức lệch){OFF}"
        elif not in_range:
            mark += f" {DIM}(ngoài khoảng){OFF}"
        print(f"{c['fraud_case_id']:<5} {c['scenario_id']:<4} {score:>5} "
              f"{str(c['expected_score_min']) + '-' + str(c['expected_score_max']):>9}  "
              f"{level:<10} {c['expected_level']:<10} {mark}")

        details.append({
            "case": c["fraud_case_id"], "score": score, "level": level,
            "expected": [c["expected_score_min"], c["expected_score_max"]],
            "expected_level": c["expected_level"], "passed": ok,
            "matched_scenario": (result.get("scenario") or {}).get("scenario_id"),
            "expected_scenario": c["scenario_id"],
            "top_factors": result.get("top_factors"),
            "degraded": result.get("degraded"),
            "description": c["description"],
        })

        try:
            httpx.post(
                f"{SCAM_URL}/fraud-cases/{c['fraud_case_id']}/test-result",
                json={"score": score, "passed": "Y" if ok else "N"}, timeout=15.0,
            ).raise_for_status()
        except httpx.HTTPError as exc:
            print(f"      {YELLOW}không ghi được kết quả về DB: {exc}{OFF}")

    print("-" * 78)
    print(f"ĐẠT {passed}/{len(cases)}   TRƯỢT {failed}   LỖI {errored}\n")

    # Case đối chứng được soi riêng: chặn nhầm một giao dịch hợp lệ là lỗi tệ nhất
    control = next((d for d in details if d["case"] == "F02"), None)
    if control:
        state = f"{GREEN}ĐÚNG{OFF}" if control["level"] == "pass" else f"{RED}SAI{OFF}"
        print(f"Đối chứng F02 (giao dịch hợp lệ) → {control['level']} "
              f"({control['score']} điểm)  {state}")
        if control["level"] != "pass":
            print(f"  {RED}Engine đang chặn một giao dịch hợp lệ. Đây là cảnh báo sai, "
                  f"cần sửa trước khi demo.{OFF}")

    wrong_scenario = [d for d in details
                      if d["matched_scenario"] and d["matched_scenario"] != d["expected_scenario"]
                      and d["level"] != "pass"]
    if wrong_scenario:
        print(f"\n{YELLOW}Khớp sai kịch bản:{OFF}")
        for d in wrong_scenario:
            print(f"  {d['case']}: khớp {d['matched_scenario']}, mong đợi {d['expected_scenario']}")

    if os.getenv("FRAUD_TEST_JSON"):
        with open(os.environ["FRAUD_TEST_JSON"], "w") as fh:
            json.dump(details, fh, ensure_ascii=False, indent=2)
        print(f"\nChi tiết đã ghi vào {os.environ['FRAUD_TEST_JSON']}")

    return 0 if failed == 0 and errored == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
