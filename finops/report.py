"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly",
                 unit_economics: dict | None = None,
                 inference_breakdown: dict | None = None,
                 extensions: str | None = None) -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# Báo cáo tối ưu chi phí GPU — NimbusAI",
        "",
        f"**Kỳ báo cáo:** {period}  ",
        f"**Chi phí baseline:** ${baseline_usd:,.0f}  ",
        f"**Chi phí sau tối ưu:** ${optimized_usd:,.0f}  ",
        f"**Projected savings (tiết kiệm dự kiến):** ${savings:,.0f}  (**{pct:.0f}%**)",
    ]
    if unit_economics:
        lines += [
            f"**Unit cost baseline:** ${unit_economics.get('baseline_per_m', 0):,.3f}/1M-token  ",
            f"**Unit cost sau tối ưu:** ${unit_economics.get('optimized_per_m', 0):,.3f}/1M-token",
            f"**Unit cost riêng inference:** ${unit_economics.get('inference_baseline_per_m', 0):,.3f} "
            f"→ ${unit_economics.get('inference_optimized_per_m', 0):,.3f}/1M-token",
        ]
    lines += ["", "## Tiết kiệm theo từng đòn bẩy", "", "| Đòn bẩy | Tiết kiệm (USD/tháng) |", "|---|---|"]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if inference_breakdown:
        lines += [
            "", "### Chi tiết phần tiết kiệm inference", "",
            "Ba cách tối ưu được áp dụng lần lượt trên cùng một lượng traffic. Vì vậy, "
            "các khoản tiết kiệm dưới đây có thể cộng lại mà không bị tính trùng.", "",
            "| Đòn bẩy inference | Tiết kiệm (USD/ngày) | Tiết kiệm (USD/tháng) |",
            "|---|---:|---:|",
        ]
        for name, daily in inference_breakdown.items():
            lines.append(f"| {name.title()} | ${daily:,.2f} | ${daily * 30:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Điện năng và phát thải",
            "",
            f"- Điện năng mỗi query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Phát thải mỗi query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Vùng sạch nhất: {sustainability.get('cleanest_region', 'n/a')}",
            f"- Vùng có giá điện thấp nhất: {sustainability.get('cheapest_region', 'n/a')}",
        ]
    if extensions:
        lines += ["", extensions]
    lines += ["", "_Các con số dùng snapshot tháng 6/2026; cần cập nhật lại trước khi áp dụng thực tế._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, baseline_usd: float | None = None) -> str:
    """Write a baseline-to-optimized savings waterfall PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers)
    vals = [float(levers[n]) for n in names]
    baseline = float(baseline_usd) if baseline_usd is not None else sum(vals)
    running = baseline
    labels = ["Baseline"] + names + ["Optimized"]
    heights = [baseline]
    bottoms = [0.0]
    colors = ["#2e548a"]
    for value in vals:
        running -= value
        heights.append(value)
        bottoms.append(running)
        colors.append("#4f9d69")
    heights.append(running)
    bottoms.append(0.0)
    colors.append("#d17a22")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(labels, heights, bottom=bottoms, color=colors)
    for index, (bar, height, bottom) in enumerate(zip(bars, heights, bottoms)):
        if index == 0 or index == len(bars) - 1:
            text = f"${height:,.0f}"
        else:
            text = f"-${height:,.0f}"
        ax.text(bar.get_x() + bar.get_width() / 2, bottom + height / 2,
                text, ha="center", va="center", color="white", fontsize=9,
                fontweight="bold")
    ax.set_ylabel("Monthly cost (USD)")
    ax.set_title("NimbusAI GPU cost: baseline to optimized")
    plt.xticks(rotation=18, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
