"""WIDEBOX: split each monitor's lag against the frozen t* into the exact detector's own delay at the wider box and
the monitor's lag against that box's t* (RECORD-2026-11-22-widebox.md). Written after the run; reads stored rows only.

  python -B widebox_split.py RESULTS        RESULTS = results/v3/widebox-a196fd68; writes RESULTS/split.json

Over the 1,081 events certified at the frozen box [23, 27], with a miss counted as N - t*:
  lag of m against the frozen t*  =  own(b)  +  lag of m against t*(b),
where own(b) is the oracle at box b scored against the frozen t* (an event it no longer detects counts N - t*), and
the second term sums over the events the oracle still detects at b. The split is exact because no monitor alarms
where the box-b oracle certifies the run consistent (checked below) and the oracle is never earlier at a wider box.
"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
N = 3600                                                   # thermal.N, the record length (samples)
DEV = ROOT / "results/v3/dev-45cff1d/rows.jsonl"          # the frozen oracle and v2
AMB = ROOT / "results/v3/ambient/amb-443d8b30-mac"        # IM and TS at [23, 27], part (b)
F3 = ROOT / "results/v3/diag3/amend10-r1r2-0ce80072-arch/R-none"   # F3 at [23, 27], the DEV reference


def key(d):
    return f"{d['seed']}-{d['cell']}-{d['arm']}-{d['ambient']}-{d['noise']}"


def lag(t, ref):
    return N - ref if t is None else t - ref


def main(res):
    frozen = {key(d): d for d in map(json.loads, DEV.read_text().splitlines())}
    ev = {k: d["oracle"]["t_star"] for k, d in frozen.items()
          if d["oracle"]["status"] == "certified" and d["oracle"]["t_star"] is not None}
    mon0 = {"v2": {}, "cyl16p": {}, "F3": {}}
    for k in ev:
        a = json.loads((AMB / f"b-{k}.json").read_text())
        mon0["v2"][k], mon0["cyl16p"][k] = a["v2@23-27"], a["cyl16p@23-27"]
        mon0["F3"][k] = json.loads((F3 / f"{k}.json").read_text())["detect"]
    rep = {"events_frozen": len(ev), "N": N,
           "frozen": {m: {"lag": sum(lag(t[k], ev[k]) for k in ev), "misses": sum(t[k] is None for k in ev)}
                      for m, t in mon0.items()},
           "boxes": {}}
    for b in ("22-28", "21-29"):
        with gzip.open(res / f"rows-{b}.jsonl.gz", "rt") as f:
            rows = {r["key"]: r for r in map(json.loads, f)}
        tb = {}
        for k in ev:
            o = rows[k]["oracle"]
            assert o["status"] == "certified", (b, k, o)
            tb[k] = o["t_star"]
            assert tb[k] is None or tb[k] >= ev[k], (b, k, "earlier than frozen")
        own = sum(lag(tb[k], ev[k]) for k in ev)
        r = {"oracle": {"own_delay_s": own, "events_lost": sum(tb[k] is None for k in ev),
                        "events_later": sum(tb[k] is not None and tb[k] > ev[k] for k in ev),
                        "delay_on_events_kept_s": sum(tb[k] - ev[k] for k in ev if tb[k] is not None)},
             "monitors": {}}
        for m in ("v2", "cyl16p", "F3"):
            tm = {k: (rows[k][m]["detect"] if m == "F3" else rows[k][m]) for k in ev}
            assert not any(tb[k] is None and tm[k] is not None for k in ev), (b, m, "alarm where t*(b) is none")
            total = sum(lag(tm[k], ev[k]) for k in ev)
            mine = sum(lag(tm[k], tb[k]) for k in ev if tb[k] is not None)
            assert total == own + mine, (b, m, total, own, mine)
            r["monitors"][m] = {"against_frozen_t_star": total, "assumption": own, "against_t_star_b": mine,
                                "assumption_share": round(own / total, 4) if total else None,
                                "misses_against_t_star_b": sum(tm[k] is None for k in ev if tb[k] is not None)}
        rep["boxes"][b] = r
    (res / "split.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
