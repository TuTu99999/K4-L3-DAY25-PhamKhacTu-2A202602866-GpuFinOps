"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    carbon_jobs = []
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

        # Extension 5 — carbon-aware scheduling. Use each job's actual `days`
        # value and catalog TDP as an explicit upper-bound energy estimate.
        if interruptible:
            actual_days = num(j["days"])
            energy_kwh = num(c["watts"]) * hpd * actual_days * ngpu / 1000.0
            current_region = "us-east-1"
            clean_region = min(sustainability.REGION_CARBON,
                               key=sustainability.REGION_CARBON.get)
            carbon_before_kg = energy_kwh * sustainability.REGION_CARBON[current_region] / 1000.0
            carbon_after_kg = energy_kwh * sustainability.REGION_CARBON[clean_region] / 1000.0
            electricity_before = energy_kwh * sustainability.REGION_PRICE_KWH[current_region]
            electricity_after = energy_kwh * sustainability.REGION_PRICE_KWH[clean_region]
            carbon_jobs.append({
                "job_id": j["job_id"], "energy_kwh": round(energy_kwh, 1),
                "from_region": current_region, "to_region": clean_region,
                "carbon_before_kg": round(carbon_before_kg, 1),
                "carbon_after_kg": round(carbon_after_kg, 1),
                "carbon_saved_kg": round(carbon_before_kg - carbon_after_kg, 1),
                "electricity_before_usd": round(electricity_before, 2),
                "electricity_after_usd": round(electricity_after, 2),
            })

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0
    carbon_before_total = sum(r["carbon_before_kg"] for r in carbon_jobs)
    carbon_after_total = sum(r["carbon_after_kg"] for r in carbon_jobs)
    carbon_summary = {
        "method": "actual workload days at catalog TDP",
        "from_region": "us-east-1",
        "to_region": min(sustainability.REGION_CARBON,
                         key=sustainability.REGION_CARBON.get),
        "carbon_before_kg": round(carbon_before_total, 1),
        "carbon_after_kg": round(carbon_after_total, 1),
        "carbon_saved_kg": round(carbon_before_total - carbon_after_total, 1),
        "electricity_before_usd": round(sum(r["electricity_before_usd"] for r in carbon_jobs), 2),
        "electricity_after_usd": round(sum(r["electricity_after_usd"] for r in carbon_jobs), 2),
    }

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")
        print("\ncarbon-aware scheduling (interruptible jobs, actual job days, TDP estimate):")
        for r in carbon_jobs:
            print(f"  {r['job_id']:18} {r['carbon_before_kg']:>7.1f} -> "
                  f"{r['carbon_after_kg']:>7.1f} kgCO2e  saved={r['carbon_saved_kg']:>7.1f}")
        print(f"  total: {carbon_summary['carbon_before_kg']:,.1f} -> "
              f"{carbon_summary['carbon_after_kg']:,.1f} kgCO2e "
              f"(saved {carbon_summary['carbon_saved_kg']:,.1f} kgCO2e)")
        print(f"  electricity: ${carbon_summary['electricity_before_usd']:,.2f} -> "
              f"${carbon_summary['electricity_after_usd']:,.2f}; "
              "cleanest is not the cheapest region")

    return {"recommendations": recs, "on_demand_monthly": round(on_demand_monthly),
            "optimized_monthly": round(optimized_monthly), "savings_pct": round(savings_pct, 1),
            "carbon_jobs": carbon_jobs, "carbon_summary": carbon_summary}


if __name__ == "__main__":
    run()
