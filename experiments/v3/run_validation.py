"""v3 independent validation of the frozen candidates (FREEZE-V1.md): oracle vs v2 vs inv4p vs cyl16p.

Refuses to touch validation seeds unless:
  - the working tree is clean (tracked files) and the v2 environment lock holds;
  - frozen/MANIFEST.json matches every file it lists (code, frozen tables, C headers);
  - FREEZE-V1.md quotes that manifest's sha256 and carries the approval line written after Can's review;
  - the seeds are exactly the manifest's validation block and OUT does not exist.
--rehearsal runs the identical pipeline on DEV seeds only (no approval needed, validation stays locked).

Per run: certified oracle t*, the v2 machine, both candidates (Python reference, float64), and the C builds of
both candidates in float32 and float64 compiled here from the frozen headers. Decision for all: the first
sample with no explanation at b = 0 and |noise| <= DELTA. Scoring is score_validation.py, not this file.
usage: python -B run_validation.py OUT [--rehearsal --seeds 430098 430099] [--workers 14]
"""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
V3 = HERE.parent
ROOT = HERE.parents[2]
for sub in ("experiments/v3", "experiments/oracle", "experiments/machine", "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402
import thermal_oracle as O  # noqa: E402
import thermal_v2_env  # noqa: E402
from thermal_machine import ThermalMachine  # noqa: E402

T = V.T
MANIFEST = V3 / "frozen" / "MANIFEST.json"
FREEZE_DOC = V3 / "FREEZE-V1.md"
APPROVAL = re.compile(r"^Status: APPROVED by Can Koç on (\d{4}-\d{2}-\d{2})$", re.M)
CANDIDATES = None
C_BINS = None


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_manifest():
    """Every listed file matches; returns (manifest dict, manifest sha256)."""
    m = json.loads(MANIFEST.read_text())
    bad = [p for p, h in m["files"].items() if sha256(ROOT / p) != h]
    if bad:
        raise SystemExit(f"frozen manifest mismatch: {bad}")
    return m, sha256(MANIFEST)


def check_approval(manifest_sha):
    doc = FREEZE_DOC.read_text()
    if f"Manifest sha256: {manifest_sha}" not in doc:
        raise SystemExit("FREEZE-V1.md does not quote this manifest's sha256")
    hit = APPROVAL.search(doc)
    if not hit:
        raise SystemExit("FREEZE-V1.md is not approved: validation data must not be generated")
    return hit.group(0)


def tasks(m, seeds):
    out = []
    for s in seeds:
        for c in m["cells"]:
            for arm in T.ARMS:
                for al, nl in m["laws_all_cells"]:
                    out.append((s, c, arm, al, nl))
        for arm in T.ARMS:
            for al, nl in m["laws_healthy_extra"]:
                out.append((s, "healthy", arm, al, nl))
    return out


def build_c(m, out):
    """Compile harness + v3_state for each frozen header; returns {tag: binary path} and build info."""
    cdir = out / "c_build"
    cdir.mkdir()
    cc = os.environ.get("CC", "cc")
    flags = ["-O2", "-std=c99", "-ffp-contract=off", "-fno-fast-math"]
    bins, info = {}, {"cc": subprocess.check_output([cc, "--version"], text=True).splitlines()[0], "flags": flags}
    for tag, rel in m["c_headers"].items():
        hdr = ROOT / rel
        exe = cdir / f"v3_{tag}"
        cmd = [cc, *flags, *(["-DV3_FLOAT"] if tag.endswith("_float") else []), f'-DV3_TABLES="{hdr}"',
               f"-I{V3 / 'c'}", "-o", str(exe), str(V3 / "c" / "harness.c"), str(V3 / "c" / "v3_state.c"), "-lm"]
        subprocess.run(cmd, check=True)
        bins[tag] = str(exe)
        info[tag] = {"header": rel, "binary_sha256": sha256(exe), "cmd": cmd}
    return bins, info


def _init(m, bins):
    global CANDIDATES, C_BINS
    CANDIDATES = {k: V.load_frozen(ROOT / c["file"], c["sha256"]) for k, c in m["candidates"].items()}
    C_BINS = bins


def v2_first(y, P):
    mach = ThermalMachine()
    for k, (a, b) in enumerate(zip(y, P)):
        if mach.observe(a, b):
            return k
    return None


def c_first(binary, y, P):
    text = "".join(f"{a!r} {b!r}\n" for a, b in zip(y, P))
    out = subprocess.run([binary], input=text, capture_output=True, text=True, check=True).stdout
    first = int(out.split()[0].split("=")[1])
    return None if first < 0 else first


def job(args):
    seed, cell_name, arm, al, nl, out = args
    cell = next(c for c in T.CELLS if c.name == cell_name)
    r = S.run(seed, cell, arm, al, nl)
    t0 = time.monotonic()
    t_star, status = O.first_inconsistent(
        r["z"], attempt_dir=Path(out) / "solver_attempts" / f"{cell_name}-{seed}-{arm}-{al}-{nl}")
    row = {"seed": seed, "cell": cell_name, "arm": arm, "ambient": al, "noise": nl, "t_f": r["t_f"],
           "oracle": {"t_star": t_star, "status": status, "seconds": round(time.monotonic() - t0, 2)},
           "v2": v2_first(r["y"], r["P"]),
           "candidates": {k: V.first_inconsistent(tp, r["y"], r["P"]) for k, tp in CANDIDATES.items()},
           "c": {tag: c_first(b, r["y"], r["P"]) for tag, b in C_BINS.items()}}
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--rehearsal", action="store_true", help="DEV seeds only; validation stays locked")
    ap.add_argument("--seeds", type=int, nargs=2)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    env = thermal_v2_env.check()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
    m, manifest_sha = check_manifest()
    if a.rehearsal:
        lo, hi = a.seeds or (430098, 430099)
        if not (S.DEV[0] <= lo <= hi <= S.DEV[-1]):
            raise SystemExit("a rehearsal uses DEV seeds only")
        approval = None
    else:
        if dirty:
            raise SystemExit("the working tree has tracked changes: commit first")
        approval = check_approval(manifest_sha)
        lo, hi = m["validation_block"]
        if a.seeds and tuple(a.seeds) != (lo, hi):
            raise SystemExit(f"validation seeds are fixed by the manifest: {lo}-{hi}")
        S.unlock_validation(manifest_sha)
    a.out.mkdir(parents=True, exist_ok=False)
    bins, c_info = build_c(m, a.out)
    meta = {"mode": "rehearsal" if a.rehearsal else "validation", "git_head": head, "git_dirty_tracked": bool(dirty),
            "env": env, "manifest_sha256": manifest_sha, "freeze_doc_sha256": sha256(FREEZE_DOC) if FREEZE_DOC.exists() else None,
            "approval": approval, "seeds": [lo, hi], "c_build": c_info, "host": platform.node(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    todo = [(*t, str(a.out)) for t in tasks(m, range(lo, hi + 1))]
    t0 = time.monotonic()
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(m, bins)) as pool, \
            (a.out / "rows.jsonl").open("w") as f:
        for row in pool.map(job, todo, chunksize=1):
            f.write(json.dumps(row) + "\n")
            f.flush()
    meta.update({"runs": len(todo), "seconds": round(time.monotonic() - t0, 1),
                 "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "rows_sha256": sha256(a.out / "rows.jsonl")})
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps({"runs": len(todo), "seconds": meta["seconds"], "rows_sha256": meta["rows_sha256"]}))


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()
