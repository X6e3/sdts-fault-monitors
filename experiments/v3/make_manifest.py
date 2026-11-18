"""Write frozen/MANIFEST.json: what freeze 1 fixes (files by sha256, candidates and targets, data block, laws).
run_validation.py refuses to run unless every file listed here matches and FREEZE-V1.md quotes this file's
sha256 with an approval line. Changing anything listed means a new freeze, not an edit of this one.
usage: python -B make_manifest.py
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FILES = [
    "experiments/v3/template_state.py", "experiments/v3/dev_scenarios.py", "experiments/v3/run_validation.py",
    "experiments/v3/score_validation.py", "experiments/v3/codegen_c.py", "experiments/v3/freeze_tables.py",
    "experiments/v3/c/v3_state.c", "experiments/v3/c/v3_state.h", "experiments/v3/c/harness.c",
    "experiments/v3/frozen/inv4p.json", "experiments/v3/frozen/cyl16p.json", "experiments/v3/frozen/build.json",
    "experiments/v3/frozen/c/tables_inv4p_float.h", "experiments/v3/frozen/c/tables_inv4p_double.h",
    "experiments/v3/frozen/c/tables_cyl16p_float.h", "experiments/v3/frozen/c/tables_cyl16p_double.h",
    "experiments/generators/thermal.py", "experiments/oracle/thermal_oracle.py",
    "experiments/machine/thermal_machine.py", "env/thermal_v2_env.py", "env/requirements-thermal-v2.txt",
]


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main():
    m = {
        "freeze": "v3-freeze-1",
        "validation_block": [440000, 440199],
        "reserved_after_this_block": [440200, 440999],
        "cells": ["healthy", "jump_0.2", "jump_0.5", "drift_0.0005", "drift_0.001", "drift_0.002", "drift_0.005",
                  "drift_0.02", "noise_x2", "stuck", "gain_0.01"],
        "arms": ["E0", "E1"],
        "laws_all_cells": [["rw", "uniform"], ["ramp", "uniform"]],
        "laws_healthy_extra": [["rw", "edge"], ["ramp", "edge"]],
        "record_length": 3600,
        "uncertified_limit_fraction_of_fault_runs": 0.01,
        "candidates": {
            "inv4p": {"file": "experiments/v3/frozen/inv4p.json", "sha256": sha("experiments/v3/frozen/inv4p.json"),
                      "target_paired_lag_reduction": 0.10},
            "cyl16p": {"file": "experiments/v3/frozen/cyl16p.json", "sha256": sha("experiments/v3/frozen/cyl16p.json"),
                       "target_paired_lag_reduction": 0.25},
        },
        "c_headers": {f"{c}_{r}": f"experiments/v3/frozen/c/tables_{c}_{r}.h"
                      for c in ("inv4p", "cyl16p") for r in ("float", "double")},
        "files": {rel: sha(rel) for rel in FILES},
    }
    path = HERE / "frozen" / "MANIFEST.json"
    path.write_text(json.dumps(m, indent=1) + "\n")
    print(path, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
