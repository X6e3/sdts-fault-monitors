"""Sensitivity of the validation scores to the choice of metric (2026-11-22; RECORD-2026-11-22-review-checks.md).

  python -B experiments/v3/diag/metric_sensitivity.py

From the recorded rows of validations 1 and 3 only (no simulation, no LP). For each candidate: D_paired as frozen
(on B, the certified events IM detects, a miss at N - t*); the same ratio over all certified events with every miss
at N - t*; the same with every lag capped at 30 s; the 90th and 99th percentile of the lag over detected events; the
misses over all certified events. Also IM's lag share of the drift cells on B and on all certified events.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
N = 3600
BLOCKS = {"validation 1": ("results/v3/freeze1/validation-440000-440199/rows.jsonl",
                           {"inv4p": lambda r: r["candidates"]["inv4p"], "TS": lambda r: r["candidates"]["cyl16p"]}),
          "validation 3": ("results/v3/freeze3/validation-440400-440599-948b46b0/rows.jsonl",
                           {"WM": lambda r: r["F3"]["detect"]})}


def det(x):
    return x["first"] if isinstance(x, dict) else x


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return math.nan
    k = (len(xs) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def lag(d, ts, cap=None):
    v = (N if d is None else d) - ts
    return v if cap is None else min(v, cap)


def main():
    out = {}
    for name, (path, cands) in BLOCKS.items():
        rows = [json.loads(l) for l in (ROOT / path).read_text().splitlines() if l.strip()]
        ev = [r for r in rows if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
        B = [r for r in ev if r["v2"] is not None]
        im = lambda r: r["v2"]
        res = {"events": len(ev), "B": len(B), "IM_misses": sum(r["v2"] is None for r in ev)}
        L = {k: sum(lag(f(r), r["oracle"]["t_star"]) for r in B) for k, f in [("IM", im)] + list(cands.items())}
        A = {k: sum(lag(f(r), r["oracle"]["t_star"]) for r in ev) for k, f in [("IM", im)] + list(cands.items())}
        C = {k: sum(lag(f(r), r["oracle"]["t_star"], 30) for r in ev) for k, f in [("IM", im)] + list(cands.items())}
        for k, f in list(cands.items()) + [("IM", im)]:
            dl = [lag(f(r), r["oracle"]["t_star"]) for r in ev if f(r) is not None]
            res[k] = {"D_paired": 1 - L[k] / L["IM"], "all_events": 1 - A[k] / A["IM"],
                      "all_events_capped_30s": 1 - C[k] / C["IM"], "p90_s": pct(dl, 0.9), "p99_s": pct(dl, 0.99),
                      "misses": sum(f(r) is None for r in ev), "L_B": L[k], "L_all": A[k]}
        drift = lambda rs: sum(lag(r["v2"], r["oracle"]["t_star"]) for r in rs if r["cell"].startswith("drift"))
        res["IM_drift_share_B"] = drift(B) / L["IM"]
        res["IM_drift_share_all"] = drift(ev) / A["IM"]
        slow = ("drift_0.0005", "drift_0.001", "drift_0.002")
        res["IM_three_slowest_drifts_share_B"] = sum(lag(r["v2"], r["oracle"]["t_star"]) for r in B
                                                     if r["cell"] in slow) / L["IM"]
        out[name] = res
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
