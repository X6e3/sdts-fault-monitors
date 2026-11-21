"""C1-PLAN.md, checks Y1-Y3: the c1 C state against freeze 1's C state and against the exact recurrence.

Y1 tables: each c1 header differs from the frozen header only in its first comment line and in V3_H0, and in V3_H0
   only at the directions whose frozen value is below the exact start support.
Y2 code: c1/v3_state.c differs from c/v3_state.c only in the ETA define and the two slab lines.
Y3 soundness: check_c_state.py's K1-K5 on the c1 headers (K5 without any follow-up), and K6's eps < ETA.
usage: python -B check_c1.py [--out FILE.json]
"""
import argparse
import difflib
import json
import sys
from fractions import Fraction as Fr
from pathlib import Path

HERE = Path(__file__).resolve().parent
V3 = HERE.parent
sys.path[:0] = [str(HERE), str(V3)]
import check_c_state as K  # noqa: E402
import codegen_c1 as G1  # noqa: E402

CG = G1.CG
ETA_C1 = 1e-9


def c1_header(real):
    tp, hmax, idx, lam, starts, pads, label = G1.c1_tables(real)
    text = CG.emit(tp, hmax, idx, lam, starts, pads, real, label)
    path = V3 / "c1" / f"tables_cyl16p1_{real}.h"
    up = lambda x: Fr(CG.up_to(x, real))
    import math
    return {"K1_header_equal": text == path.read_text(), "tp": tp, "idx": idx,
            "lam": [[Fr(x) for x in r] for r in lam], "starts": starts, "pad": [up(p) for p in pads],
            "hmax": up(hmax), "cap_const": Fr(2.2),
            "rhopad": [up(math.nextafter(x, math.inf)) if x else Fr(0) for x in tp.rho_pad],
            "caps": [up(x) for x in CG._caps(tp)], "h0": [up(x) for x in tp.clamp(tp.h0)],
            "u": Fr(1, 2 ** 53) if real == "double" else Fr(1, 2 ** 24)}, path


def y1(real, h):
    old = (V3 / "frozen" / "c" / f"tables_cyl16p_{real}.h").read_text().splitlines()
    new = (V3 / "c1" / f"tables_cyl16p1_{real}.h").read_text().splitlines()
    lines = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    h0_line = next(i for i, l in enumerate(old) if l.startswith("static const v3_real V3_H0"))
    body = lambda l: l[l.index("{") + 1:l.rindex("}")].split(",")
    changed = [i for i, (a, b) in enumerate(zip(body(old[h0_line]), body(new[h0_line]))) if a != b]
    fro = K.headers()[real]
    short = [i for i, d in enumerate(h["tp"].D) if fro["h0"][i] < G1.start_support(d)]
    ok = len(old) == len(new) and set(lines) <= {0, h0_line} and changed == short
    return {"lines_differing": lines, "h0_line": h0_line, "h0_entries_changed": changed,
            "frozen_h0_below_start_support": short, "holds": ok}


def y2():
    a = (V3 / "c" / "v3_state.c").read_text().splitlines()
    b = (V3 / "c1" / "v3_state.c").read_text().splitlines()
    d = [l for l in difflib.unified_diff(a, b, lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    removed = [l[1:].strip() for l in d if l.startswith("-")]
    added = [l[1:].strip() for l in d if l.startswith("+")]
    want_removed = ["v3_real lo = DOWN((v3_real)nextafter(nextafter(zs, -INFINITY) - DELTA, -INFINITY));",
                    "v3_real hi = UP((v3_real)nextafter(nextafter(zs, INFINITY) + DELTA, INFINITY));"]
    want_added = [l for l in added if l.startswith("#define ETA 1e-9")][:1] + \
                 [w.replace("- DELTA,", "- (DELTA + ETA),").replace("+ DELTA,", "+ (DELTA + ETA),") for w in want_removed]
    h_same = (V3 / "c" / "v3_state.h").read_bytes() == (V3 / "c1" / "v3_state.h").read_bytes()
    return {"removed": removed, "added": added, "header_same": h_same,
            "holds": removed == want_removed and added == want_added and len(want_added) == 3 and h_same}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    ub = K.exact_sup()
    rep = {"headers": {}}
    ok = True
    for real in ("double", "float"):
        h, path = c1_header(real)
        k2 = K.pads(h)
        k3, k4, k5 = K.clamps_rate_start(h, ub)
        r = {"Y1": y1(real, h), "K1_header_equal": h["K1_header_equal"], "K2_pads": k2, "K3_clamps": k3,
             "K4_rate_pads": k4, "K5_start": k5}
        r["holds"] = {"Y1": r["Y1"]["holds"], "K1": h["K1_header_equal"],
                      "K2": k2["entries_not_covered"] == 0 and k2["negative_lambdas"] == 0,
                      "K3": not k3["caps_not_proved"], "K4": not k4["rate_pads_too_small"],
                      "K5": not k5["start_supports_too_small"]}
        ok &= all(r["holds"].values())
        rep["headers"][real] = r
    rep["Y2"] = y2()
    k6 = K.data_bound(Fr(1, 2 ** 53))
    rep["K6_data"] = {"eps": k6["eps"], "ETA": ETA_C1, "holds": k6["eps"] < ETA_C1}
    rep["Y1_Y2_Y3_hold"] = ok and rep["Y2"]["holds"] and rep["K6_data"]["holds"]
    txt = json.dumps(rep, indent=1, default=str)
    print(txt)
    if a.out:
        a.out.write_text(txt + "\n")


if __name__ == "__main__":
    main()
