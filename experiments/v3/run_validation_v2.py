"""v3 freeze 2: independent validation of the compressed window F (FREEZE-V2.md): oracle vs v2 vs F.

Refuses to touch validation seeds unless:
  - the working tree is clean (tracked files) and the v2 environment lock holds;
  - frozen/MANIFEST-V2.json matches every file it lists (code and the direction table);
  - FREEZE-V2.md quotes that manifest's sha256 and carries the approval line written after Can's review;
  - the seeds are exactly the manifest's validation block and OUT does not exist.
--rehearsal runs the identical pipeline on DEV seeds only (no approval needed, validation stays locked).

Per run: the certified oracle t*, the v2 machine, and F: the compressed window of DIAG-3 amendment 6
(diag/diag3_cw_dev.online, variant F) with the manifest's W and K, float64, online from k = 0. Decision for all:
the first sample with no explanation at b = 0 and |noise| <= DELTA; F also certifies each alarm. Scoring is
score_validation_v2.py, not this file.
usage: python -B run_validation_v2.py OUT [--rehearsal --seeds 430096 430097] [--workers 14]
"""
import argparse
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
for sub in ("experiments/v3", "experiments/v3/diag", "experiments/oracle", "experiments/machine",
            "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402
import thermal_oracle as O  # noqa: E402
import thermal_v2_env  # noqa: E402
import run_validation as RV1  # noqa: E402   (sha256, tasks, v2_first; freeze 1's runner, unchanged)
import diag1 as G  # noqa: E402
import diag3_cw_dev as CWD  # noqa: E402

T = V.T
MANIFEST = V3 / "frozen" / "MANIFEST-V2.json"
FREEZE_DOC = V3 / "FREEZE-V2.md"
APPROVAL = re.compile(r"^Status: APPROVED by Can Koç on (\d{4}-\d{2}-\d{2})$", re.M)
CAND = None
F_KEYS = ("detect", "alarm_certificate", "margin_at_detect_mC", "evictions", "max_kept", "max_nodes", "max_vars",
          "max_rows", "n_lp", "n_retry", "folds_raised_to_dual_bound", "largest_raise_C", "steps", "step_ms",
          "fold_step_ms", "seconds")


def check_manifest():
    m = json.loads(MANIFEST.read_text())
    bad = [p for p, h in m["files"].items() if RV1.sha256(ROOT / p) != h]
    if bad:
        raise SystemExit(f"frozen manifest mismatch: {bad}")
    return m, RV1.sha256(MANIFEST)


def check_approval(manifest_sha):
    if not FREEZE_DOC.exists():
        raise SystemExit("FREEZE-V2.md does not exist: validation data must not be generated")
    doc = FREEZE_DOC.read_text()
    if f"Manifest sha256: {manifest_sha}" not in doc:
        raise SystemExit("FREEZE-V2.md does not quote this manifest's sha256")
    hit = APPROVAL.search(doc)
    if not hit:
        raise SystemExit("FREEZE-V2.md is not approved: validation data must not be generated")
    return hit.group(0)


def _init(m, unlock_sha):
    global CAND
    if unlock_sha is not None:                # workers may be spawned, not forked: unlock them explicitly
        S.unlock_validation(unlock_sha)
    c = m["candidate"]
    CAND = (V.load_frozen(ROOT / c["directions_file"], c["directions_sha256"]), c["W"], c["K"], c["variant"])


def job(args):
    seed, cell_name, arm, al, nl, out = args
    cell = next(c for c in T.CELLS if c.name == cell_name)
    r = S.run(seed, cell, arm, al, nl)
    t0 = time.monotonic()
    t_star, status = O.first_inconsistent(
        r["z"], attempt_dir=Path(out) / "solver_attempts" / f"{cell_name}-{seed}-{arm}-{al}-{nl}")
    oracle_s = round(time.monotonic() - t0, 2)
    tp, W, K, var = CAND
    f = CWD.online(var, G.zs_of(r), W, K, t_star, tp=tp)
    return {"seed": seed, "cell": cell_name, "arm": arm, "ambient": al, "noise": nl, "t_f": r["t_f"],
            "oracle": {"t_star": t_star, "status": status, "seconds": oracle_s},
            "v2": RV1.v2_first(r["y"], r["P"]), "F": {k: f[k] for k in F_KEYS}}


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
        lo, hi = a.seeds or (430096, 430097)
        if not (S.DEV[0] <= lo <= hi <= S.DEV[-1]):
            raise SystemExit("a rehearsal uses DEV seeds only")
        approval, unlock = None, None
    else:
        if dirty:
            raise SystemExit("the working tree has tracked changes: commit first")
        approval = check_approval(manifest_sha)
        lo, hi = m["validation_block"]
        if a.seeds and tuple(a.seeds) != (lo, hi):
            raise SystemExit(f"validation seeds are fixed by the manifest: {lo}-{hi}")
        S.unlock_validation(manifest_sha)
        unlock = manifest_sha
    a.out.mkdir(parents=True, exist_ok=False)
    meta = {"mode": "rehearsal" if a.rehearsal else "validation", "git_head": head, "git_dirty_tracked": bool(dirty),
            "env": env, "manifest_sha256": manifest_sha,
            "freeze_doc_sha256": RV1.sha256(FREEZE_DOC) if FREEZE_DOC.exists() else None,
            "approval": approval, "seeds": [lo, hi], "candidate": m["candidate"], "host": platform.node(),
            "machine": platform.machine(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    todo = [(*t, str(a.out)) for t in RV1.tasks(m, range(lo, hi + 1))]
    t0 = time.monotonic()
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(m, unlock)) as pool, \
            (a.out / "rows.jsonl").open("w") as f:
        for row in pool.map(job, todo, chunksize=1):
            f.write(json.dumps(row) + "\n")
            f.flush()
    meta.update({"runs": len(todo), "seconds": round(time.monotonic() - t0, 1),
                 "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "rows_sha256": RV1.sha256(a.out / "rows.jsonl")})
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps({"runs": len(todo), "seconds": meta["seconds"], "rows_sha256": meta["rows_sha256"]}))


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()
