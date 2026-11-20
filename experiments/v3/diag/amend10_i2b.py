"""DIAG-3 amendment 10, I2b as Can set it on 2026-11-20 (DIAG-3-PLAN.md): the frozen code on all of R-none and on a
sample of R-b, R-d and R-e, compared with the 0ce80072 records of the R1-R2 drive on Arch.

Written and committed before it ran. Nothing here is part of the candidate. The selection is fixed by `select`,
before any run, from amend10.run's own job list, in its order, and from the 0ce80072 records:
  - none: every job (1400);
  - b, d and e: every job whose index in that list is a multiple of 10 (140 each);
  - d and e also: the 20 jobs outside those with the largest total of fallback events in their 0ce80072 record (the
    sum of every amend10.FALLBACK counter over its kinds), ties broken by the sha256 of the key.
The comparison is that of I1 and I2a: every field except seconds, step_ms and fold_step_ms.
usage: python -B amend10_i2b.py select REF OUT    (REF: the drive's run dir, holding R-none, R-b, R-d and R-e)
       python -B amend10_i2b.py run OUT --workers N
       python -B amend10_i2b.py compare REF OUT
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import amend10 as A  # noqa: E402

D = A.D
SETTINGS = ("none", "b", "d", "e")
WALL = {"seconds", "step_ms", "fold_step_ms"}


def jobs_in_order(setting, out):
    """amend10.run's job list, in its order"""
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: r["oracle"].get("t_star") is not None)
    return ([("edge", e, setting, "F3", str(out)) for e in A.EDGE]
            + [("dev", r, setting, "F3", str(out)) for r in rows])


def key_of(job):
    kind, spec = job[0], job[1]
    return D.key(spec) if kind == "dev" else "edge-{}-{}-{}".format(*spec)


def fallback_total(rec):
    fs = rec["failsafe"]
    return sum(sum(fs[k].values()) if isinstance(fs[k], dict) else int(fs[k]) for k in A.FALLBACK)


def select(ref, out):
    out.mkdir(parents=True, exist_ok=False)
    sel, extra = {}, {}
    for s in SETTINGS:
        keys = [key_of(j) for j in jobs_in_order(s, out)]
        assert len(keys) == len(set(keys)) == 1400
        if s == "none":
            sel[s] = keys
            continue
        tenth = [k for i, k in enumerate(keys) if i % 10 == 0]
        if s == "b":
            sel[s] = tenth
            continue
        rest = sorted(set(keys) - set(tenth))
        score = {k: fallback_total(json.loads((ref / f"R-{s}" / f"{k}.json").read_text())) for k in rest}
        top = sorted(rest, key=lambda k: (-score[k], hashlib.sha256(k.encode()).hexdigest()))[:20]
        sel[s] = tenth + top
        extra[s] = [{"key": k, "fallback_total": score[k]} for k in top]
    blob = json.dumps(sel, sort_keys=True).encode()
    rep = {"selection": sel, "targeted": extra, "counts": {s: len(v) for s, v in sel.items()},
           "selection_sha256": hashlib.sha256(blob).hexdigest(), "ref": str(ref)}
    (out / "selection.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps({k: rep[k] for k in ("counts", "targeted", "selection_sha256")}, indent=1))


def run(out, workers):
    sel = json.loads((out / "selection.json").read_text())["selection"]
    jobs = []
    for s in SETTINGS:
        o = out / f"R-{s}"
        o.mkdir(exist_ok=True)
        want = set(sel[s])
        jobs += [j for j in jobs_in_order(s, o) if key_of(j) in want]
    assert len(jobs) == sum(len(v) for v in sel.values())
    git = ["git", "rev-parse", "HEAD"], ["git", "diff", "--quiet", "HEAD"]
    meta = {"workers": workers, "n_jobs": len(jobs),
            "git_head": subprocess.run(git[0], cwd=HERE, capture_output=True, text=True).stdout.strip(),
            "git_dirty_tracked": bool(subprocess.run(git[1], cwd=HERE).returncode),
            "machine": platform.machine(), "platform": platform.platform(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    with ProcessPoolExecutor(workers) as pool:
        for f in as_completed([pool.submit(A.job, j) for j in jobs]):
            print(f.result(), flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def compare(ref, out):
    sel = json.loads((out / "selection.json").read_text())["selection"]
    rep, ok = {}, True
    for s in SETTINGS:
        same, diff = 0, []
        for k in sel[s]:
            pa, pb = ref / f"R-{s}" / f"{k}.json", out / f"R-{s}" / f"{k}.json"
            if not (pa.exists() and pb.exists()):
                diff.append({"key": k, "fields": "missing on one side"})
                continue
            a, b = (json.loads(p.read_text()) for p in (pa, pb))
            fa = {x: v for x, v in a.items() if x not in WALL}
            fb = {x: v for x, v in b.items() if x not in WALL}
            if fa == fb:
                same += 1
            else:
                diff.append({"key": k, "fields": sorted(x for x in set(fa) | set(fb) if fa.get(x) != fb.get(x))})
        rep[s] = {"selected": len(sel[s]), "identical_except_wall_clock": same, "differ": diff}
        ok = ok and not diff and same == len(sel[s])
    rep["I2b"] = ok
    (out / "compare.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("select")
    p.add_argument("ref", type=Path)
    p.add_argument("out", type=Path)
    p = sub.add_parser("run")
    p.add_argument("out", type=Path)
    p.add_argument("--workers", type=int, required=True)
    p = sub.add_parser("compare")
    p.add_argument("ref", type=Path)
    p.add_argument("out", type=Path)
    a = ap.parse_args()
    if a.cmd == "select":
        select(a.ref, a.out)
    elif a.cmd == "run":
        run(a.out, a.workers)
    else:
        compare(a.ref, a.out)


if __name__ == "__main__":
    main()
