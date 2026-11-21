"""ISOLATION-PLAN.md section 5: the items reported, not deciding, that `iso_run.py summary` does not compute.

Written after the run (2026-11-21), committed before it was run. It reads the run's per-row files and the records of
R1 (DIAG-3 amendment 10, setting none: F3 with no failure, at 0ce80072); it runs nothing.
  - detections against R1, row by row: equal, later, earlier, missed; D_paired against v2 for both
  - the cost of isolation: the per-row seconds summed, against R1's (R1 ran with 14 workers, this run with 10)
  - rows with any injected failure, and natural restarts (from the summary)

  python -B iso_report.py ISO_OUT R1_DIR [--json FILE]
"""
import argparse
import json
from pathlib import Path

import baselines_run as BR

N = BR.N


def r1_name(r):
    if r["noise"] == "edge":
        return f"edge-{r['seed']}-{r['arm']}-{r['ambient']}.json"
    return BR.key(r) + ".json"


def dpaired(rows, det):
    paired = [r for r in rows if r["status"] == "certified" and r["t_star"] is not None and r["v2"] is not None]
    lv2 = sum(r["v2"] - r["t_star"] for r in paired)
    lag = sum((N if det[BR.key(r)] is None else det[BR.key(r)]) - r["t_star"] for r in paired)
    return 1 - lag / lv2, lag, lv2, len(paired)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("iso", type=Path)
    ap.add_argument("r1", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    rows = BR.dev_rows()
    iso = {BR.key(r): json.loads((a.iso / f"iso-{BR.key(r)}.json").read_text()) for r in rows}
    r1 = {BR.key(r): json.loads((a.r1 / r1_name(r)).read_text()) for r in rows}
    cmp = {"equal": 0, "later": [], "earlier": [], "missed": [], "new": [], "margin_differs": []}
    for k in iso:
        x, y = iso[k]["detect"], r1[k]["detect"]
        if x == y:
            cmp["equal"] += 1
            mx, my = iso[k]["margin_at_detect_mC"], r1[k]["margin_at_detect_mC"]
            if x is not None and abs(mx - my) > 1e-6:
                cmp["margin_differs"].append([k, mx, my])
        elif x is None:
            cmp["missed"].append([k, y])
        elif y is None:
            cmp["new"].append([k, x])
        elif x > y:
            cmp["later"].append([k, x, y])
        else:
            cmp["earlier"].append([k, x, y])
    later = sorted(x - y for _, x, y in cmp["later"])
    d_iso = dpaired(rows, {k: v["detect"] for k, v in iso.items()})
    d_r1 = dpaired(rows, {k: v["detect"] for k, v in r1.items()})
    inj_rows = sum(1 for v in iso.values() if sum(v["injected"].values()) > 0)
    rep = {"rows": len(iso), "detections_vs_R1": {"equal": cmp["equal"], "later": len(cmp["later"]),
           "later_by_median_max": [later[len(later) // 2], later[-1]] if later else None,
           "earlier": len(cmp["earlier"]), "missed": len(cmp["missed"]), "new": len(cmp["new"]),
           "margin_differs_on_equal": len(cmp["margin_differs"])},
           "later_rows": cmp["later"], "missed_rows": cmp["missed"], "earlier_rows": cmp["earlier"],
           "alarms": sum(v["detect"] is not None for v in iso.values()),
           "D_paired": {"iso": d_iso[0], "R1": d_r1[0], "paired_events": d_iso[3], "lag_iso": d_iso[1],
                        "lag_R1": d_r1[1], "lag_v2": d_iso[2]},
           "seconds": {"iso": round(sum(v["seconds"] for v in iso.values()), 1),
                       "R1": round(sum(v["seconds"] for v in r1.values()), 1)},
           "rows_with_injection": inj_rows,
           "restarts": sum(v["restarts"] for v in iso.values()),
           "measurements_not_kept": sum(v["failsafe"]["measurements_not_kept"] for v in iso.values()),
           "full_resets": sum(v["failsafe"]["fold_full_resets"] for v in iso.values())}
    txt = json.dumps(rep, indent=1)
    print(txt)
    if a.json:
        a.json.write_text(txt + "\n")


if __name__ == "__main__":
    main()
