"""Alternative explanations: how tight is the constant-offset interval of v2 (2 numbers) and of the 4-D template,
against the oracle's exact interval (full history, certified inner and outer bounds)? DEV seeds 430060-430079.
Reports the excess width of each outer interval over the oracle's outer interval, and certification at R = 1, 3.
usage: python -B eval_offset.py OUT_JSON
"""
import json
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "oracle"), str(HERE.parent / "machine"), str(HERE.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import template_offset as W  # noqa: E402
import thermal_oracle as O  # noqa: E402
from thermal_machine import ThermalMachine  # noqa: E402

T = S.T
CELLS = ("healthy", "offset_1", "offset_3", "drift_0.0005", "drift_0.001")
TP = None


def job(args):
    global TP
    if TP is None:
        TP = W.OffsetTemplate(W.directions(N=4))
    seed, cname, arm, law = args
    r = S.run(seed, next(c for c in T.CELLS if c.name == cname), arm, law, "uniform")
    m4, m2 = W.OffsetMachine(TP), ThermalMachine()
    for y, p in zip(r["y"], r["P"]):
        m4.observe(y, p)
        m2.observe(y, p)
    with tempfile.TemporaryDirectory() as d:
        v, _, _, inner, outer = O.verdict_and_offsets(r["z"], attempt_dir=d)
    return {"seed": seed, "cell": cname, "arm": arm, "law": law, "oracle_verdict": v, "oracle_inner": inner,
            "oracle_outer": outer, "v2": m2.offset_outer, "v2_inconsistent": m2.inconsistent,
            "v3_4d": m4.offset(), "v3_4d_inconsistent": m4.inconsistent,
            "v2_R": [m2.verdict(1), m2.verdict(3)], "v3_R": [m4.verdict(1), m4.verdict(3)]}


def main():
    tasks = [(s, c, arm, law) for s in range(430060, 430080) for c in CELLS for arm in ("E0",) for law in ("rw", "ramp")]
    with ProcessPoolExecutor(6) as pool:
        rows = list(pool.map(job, tasks))
    ex = {"v2": [], "v3_4d": []}
    agree = {"v2": 0, "v3_4d": 0}
    n = 0
    for r in rows:
        if r["oracle_verdict"] != "consistent" or r["oracle_outer"] is None:
            continue
        n += 1
        lo, hi = r["oracle_outer"]
        for m in ex:
            iv = r[m]
            ex[m].append((lo - iv[0]) + (iv[1] - hi))
        for m, R in (("v2", r["v2_R"]), ("v3_4d", r["v3_R"])):
            exact = ["TUTARLI" if -rad <= lo and hi <= rad else "other" for rad in (1, 3)]
            agree[m] += all((a == "TUTARLI") == (b == "TUTARLI") for a, b in zip(R, exact))
    summary = {"runs": len(rows), "oracle_consistent": n,
               "excess_width_over_oracle_outer": {m: {"max": max(v), "mean": sum(v) / len(v)} for m, v in ex.items()},
               "certification_agrees_with_oracle_outer_R1_R3": agree}
    Path(sys.argv[1]).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
