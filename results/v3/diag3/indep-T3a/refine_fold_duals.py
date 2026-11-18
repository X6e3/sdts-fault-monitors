
"""Check missing fold duals without rerunning the online trajectory."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

import independent_window as W


def refine(window, problem, target, row):
    eq, beq, ub, rhs, bounds = problem
    i = row["direction"]
    c = np.zeros(len(bounds))
    off = 3 * (target - window.tau)
    c[off:off + 3] = -W.DIRECTIONS[i]
    radii = np.full(len(bounds), max(abs(W.LOW), abs(W.HIGH)))
    attempts = []
    best = None
    for method, use_presolve, tol in (("highs-ipm", False, 1e-9), ("highs-ds", False, 1e-9),
                                      ("highs-ipm", True, 1e-9), ("highs-ds", True, 1e-10)):
        options = {"presolve": use_presolve, "threads": 1, "primal_feasibility_tolerance": tol,
                   "dual_feasibility_tolerance": tol, "ipm_optimality_tolerance": 1e-10}
        answer = linprog(c, A_ub=ub, b_ub=rhs, A_eq=eq, b_eq=beq, bounds=bounds, method=method, options=options)
        bound = None
        if answer.status == 0:
            signed = W.O._dual_bound(answer, c, ub, rhs, eq, beq, bounds, radii)
            bound = -signed if signed is not None else None
        attempts.append({"method": method, "presolve": use_presolve, "tolerance": tol, "status": int(answer.status),
                         "upper_c": bound})
        if bound is not None:
            best = bound if best is None else min(best, bound)
            if min(best, row["valid_clamp_c"]) <= row["written_support_c"]:
                break
    row["dual_refinement"] = attempts
    if best is not None:
        bound = min(best, row["valid_clamp_c"])
        row.update(dual_upper_before_clamp_c=best, dual_upper_with_same_clamp_c=bound,
                   shortfall_before_clamp_c=max(0, best - row["written_before_clamp_c"]),
                   shortfall_after_clamp_c=max(0, bound - row["written_support_c"]))


def restore(out):
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text())
    for entry in summary["runs"]:
        if not entry["missing_dual_bounds"]:
            continue
        run = entry["run"]
        path = out / f"{run['seed']}-{run['cell']}-{run['ambient']}.json"
        record = json.loads(path.read_text())
        obs = W.DEV.run(run["seed"], next(c for c in W.T.CELLS if c.name == run["cell"]),
                        run["arm"], run["ambient"], run["noise"])["z"]
        kept = {r["t"] for r in record["steps"]
                if r["category"] != "alarm" and (record["task"] == "T3a" or r["category"] != "redundant")}
        window = W.Window()
        for fold in record["folds"]:
            problem = None
            for row in fold["supports"]:
                if row["dual_upper_before_clamp_c"] is not None:
                    continue
                if problem is None:
                    window.measurements = {j: obs[j] - W.O.SHIFT for j in range(window.tau, fold["sample"] + 1) if j in kept}
                    problem = window.problem(fold["sample"])
                refine(window, problem, fold["base_sample"], row)
            window.tau = fold["base_sample"]
            window.supports = np.array([row["written_support_c"] for row in fold["supports"]])
        all_bounds = [b for f in record["folds"] for b in f["supports"]]
        for dst in (entry, record):
            dst["missing_dual_bounds"] = sum(b["dual_upper_before_clamp_c"] is None for b in all_bounds)
            dst["peak_written_support_shortfall_c"] = max(b["shortfall_after_clamp_c"] or 0.0 for b in all_bounds)
            dst["peak_unclamped_padded_support_shortfall_c"] = max(b["shortfall_before_clamp_c"] or 0.0 for b in all_bounds)
        W.save_json(path, record)
        print("refined", run["seed"], "missing", entry["missing_dual_bounds"],
              "largest shortfall", entry["peak_written_support_shortfall_c"], flush=True)
    W.save_json(summary_path, summary)


if __name__ == "__main__":
    W.DIRECTIONS, W.CLAMPS, W.TEMPLATE_SHA = W.read_template()
    restore(Path(sys.argv[1]))

