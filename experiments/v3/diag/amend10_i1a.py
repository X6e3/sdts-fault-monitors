"""I1a (DIAG-3 amendment 10, third addendum; this is the script as it ran, from a scratch copy): run amend10.job on a fixed subset with the code in SRC, and track memory.
usage: python -B i1a.py SRC OUT"""
import json, sys, time
from pathlib import Path
SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(SRC / "experiments/v3/diag"))
import amend10 as A  # noqa: E402
C = A.C
mem = {"max_zs": 0, "max_last_active": 0, "subset_violations": 0, "checks": 0}
ok_, oe_, of_ = C.Compressed.keep, C.Compressed.evict, C.Failsafe.fold
def chk(w):
    mem["checks"] += 1
    mem["max_zs"] = max(mem["max_zs"], len(w.zs)); mem["max_last_active"] = max(mem["max_last_active"], len(w.last_active))
    if not set(w.last_active) <= set(w.zs): mem["subset_violations"] += 1
def keep(self, t, z): ok_(self, t, z); chk(self)
def evict(self): oe_(self); chk(self)
def fold(self, t): of_(self, t); chk(self)
C.Compressed.keep, C.Compressed.evict, C.Failsafe.fold = keep, evict, fold
rows = [json.loads(l) for l in A.D.ROWS.read_text().splitlines() if l.strip()]
fault = sorted((r for r in rows if r["oracle"].get("t_star") is not None), key=lambda r: A.D.key(r))
dev = [fault[i] for i in (0, 100, 200, 300)]
edge = list(A.EDGE)[:4]
OUT.mkdir(parents=True, exist_ok=True)
sel = {"edge": edge, "dev": [A.D.key(r) for r in dev]}
(OUT / "selection.json").write_text(json.dumps(sel, default=str) + "\n")
per = {}
for setting in ("none", "d"):
    o = OUT / setting
    o.mkdir(exist_ok=True)
    for kind, spec in [("edge", e) for e in edge] + [("dev", r) for r in dev]:
        for k in mem: mem[k] = 0
        t0 = time.monotonic()
        key = A.job((kind, spec, setting, "F3", str(o)))[0]
        per[f"{setting}/{key}"] = dict(mem, seconds=round(time.monotonic() - t0, 1))
        print(setting, key, per[f"{setting}/{key}"], flush=True)
(OUT / "memory.json").write_text(json.dumps(per, indent=1) + "\n")
print("done", flush=True)
