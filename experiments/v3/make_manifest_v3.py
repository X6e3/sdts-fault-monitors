"""Write frozen/MANIFEST-V3.json: what freeze 3 fixes (files by sha256, the candidate and its target, the data block,
the laws). run_validation_v3.py refuses to run unless every file listed here matches and FREEZE-V3.md quotes this
file's sha256 with an approval line. Changing anything listed means a new freeze, not an edit of this one.
usage: python -B make_manifest_v3.py
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FILES = [
    "experiments/v3/run_validation_v3.py", "experiments/v3/score_validation_v3.py",
    "experiments/v3/score_validation_v2.py",
    "experiments/v3/run_validation.py", "experiments/v3/score_validation.py",
    "experiments/v3/template_state.py", "experiments/v3/dev_scenarios.py",
    "experiments/v3/diag/diag1.py", "experiments/v3/diag/diag3.py", "experiments/v3/diag/diag3_dev.py",
    "experiments/v3/diag/diag3_cw.py", "experiments/v3/diag/diag3_cw_dev.py",
    "experiments/v3/frozen/cyl16p.json",
    "experiments/generators/thermal.py", "experiments/oracle/thermal_oracle.py",
    "experiments/machine/thermal_machine.py", "env/thermal_v2_env.py", "env/requirements-thermal-v2.txt",
]


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main():
    m = {
        "freeze": "v3-freeze-3",
        "validation_block": [440400, 440599],
        "reserved_after_this_block": [440600, 440999],
        "cells": ["healthy", "jump_0.2", "jump_0.5", "drift_0.0005", "drift_0.001", "drift_0.002", "drift_0.005",
                  "drift_0.02", "noise_x2", "stuck", "gain_0.01"],
        "arms": ["E0", "E1"],
        "laws_all_cells": [["rw", "uniform"], ["ramp", "uniform"]],
        "laws_healthy_extra": [["rw", "edge"], ["ramp", "edge"]],
        "record_length": 3600,
        "uncertified_limit_fraction_of_fault_runs": 0.01,
        "candidate": {
            "name": "F3", "variant": "F3", "W": 256, "B": 16, "K": 64, "pad_C": 1e-6,
            "directions_file": "experiments/v3/frozen/cyl16p.json",
            "directions_sha256": sha("experiments/v3/frozen/cyl16p.json"),
            "target_paired_lag_reduction": 0.80,
        },
        "files": {rel: sha(rel) for rel in FILES},
    }
    path = HERE / "frozen" / "MANIFEST-V3.json"
    path.write_text(json.dumps(m, indent=1) + "\n")
    print(path, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
