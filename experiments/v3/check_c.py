"""Cross-check the C template state (float32 and float64 builds) against the Python reference on DEV runs.

Expected: healthy runs never flagged (also at the noise edge); on fault runs the C first-inconsistent sample is
never earlier than Python's (C pads are static, so they can only be more conservative) and usually equal.
usage: python -B check_c.py BIN_FLOAT BIN_DOUBLE [--seeds 430030 430039]
"""
import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402

T = V.T
CELLS = ("healthy", "jump_0.2", "jump_0.5", "drift_0.0005", "drift_0.001", "drift_0.002", "drift_0.005", "noise_x2",
         "stuck", "gain_0.01")


def c_first(binary, y, P):
    text = "".join(f"{a!r} {b!r}\n" for a, b in zip(y, P))
    out = subprocess.run([binary], input=text, capture_output=True, text=True, check=True).stdout
    first = int(out.split()[0].split("=")[1])
    return None if first < 0 else first


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bin_float")
    ap.add_argument("bin_double")
    ap.add_argument("--seeds", type=int, nargs=2, default=(430030, 430039))
    ap.add_argument("--prune", action="store_true")
    a = ap.parse_args()
    import codegen_c
    tp = codegen_c.make_template("inv", 4, 0, a.prune)
    stats, problems = Counter(), []
    for seed in range(a.seeds[0], a.seeds[1] + 1):
        for name in CELLS:
            cell = next(c for c in T.CELLS if c.name == name)
            for arm in T.ARMS:
                laws = [("rw", "uniform"), ("ramp", "uniform")] + ([("rw", "edge"), ("ramp", "edge")] if name == "healthy" else [])
                for al, nl in laws:
                    r = S.run(seed, cell, arm, al, nl)
                    py = V.first_inconsistent(tp, r["y"], r["P"])
                    for tag, b in (("float", a.bin_float), ("double", a.bin_double)):
                        c = c_first(b, r["y"], r["P"])
                        if name == "healthy" and c is not None:
                            problems.append(("healthy flagged", tag, seed, arm, al, nl, c))
                        elif py is not None and c is not None and c < py:
                            problems.append(("C earlier than Python", tag, seed, name, arm, al, c, py))
                        elif (py is None) != (c is None):
                            stats[f"{tag}: detection differs"] += 1
                        elif py is not None:
                            stats[f"{tag}: lag C-Python={c - py}"] += 1
                        else:
                            stats[f"{tag}: both none"] += 1
    print(dict(sorted(stats.items())))
    print("problems:", len(problems))
    for p in problems[:20]:
        print("  ", p)


if __name__ == "__main__":
    main()
