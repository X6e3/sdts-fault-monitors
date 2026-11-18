
"""Replay from the first fold whose stored supports could not be certified as written."""
import json
import math
import sys
from pathlib import Path

import numpy as np

import independent_window as W
from refine_fold_duals import refine


def safe_fold(window, t):
    problem = window.problem(t)
    target = window.tau + W.BLOCK
    details = []
    written = []
    for i, d in enumerate(W.DIRECTIONS):
        estimate, upper, solver = window.maximize(problem, target, d)
        padded = estimate + W.PAD
        clamp = float(W.CLAMPS[i])
        row = {"direction": i, "raw_support_c": estimate, "written_before_clamp_c": padded,
               "written_support_c": min(padded, clamp), "valid_clamp_c": clamp, "solver": solver,
               "dual_upper_before_clamp_c": upper}
        if upper is None or min(clamp, upper) > row["written_support_c"]:
            refine(window, problem, target, row)
            upper = row["dual_upper_before_clamp_c"]
        folded = clamp if upper is None else min(clamp, max(padded, upper))
        written.append(folded)
        row["safe_written_support_c"] = folded
        row["increment_over_raw_padded_clamped_c"] = folded - row["written_support_c"]
        row["certifying_upper_c"] = clamp if upper is None else min(clamp, upper)
        assert folded >= row["certifying_upper_c"]
        details.append(row)
    window.supports, window.tau = np.array(written), target
    window.measurements = {j: z for j, z in window.measurements.items() if j > target}
    return {"sample": t, "base_sample": target, "supports": details}


def replay(path, out):
    old = json.loads(path.read_text())
    run = old["run"]
    obs = W.DEV.run(run["seed"], next(c for c in W.T.CELLS if c.name == run["cell"]),
                    run["arm"], run["ambient"], run["noise"])["z"]
    z = [y - W.O.SHIFT for y in obs]
    folds = old["folds"]
    first = next(i for i, fold in enumerate(folds) if any(
        r["dual_upper_with_same_clamp_c"] is None or (r["shortfall_after_clamp_c"] or 0) > 0
        for r in fold["supports"]))
    t_start = folds[first]["sample"]
    assert first and old["detect"] == run["t_star"]
    window = W.Window()
    previous = folds[first - 1]
    window.tau = previous["base_sample"]
    window.supports = np.array([r["written_support_c"] for r in previous["supports"]])
    window.measurements = {t: z[t] for t in range(window.tau + 1, t_start + 1)}
    updated_folds = [safe_fold(window, t_start)]
    examined = []
    for t in range(t_start + 1, run["t_star"] + 1):
        estimated, outer, status = window.predicted(t)
        enclosure = W.certificate(t, z[t], estimated, outer, status)
        raw = W.signed_margin(estimated, z[t])
        examined.append({"t": t, "raw_margin_c": raw, "alarm_enclosure": enclosure})
        if enclosure["separation_certified"]:
            break
        if raw < 0:
            raise RuntimeError(f"Numerical separation without certificate at {t}; continuation is ambiguous")
        window.measurements[t] = z[t]
        if t - window.tau > W.W + W.BLOCK:
            updated_folds.append(safe_fold(window, t))
    last = examined[-1]
    result = {"task": "DIAG3-T3a support-certified suffix replay", "run": run, "root_commit": old["root_commit"],
              "reference_file": path.name, "reference_sha256": W.sha256(path),
              "first_unverified_original_fold": t_start, "resume_from_certified_fold": previous["sample"],
              "rule": "keep the original padded support if certified, else raise it to the dual upper bound, bounded by a valid reachable clamp",
              "certified_detect": last["t"] if last["alarm_enclosure"]["separation_certified"] else None,
              "alarm_certificate": last["alarm_enclosure"], "updated_folds": updated_folds,
              "largest_fold_support_increment_c": max(r["increment_over_raw_padded_clamped_c"]
                                                        for f in updated_folds for r in f["supports"]),
              "steps_rechecked": examined}
    W.save_json(out, result)
    print("safe replay", run["seed"], "detection", result["certified_detect"],
          "margin upper", result["alarm_certificate"]["margin_upper_c"], flush=True)


if __name__ == "__main__":
    W.DIRECTIONS, W.CLAMPS, W.TEMPLATE_SHA = W.read_template()
    replay(Path(sys.argv[1]), Path(sys.argv[2]))

