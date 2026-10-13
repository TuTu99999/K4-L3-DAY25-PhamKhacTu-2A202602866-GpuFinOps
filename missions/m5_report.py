"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, ROOT
from finops import report, sustainability
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    for lie in r1["lies"]:
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size util-lies": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "cleanest_region": min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get),
        "cheapest_region": min(sustainability.REGION_PRICE_KWH,
                               key=sustainability.REGION_PRICE_KWH.get),
    }

    monthly_tokens = r2["total_tokens"] * DAYS
    units = {
        "baseline_per_m": baseline / (monthly_tokens / 1e6),
        "optimized_per_m": optimized / (monthly_tokens / 1e6),
        "inference_baseline_per_m": r2["baseline_per_m"],
        "inference_optimized_per_m": r2["optimized_per_m"],
    }
    reason = r2["reasoning"]
    cap = r2["reasoning_cap"]
    carbon = r3["carbon_summary"]
    reasoning_total_cost = reason["reasoning"]["cost"] + reason["standard"]["cost"]
    reasoning_total_wh = reason["reasoning"]["wh"] + reason["standard"]["wh"]
    reason_req_pct = reason["reasoning"]["requests"] / (
        reason["reasoning"]["requests"] + reason["standard"]["requests"]) * 100
    reason_cost_pct = reason["reasoning"]["cost"] / reasoning_total_cost * 100
    reason_wh_pct = reason["reasoning"]["wh"] / reasoning_total_wh * 100
    extension_lines = [
        "## Hai phần mở rộng đã thực hiện",
        "",
        "### 1. Ngân sách cho Reasoning",
        "",
        f"Trong bộ dữ liệu này, reasoning chỉ chiếm **{reason_req_pct:.1f}% số request**, "
        f"nhưng lại chiếm **{reason_cost_pct:.1f}% chi phí inference sau tối ưu** và "
        f"**{reason_wh_pct:.1f}% điện năng ước tính**. Khi thử đặt ngưỡng 10%, "
        f"có **{cap['requests_over_cap']} request** vượt ngưỡng; mức tiết kiệm tương ứng là "
        f"**${cap['cost_savings_daily']:.2f}/ngày** và **{cap['wh_savings_daily']:.0f} Wh/ngày**. "
        "Traffic hiện tại vốn đã dưới 10%, nên kết quả bằng 0 là hợp lý. Tôi đề xuất chỉ bật "
        "reasoning cho câu hỏi khó hoặc khi model có độ tin cậy thấp, đồng thời cảnh báo sớm khi tỷ lệ này gần 10%.",
        "",
        "| Nhóm traffic | Số request | Chi phí sau tối ưu/ngày | Điện năng/ngày |",
        "|---|---:|---:|---:|",
        f"| Reasoning | {reason['reasoning']['requests']} | ${reason['reasoning']['cost']:.2f} | {reason['reasoning']['wh']:,.0f} Wh |",
        f"| Standard | {reason['standard']['requests']} | ${reason['standard']['cost']:.2f} | {reason['standard']['wh']:,.0f} Wh |",
        f"| After 10% cap | {reason['reasoning']['requests'] - cap['requests_over_cap']} reasoning requests | "
        f"${reasoning_total_cost - cap['cost_savings_daily']:.2f} total | "
        f"{reasoning_total_wh - cap['wh_savings_daily']:,.0f} Wh total |",
        "",
        "### 2. Lập lịch theo lượng carbon",
        "",
        f"Tôi thử chuyển các job có thể gián đoạn từ **{carbon['from_region']}** sang vùng sạch nhất "
        f"là **{carbon['to_region']}**. Lượng phát thải ước tính giảm từ "
        f"**{carbon['carbon_before_kg']:,.1f} xuống {carbon['carbon_after_kg']:,.1f} kgCO2e**, "
        f"tức giảm **{carbon['carbon_saved_kg']:,.1f} kgCO2e**. Chi phí điện ước tính cũng giảm "
        f"từ **${carbon['electricity_before_usd']:,.2f} xuống ${carbon['electricity_after_usd']:,.2f}**. "
        "Phép tính dùng số ngày chạy thật của từng job và TDP trong catalog, nên chỉ nên xem là một "
        "ước lượng trần. Khi triển khai thật vẫn phải cân nhắc latency, nơi lưu dữ liệu và phí truyền dữ liệu.",
        "",
        "| Job có thể gián đoạn | Điện năng | Carbon trước | Carbon sau | Lượng giảm |",
        "|---|---:|---:|---:|---:|",
    ]
    for job in r3["carbon_jobs"]:
        extension_lines.append(
            f"| {job['job_id']} | {job['energy_kwh']:,.1f} kWh | "
            f"{job['carbon_before_kg']:,.1f} kg | {job['carbon_after_kg']:,.1f} kg | "
            f"{job['carbon_saved_kg']:,.1f} kg |")
    extension_lines += [
        "",
        "## Nhận xét và thứ tự hành động",
        "",
        "1. Ưu tiên lại cách mua GPU bằng spot/reserved vì đây là khoản tiết kiệm lớn nhất.",
        "2. Áp dụng cascade, cache và batch, nhưng vẫn phải theo dõi chất lượng đầu ra và độ trễ.",
        "3. Kiểm tra các GPU có util cao nhưng MFU thấp, sau đó tự động tắt GPU idle trước khi chargeback.",
        "",
        "GPU-Util cao chỉ cho biết GPU có hoạt động trong lúc lấy mẫu, chứ chưa nói rằng GPU làm việc hiệu quả. "
        "Memory stall, kernel nhỏ, đồng bộ hoặc launch overhead vẫn có thể làm GPU trông rất bận trong khi FLOPs "
        "hữu ích thấp. Vì vậy cần đọc GPU-Util cùng với MFU, MBU và chi phí trên mỗi triệu token.",
    ]
    extensions = "\n".join(extension_lines)

    md = report.build_report(
        baseline, optimized, levers, sustainability=sust,
        unit_economics=units,
        inference_breakdown=r2["lever_savings_daily"],
        extensions=extensions,
    )
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    png = report.savings_waterfall(
        levers, os.path.join(ROOT, "outputs", "savings.png"), baseline_usd=baseline)

    if verbose:
        print("== M5 Optimization Report ==")
        print(md)
        print(f"\nWritten: outputs/report.md" + (f" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "baseline_per_m": round(units["baseline_per_m"], 3),
            "optimized_per_m": round(units["optimized_per_m"], 3),
            "levers": levers, "total_savings_pct": round(total_pct, 1),
            "reasoning": reason, "reasoning_cap": cap, "carbon": carbon}


if __name__ == "__main__":
    run()
