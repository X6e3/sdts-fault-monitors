"""DEV reference values of the frozen candidates under the frozen scoring rules (FREEZE-V1.md section 4).

Reuses the certified oracle t* and the v2 machine of the DEV comparison rows (run_dev.py, DEV 430000-430029,
uniform noise only, no C builds) and runs the frozen candidate files on the same runs. The numbers this writes
are DEV numbers: they show what the frozen rules read on the data the candidates were developed on. They are
not validation and not a prediction of it.
usage: python -B dev_reference.py RUN_DEV_DIR OUT_JSON [--workers 14]
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(HERE.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import score_validation as SV  # noqa: E402
import template_state as V  # noqa: E402

T = V.T
CELL = {c.name: c for c in T.CELLS}
CANDS = None


def _init(manifest):
    global CANDS
    CANDS = {k: V.load_frozen(ROOT / c["file"], c["sha256"]) for k, c in manifest["candidates"].items()}


def _job(r):
    run = S.run(r["seed"], CELL[r["cell"]], r["arm"], r["ambient"], r["noise"])
    return {k: V.first_inconsistent(tp, run["y"], run["P"]) for k, tp in CANDS.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dev_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    manifest = json.loads((HERE / "frozen" / "MANIFEST.json").read_text())
    rows = [json.loads(l) for l in (a.run_dev_dir / "rows.jsonl").read_text().splitlines() if l.strip()]
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(manifest,)) as pool:
        firsts = list(pool.map(_job, rows, chunksize=4))
    vrows = [{k: r[k] for k in ("seed", "cell", "arm", "ambient", "noise", "t_f", "oracle", "v2")} | {"candidates": f}
             for r, f in zip(rows, firsts)]
    s = SV.score(vrows, manifest)
    s["note"] = "DEV reference (430000-430029, run_dev rows); not validation"
    s["source_rows"] = str(a.run_dev_dir / "rows.jsonl")
    a.out.write_text(json.dumps(s, indent=1) + "\n")
    for name, c in s["candidates"].items():
        print(f"{name}: D_paired={c['D_paired']:.4f} D_censored={c['D_censored']:.4f} misses={c['misses']} "
              f"(v2 {s['v2']['misses']}) equal={c['equal_to_oracle']} sound={len(c['soundness_violations'])} "
              f"dom={len(c['dominance_violations'])} boot={c['D_paired_bootstrap95_descriptive']}")
    print(f"events {s['detection_events']} uncertified {s['uncertified']} admissible {s['admissible_runs']}")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
