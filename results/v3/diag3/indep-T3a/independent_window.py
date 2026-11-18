
"""Independent DIAG-3 finite-window LP, and an arrival-redundancy ablation."""
import argparse
import functools
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np
from scipy.optimize import OptimizeWarning, linprog
from scipy.sparse import coo_matrix

ROOT = Path("/home/x6e3/Research/sdts-v3-codex")
CLAUDE = Path("/home/x6e3/Research/sdts-runs/v3-diag3/run1-c16f7be")
for module_dir in ("env", "experiments/v3", "experiments/oracle"):
    sys.path.insert(0, str(ROOT / module_dir))
import dev_scenarios as DEV
import thermal_oracle as O
import thermal_v2_env as ENV

T = O.T
W, BLOCK, PAD = 256, 16, 1e-6
LOW, HIGH = T.TA_LO - O.SHIFT, T.TA_HI - O.SHIFT
M = np.array([[O.A11, O.A12, 0.0], [O.A21, O.A22, O.B2]])
E2 = np.array([0.0, 1.0, 0.0])
TOL = 1e-6
RUNS = (
    (430007, "drift_0.002", "rw", 673),
    (430027, "drift_0.002", "rw", 579),
    (430000, "drift_0.001", "ramp", 849),
    (430010, "drift_0.0005", "ramp", 695),
    (430019, "drift_0.001", "ramp", 393),
)
warnings.filterwarnings("ignore", category=OptimizeWarning, message="Unrecognized options detected.*")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_template():
    path = ROOT / "experiments/v3/frozen/cyl16p.json"
    raw = json.loads(path.read_text())
    directions = np.array([[float.fromhex(x) for x in d] for d in raw["D"]])
    caps = np.array([float.fromhex(x) for x in raw["cap_inv"]])
    caps[raw["ip"]] = np.minimum(caps[raw["ip"]], HIGH)
    caps[raw["im"]] = np.minimum(caps[raw["im"]], -LOW)
    assert directions.shape == (42, 3)
    return directions, caps, sha256(path)


def sparse(rows, n_cols):
    triplets = [(i, j, value) for i, row in enumerate(rows) for j, value in row if value]
    r, c, values = zip(*triplets) if triplets else ([], [], [])
    return coo_matrix((values, (r, c)), shape=(len(rows), n_cols)).tocsr()


@functools.lru_cache(maxsize=32)
def structure(size, initial):
    equality, inequality = [], []
    if initial:
        equality.extend((((0, 1.0), (2, -1.0)), ((1, 1.0), (2, -1.0))))
    for j in range(1, size):
        src, dst = 3 * (j - 1), 3 * j
        for r in range(2):
            equality.append([(dst + r, 1.0)] + [(src + col, -a) for col, a in enumerate(M[r])])
        inequality.extend((((dst + 2, 1.0), (src + 2, -1.0)), ((dst + 2, -1.0), (src + 2, 1.0))))
    if not initial:
        inequality.extend([list(enumerate(d)) for d in DIRECTIONS])
    ncols = size * 3
    return sparse(equality, ncols), sparse(inequality, ncols)


def slab(z):
    # Enclose exact sums/subtractions of the stored float constants in the LP.
    return math.nextafter(z - T.DELTA, -math.inf), math.nextafter(z + T.DELTA, math.inf)


def inner_slab(z):
    return math.nextafter(z - T.DELTA, math.inf), math.nextafter(z + T.DELTA, -math.inf)


