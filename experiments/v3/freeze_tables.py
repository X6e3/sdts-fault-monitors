"""Build the two frozen v3 candidates (pruned basis tables) from DEV selection runs only.

  inv4p   family inv N=4 (16 directions) + reachable-set clamps; bases kept: every basis that was the argmin
          at least once on the selection set DEV 430050-430069 (10 cells x 2 arms x 2 ambient laws, uniform
          noise: 800 runs), plus the Theorem-3 bases.
  cyl16p  family cyl N=4 L=16 (42 directions) + clamps; same rule on the first 120 runs of that list
          (seeds 430050-430052), as evaluated on DEV in RESULTS.md.

The output files are the candidates. Validation loads them by sha256 and never rebuilds them.
usage: python -B freeze_tables.py OUT_DIR [--workers 14]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402

T = V.T
CELL = {c.name: c for c in T.CELLS}
SEL_SEEDS = range(430050, 430070)
SEL_CELLS = ("healthy", "jump_0.2", "jump_0.5", "drift_0.0005", "drift_0.001", "drift_0.002", "drift_0.005",
             "noise_x2", "stuck", "gain_0.01")
CANDIDATES = {
    "inv4p": {"kind": "inv", "N": 4, "L": 0, "selection_runs": 800},
    "cyl16p": {"kind": "cyl", "N": 4, "L": 16, "selection_runs": 120},
}


def selection_keys():
    """The selection runs in a fixed order: seed, cell, arm, ambient law (noise uniform)."""
    return [(s, c, arm, al) for s in SEL_SEEDS for c in SEL_CELLS for arm in T.ARMS for al in ("rw", "ramp")]


FULL = None


def _init(kind, N, L):
    global FULL
    FULL = V.Template(V.directions(kind, N=N, L=L), invariant=True)


def _usage(key):
    s, c, arm, al = key
    r = S.run(s, CELL[c], arm, al, "uniform")
    return V.usage(FULL, [(r["y"], r["P"])])


def build(name, spec, workers):
    keys = selection_keys()[: spec["selection_runs"]]
    _init(spec["kind"], spec["N"], spec["L"])
    full = FULL
    with ProcessPoolExecutor(workers, initializer=_init, initargs=(spec["kind"], spec["N"], spec["L"])) as pool:
        parts = list(pool.map(_usage, keys, chunksize=2))
    counts = [sum(p[i] for p in parts) for i in range(len(parts[0]))]
    tp = V.pruned(full, counts)
    missing = V.dominance_bases_present(tp)
    if missing:
        raise SystemExit(f"{name}: Theorem-3 bases missing: {missing}")
    meta = {"name": name, "family": {k: spec[k] for k in ("kind", "N", "L")}, "invariant": True,
            "selection": {"seeds": [keys[0][0], keys[-1][0]], "runs": len(keys), "cells": list(SEL_CELLS),
                          "arms": list(T.ARMS), "ambient_laws": ["rw", "ramp"], "noise_law": "uniform",
                          "rule": "keep every basis that was the argmin at least once, plus the Theorem-3 bases"},
            "full_table_entries": int(full.table_entries), "state_numbers": int(tp.n),
            "table_entries": int(tp.table_entries)}
    return tp, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    root = HERE.parents[1]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=root).returncode)
    import numpy, scipy
    summary = {"built_at_git_head": head, "git_dirty_tracked": dirty, "numpy": numpy.__version__,
               "scipy": scipy.__version__, "python": sys.version.split()[0], "platform": sys.platform,
               "candidates": {}}
    for name, spec in CANDIDATES.items():
        tp, meta = build(name, spec, a.workers)
        path = a.out / f"{name}.json"
        V.write_frozen(tp, meta, path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        summary["candidates"][name] = {**meta, "file": path.name, "sha256": sha}
        print(name, json.dumps({"entries": tp.table_entries, "full": meta["full_table_entries"], "sha256": sha}))
    (a.out / "build.json").write_text(json.dumps(summary, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
