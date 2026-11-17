"""Check CAL twin score agreement and causality with no calibrated threshold."""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from thermal_baselines import T, cusum_score, dmreda_score, verify_reference
from thermal_twins import pairs

SMOKE_SEEDS = (410000, 410197)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--cusum-allowance", type=float, required=True)
    args = parser.parse_args()
    digest = verify_reference()
    methods = {"DMREDA": dmreda_score, "CUSUM": lambda y: cusum_score(y, allowance=args.cusum_allowance)}
    twins = []
    for seed, case, arm, draw, b, (y_a, _, y_b, _) in pairs(T):
        if seed not in SMOKE_SEEDS:
            continue
        for name, score in methods.items():
            a, t = score(y_a), score(y_b)
            twins.append({"seed": seed, "case": case, "arm": arm, "draw": draw, "offset": b, "method": name,
                          "max_abs_score_difference": float(np.max(np.abs(a.values - t.values))),
                          "evaluate_from": a.evaluate_from})
    y = T.run(SMOKE_SEEDS[-1], T.CELLS[0], "E1")["y"]
    n = 600
    causality = {name: float(np.max(np.abs(score(y).values[:n] - score(y[:n]).values)))
                 for name, score in methods.items()}
    args.out.mkdir(parents=True, exist_ok=False)
    with (args.out / "P1_scores.jsonl").open("w") as stream:
        for row in twins:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    out = {"git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
           "dmreda_reference_sha256": digest, "seeds": SMOKE_SEEDS, "cusum_smoke_allowance": args.cusum_allowance,
           "calibrated_thresholds": None, "twin_pairs_per_method": len(twins) // len(methods),
           "prefix_causality_max_abs_difference": causality,
           "twin_max_abs_difference": {name: max(r["max_abs_score_difference"] for r in twins if r["method"] == name)
                                       for name in methods}}
    (args.out / "summary.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