class Window:
    def __init__(self):
        self.tau = 0
        self.supports = None
        self.measurements = {}
        self.objectives = 0
        self.retries = 0
        self.max_variables = 0
        self.max_rows = 0

    def problem(self, end):
        samples = end - self.tau + 1
        ncols = 3 * samples
        eq, ub = structure(samples, self.supports is None)
        lower, upper = np.full(ncols, LOW), np.full(ncols, HIGH)
        for sample, z in self.measurements.items():
            if sample < self.tau or (self.supports is not None and sample == self.tau):
                continue
            i = 3 * (sample - self.tau) + 1
            lo, hi = slab(z)
            lower[i], upper[i] = max(LOW, lo), min(HIGH, hi)
        if np.any(lower > upper):
            raise RuntimeError(f"Infeasible LP bounds prior to sample {end}")
        rhs = np.full(2 * (samples - 1), T.RHO_A)
        if self.supports is not None:
            rhs = np.concatenate((rhs, self.supports))
        bounds = list(zip(lower.tolist(), upper.tolist(), strict=True))
        self.max_variables = max(self.max_variables, ncols)
        self.max_rows = max(self.max_rows, eq.shape[0] + ub.shape[0])
        return eq, np.zeros(eq.shape[0]), ub, rhs, bounds

    def maximize(self, problem, end_state, direction):
        eq, beq, ub, rhs, bounds = problem
        c = np.zeros(len(bounds))
        off = 3 * (end_state - self.tau)
        c[off:off + 3] = -direction
        caps = np.full(len(bounds), max(abs(LOW), abs(HIGH)))
        self.objectives += 1
        for index, (method, presolve) in enumerate((("highs-ds", False), ("highs-ipm", False), ("highs-ds", True))):
            sol = linprog(c, A_ub=ub, b_ub=rhs, A_eq=eq, b_eq=beq,
                          bounds=bounds, method=method, options={"presolve": presolve, "threads": 1})
            if sol.status == 0:
                dual = O._dual_bound(sol, c, ub, rhs, eq, beq, bounds, caps)
                return -float(sol.fun), (-dual if dual is not None else None), {
                    "method": method, "presolve": presolve, "status": int(sol.status), "fallback_index": index,
                }
            if sol.status == 2:
                raise RuntimeError(f"Solver infeasible on an admitted window, states {self.tau} through {end_state}")
            self.retries += 1
        raise RuntimeError(f"Solver failed: status {sol.status}: {sol.message}")

    def predicted(self, t):
        problem = self.problem(t)
        hi, hi_cert, up = self.maximize(problem, t, E2)
        minus_lo, minus_lo_cert, dn = self.maximize(problem, t, -E2)
        return [-minus_lo, hi], [-minus_lo_cert if minus_lo_cert is not None else None, hi_cert], [dn, up]

    def fold(self, t):
        problem = self.problem(t)
        target = self.tau + BLOCK
        results = [self.maximize(problem, target, d) for d in DIRECTIONS]
        raw = np.array([x[0] for x in results])
        raw_padded = raw + PAD
        written = np.minimum(raw_padded, CLAMPS)
        proof = []
        for i, (estimate, bound, solve) in enumerate(results):
            capped_upper = min(bound, CLAMPS[i]) if bound is not None else None
            proof.append({
                "direction": i, "solver": solve, "raw_support_c": estimate,
                "dual_upper_before_clamp_c": bound, "written_before_clamp_c": float(raw_padded[i]),
                "written_support_c": float(written[i]), "valid_clamp_c": float(CLAMPS[i]),
                "dual_upper_with_same_clamp_c": capped_upper,
                "shortfall_before_clamp_c": max(0.0, bound - raw_padded[i]) if bound is not None else None,
                "shortfall_after_clamp_c": max(0.0, capped_upper - written[i]) if capped_upper is not None else None,
            })
        self.supports, self.tau = written, target
        self.measurements = {j: z for j, z in self.measurements.items() if j > target}
        return {"sample": t, "base_sample": target, "supports": proof}


def signed_margin(predicted, z):
    lo, hi = predicted
    return min(z + T.DELTA - lo, hi - (z - T.DELTA))


def certificate(sample, z, estimated, outer, statuses):
    slab_lo, slab_hi = slab(z)
    certified = None not in outer
    margin_upper = math.nextafter(min(slab_hi - outer[0], outer[1] - slab_lo), math.inf) if certified else None
    return {"sample": sample, "estimated_as_range_shifted_c": estimated, "outer_as_range_shifted_c": outer,
            "outward_slab_shifted_c": [slab_lo, slab_hi], "margin_upper_c": margin_upper,
            "separation_certified": certified and margin_upper < 0, "solver": statuses}


def run_window(z, drop_redundant):
    window = Window()
    diagnostic_kept = set()
    entries, folds = [], []
    det = det_cert = None
    for t, y in enumerate(z):
        started, prior_lp = time.perf_counter(), window.objectives
        if t == 0:
            estimate, outer, status = [LOW, HIGH], [LOW, HIGH], []
        else:
            estimate, outer, status = window.predicted(t)
        m = signed_margin(estimate, y)
        yl, yh = inner_slab(y)
        layout_redundant = None not in outer and yl <= outer[0] and outer[1] <= yh
        numeric_redundant = y - T.DELTA <= estimate[0] and estimate[1] <= y + T.DELTA
        fold = None
        if m < 0:
            det = t
            det_cert = certificate(t, y, estimate, outer, status)
            category = "alarm"
        else:
            category = "redundant" if layout_redundant else "possibly_informative"
            if not layout_redundant:
                diagnostic_kept.add(t)
            if not drop_redundant or not layout_redundant:
                window.measurements[t] = y
        peak_kept = len(diagnostic_kept)
        lp_measurements_before_fold = len(window.measurements)
        if det is None and t - window.tau > W + BLOCK:
            fold = window.fold(t)
            diagnostic_kept = {j for j in diagnostic_kept if j > window.tau}
            folds.append(fold)
        entries.append({
            "t": t, "margin_c": m, "category": category, "redundant_by_numerical_range": numeric_redundant,
            "n_nonredundant_before_fold": peak_kept, "n_nonredundant_after_fold": len(diagnostic_kept),
            "n_measurements_in_window_before_fold": lp_measurements_before_fold,
            "lp_objectives": window.objectives - prior_lp, "fold": fold is not None,
            "seconds": time.perf_counter() - started,
        })
        if det is not None:
            break
    all_checks = [item for fold in folds for item in fold["supports"]]
    missing = [item for item in all_checks if item["dual_upper_before_clamp_c"] is None]
    timings = {}
    for name, is_fold in (("fold_samples", True), ("ordinary_samples", False)):
        selected = [r for r in entries if r["fold"] == is_fold and r["t"] != 0]
        seconds = [r["seconds"] for r in selected]
        timings[name] = {"count": len(seconds), "peak_lp_objectives": max((r["lp_objectives"] for r in selected), default=0),
                         "peak_seconds": max(seconds, default=None),
                         "median_seconds": float(np.median(seconds)) if seconds else None}
    return {
        "detect": det, "alarm_certificate": det_cert, "total_lp_objectives": window.objectives,
        "solver_fallback_attempts": window.retries, "max_variables": window.max_variables, "max_matrix_rows": window.max_rows,
        "fold_count": len(folds), "fold_support_count": len(all_checks), "missing_dual_bounds": len(missing),
        "peak_written_support_shortfall_c": max((r["shortfall_after_clamp_c"] or 0.0 for r in all_checks), default=0.0),
        "peak_unclamped_padded_support_shortfall_c": max((r["shortfall_before_clamp_c"] or 0.0 for r in all_checks), default=0.0),
        "peak_nonredundant_measurements": max(r["n_nonredundant_before_fold"] for r in entries),
        "redundant_at_arrival": sum(r["category"] == "redundant" for r in entries),
        "numerical_only_redundant": sum(r["category"] == "possibly_informative" and r["redundant_by_numerical_range"] for r in entries),
        "timings": timings, "folds": folds, "steps": entries,
    }


