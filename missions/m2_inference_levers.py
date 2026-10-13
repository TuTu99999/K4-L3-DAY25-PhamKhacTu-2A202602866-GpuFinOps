"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = cascade_cost = cache_cost = opt_cost = 0.0
    total_tokens = 0
    reasoning = {
        "reasoning": {"requests": 0, "tokens": 0, "cost": 0.0, "wh": 0.0},
        "standard": {"requests": 0, "tokens": 0, "cost": 0.0, "wh": 0.0},
    }
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # Apply one lever at a time so its marginal contribution is measurable.
        pin, pout = MODEL_PRICES[r["route_tier"]]
        routed = pricing.request_cost(inp, out, pin, pout)
        cached_cost = pricing.request_cost(inp, out, pin, pout, cached_in=cached)
        optimized = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        cascade_cost += routed
        cache_cost += cached_cost
        opt_cost += optimized

        group = reasoning["reasoning" if is_reasoning else "standard"]
        tokens = inp + out
        group["requests"] += 1
        group["tokens"] += tokens
        group["cost"] += optimized
        group["wh"] += sustainability.wh_per_query(tokens, is_reasoning=is_reasoning)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    lever_savings = {
        "cascade": base_cost - cascade_cost,
        "cache": cascade_cost - cache_cost,
        "batch": cache_cost - opt_cost,
    }

    # Extension 4 — cap reasoning at 10% of requests. The current seeded dataset
    # is already below the cap, so no requests are removed and measured savings
    # are correctly zero rather than invented.
    reasoning_requests = reasoning["reasoning"]["requests"]
    cap_requests = int(len(rows) * 0.10)
    requests_over_cap = max(0, reasoning_requests - cap_requests)
    if reasoning_requests and requests_over_cap:
        removed_frac = requests_over_cap / reasoning_requests
        cap_cost_savings = reasoning["reasoning"]["cost"] * removed_frac
        cap_wh_savings = reasoning["reasoning"]["wh"] * removed_frac
    else:
        cap_cost_savings = cap_wh_savings = 0.0

    for group in reasoning.values():
        group["cost"] = round(group["cost"], 4)
        group["wh"] = round(group["wh"], 2)

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print("marginal savings ($/day): " + ", ".join(
            f"{name}=${value:,.2f}" for name, value in lever_savings.items()))
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("reasoning budget:")
        for name, group in reasoning.items():
            req_pct = group["requests"] / len(rows) * 100 if rows else 0.0
            print(f"  {name:9} {group['requests']:4} req ({req_pct:4.1f}%)  "
                  f"${group['cost']:,.2f}/day  {group['wh']:,.0f} Wh/day")
        print(f"  cap=10%: {requests_over_cap} requests over cap; "
              f"savings=${cap_cost_savings:,.2f}/day, {cap_wh_savings:,.0f} Wh/day")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "stage_costs_daily": {
            "baseline": round(base_cost, 4), "cascade": round(cascade_cost, 4),
            "cache": round(cache_cost, 4), "optimized": round(opt_cost, 4),
        },
        "lever_savings_daily": {k: round(v, 4) for k, v in lever_savings.items()},
        "reasoning": reasoning,
        "reasoning_cap": {
            "cap_pct": 10.0, "requests_over_cap": requests_over_cap,
            "cost_savings_daily": round(cap_cost_savings, 4),
            "wh_savings_daily": round(cap_wh_savings, 2),
        },
    }


if __name__ == "__main__":
    run()
