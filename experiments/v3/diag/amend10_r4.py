"""DIAG-3 amendment 10, R4 (DIAG-3-PLAN.md): F3 on (440243, healthy, E0, ramp, edge), the run that failed freeze 2.

Freeze 2's block is no longer a holdout: this tests the code and is not evidence. The run is replayed in full with
F3a (F3 with the exact rational audit). Every P_J fallback is logged with its sample, direction, bound and a priori
support. Criterion U4:
  - all 3600 samples, no alarm (the run is healthy, so admissible);
  - the t = 945 fold takes the P_J bound for direction 40;
  - the exact audit, that bound included, finds no violation.
The validation seeds are unlocked with freeze 2's manifest sha256, as in the diagnosis of 2026-11-19 (Can's decision);
nothing else of that block is generated.
usage: python -B amend10_r4.py OUT
       python -B amend10_r4.py check OUT/r4.json
"""
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for sub in ("env", "experiments/generators", "experiments/machine", "experiments/oracle", "experiments/v3"):
    sys.path.insert(0, str(ROOT / sub))
sys.path.insert(0, str(HERE))
import diag3_cw as C  # noqa: E402
import diag3_cw_dev as CD  # noqa: E402
import run_validation as RV1  # noqa: E402

G, S, T, V = C.G, C.S, C.T, C.V
SEED, CELL, ARM, AMB, NOISE = 440243, "healthy", "E0", "ramp", "edge"


def u4_of(rec, log, audit):
    """U4 as made exact by amendment 10's second addendum: the P_J bound for direction 40 at t = 945 exists, is below
    its a priori support and is confirmed by the exact audit"""
    return {"all_samples": rec["steps"] == T.N - 1, "no_alarm": rec["detect"] is None,
            "dir40_at_945_implied": any(x["t"] == 945 and x["dir"] == 40 and x["bound"] is not None
                                        and x["bound"] < x["apriori"] for x in log),
            "audit_no_violation": audit["violations"] == 0 and audit["n_implied"] > 0}


def check(path):
    """re-evaluate U4 from an existing r4.json"""
    rep = json.loads(Path(path).read_text())
    u4 = u4_of(rep["record"], rep["implied_log"], rep["audit"])
    print(json.dumps({"U4": all(u4.values()), "u4": u4, "git_head_of_run": rep["meta"]["git_head"]}, indent=1))


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    msha = RV1.sha256(ROOT / "experiments" / "v3" / "frozen" / "MANIFEST-V2.json")
    S.unlock_validation(msha)
    r = S.run(SEED, next(c for c in T.CELLS if c.name == CELL), ARM, AMB, NOISE)
    tp = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    apriori = tp.clamp(np.full(len(tp.D), np.inf))
    log, box = [], {}
    orig_implied, orig_make = C.Failsafe.implied, C.make

    def implied(self, i, J, h):
        b = orig_implied(self, i, J, h)
        log.append({"t": self.now, "dir": i, "bound": b, "apriori": float(apriori[i]), "n_solved": len(J)})
        return b

    def make(var, cy):
        box["w"] = orig_make(var, cy)
        return box["w"]

    C.Failsafe.implied, C.make = implied, make
    t0 = time.monotonic()
    try:
        rec = CD.online("F3a", G.zs_of(r), 256, 64, None, tp=tp)
    finally:
        C.Failsafe.implied, C.make = orig_implied, orig_make
    audit = box["w"].audit
    u4 = u4_of(rec, log, audit)
    rep = {"key": [SEED, CELL, ARM, AMB, NOISE], "U4": all(u4.values()), "u4": u4, "implied_log": log, "audit": audit,
           "record": rec, "meta": {
               "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip(),
               "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=HERE).returncode),
               "platform": platform.platform(), "seconds": round(time.monotonic() - t0, 1)}}
    (out / "r4.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps({"U4": rep["U4"], "u4": u4, "implied_log": log[:10], "failsafe": rec["failsafe"]}, default=str))


if __name__ == "__main__":
    if sys.argv[1] == "check":
        check(sys.argv[2])
    else:
        main(Path(sys.argv[1]))