def difference_summary(ref, new):
    a = {r["t"]: r["margin_c"] for r in ref["steps"]}
    b = {r["t"]: r["margin_c"] for r in new["steps"]}
    deviations = [{"t": t, "all_measurements_margin_c": a[t], "eviction_margin_c": b[t], "difference_c": b[t] - a[t]}
                  for t in sorted(a.keys() & b.keys()) if abs(b[t] - a[t]) > TOL]
    return {"full_window_detect": ref["detect"], "eviction_detect": new["detect"],
            "common_samples": len(a.keys() & b.keys()),
            "largest_abs_margin_delta_c": max((abs(b[t] - a[t]) for t in a.keys() & b.keys()), default=None),
            "margin_deviations_over_1e_6": deviations}


def save_json(path, record):
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("T3a", "T3c"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    env = ENV.check()
    records = []
    for seed, cell, ambient, t_star in RUNS:
        definition = next(c for c in T.CELLS if c.name == cell)
        generated = DEV.run(seed, definition, "E0", ambient, "uniform")
        z = [y - O.SHIFT for y in generated["z"]]
        output = run_window(z, drop_redundant=(args.mode == "T3c"))
        slug = f"{seed}-{cell}-{ambient}"
        record = {"task": args.mode, "root_commit": commit, "frozen_direction_input_sha256": TEMPLATE_SHA,
                  "environment": env, "run": {"seed": seed, "cell": cell, "ambient": ambient, "arm": "E0",
                                               "noise": "uniform", "t_star": t_star},
                  "W": W, "block": BLOCK, "fold_pad_c": PAD, "tolerance_c": TOL,
                  "bound_scope": "stored plant constants, outward measurement RHS, finite variable caps; existing reachable-set clamps",
                  "dropped_measurements": "redundant by outer predicted range at arrival" if args.mode == "T3c" else "none",
                  **output}
        if args.mode == "T3a":
            cp = CLAUDE / f"w-{slug}-S256.json"
            ref = json.loads(cp.read_text())
            margin = next((r["margin_c"] for r in output["steps"] if r["t"] == t_star), None)
            delta = margin - ref["margin_at_t_star_mC"] * 1e-3 if margin is not None else None
            record["claude_comparison"] = {"file": str(cp), "sha256": sha256(cp),
                 "detect": ref["detect"], "same_detection_time": output["detect"] == ref["detect"] == t_star,
                 "margin_at_t_star_c": margin, "claude_margin_at_t_star_c": ref["margin_at_t_star_mC"] * 1e-3,
                 "margin_difference_c": delta, "margin_difference_exceeds_threshold": delta is None or abs(delta) > TOL}
        else:
            original = args.output.parent / "T3a" / f"{slug}.json"
            record["full_window_comparison"] = {"file": str(original), "sha256": sha256(original),
                **difference_summary(json.loads(original.read_text()), record)}
        save_json(args.output / f"{slug}.json", record)
        summary = {k: v for k, v in record.items() if k not in ("steps", "folds", "environment")}
        if args.mode == "T3c":
            diffs = summary["full_window_comparison"].pop("margin_deviations_over_1e_6")
            summary["full_window_comparison"]["deviation_count_over_1e_6"] = len(diffs)
            summary["first_deviation"] = diffs[0] if diffs else None
        records.append(summary)
        print(f"{args.mode} seed={seed} detect={output['detect']} folds={len(output['folds'])} "
              f"shortfall={output['peak_written_support_shortfall_c']:.3g} peak_kept={output['peak_nonredundant_measurements']}",
              flush=True)
    save_json(args.output / "summary.json", {"task": args.mode, "root_commit": commit, "runs": records})


if __name__ == "__main__":
    DIRECTIONS, CLAMPS, TEMPLATE_SHA = read_template()
    main()

