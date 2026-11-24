"""Independent read-only checks of reviewer B's CAL evidence (no evidence-supplied code is executed).
usage: python -I check_evidence.py <review-worktree> <evidence-dir>"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

repo, ev = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / "experiments" / "generators"))
import thermal as T  # noqa: E402

D, ADD = T.DELTA, ("offset", "jump", "drift", "noise")
kind = {c.name: c for c in T.CELLS}
problems = []


def rows(p):
    return [json.loads(l) for l in (ev / p).read_text().splitlines() if l.strip()]


def bad(msg):
    problems.append(msg)
    print("  !!", msg)


# A. final oracle map
print("A. oracle map cal-4e87cd3/cells.jsonl")
O = rows("cal-4e87cd3/cells.jsonl")
keys = {(r["seed"], r["cell"], r["arm"]) for r in O}
want = {(s, c.name, a) for s in range(410000, 410050) for c in T.CELLS for a in T.ARMS}
print("  rows", len(O), "unique", len(keys), "== expected set:", keys == want)
cnt = Counter(r["verdict"] for r in O)
print("  verdicts", dict(cnt))
for r in O:
    if r["d_lo"] > r["d_up"] + 1e-12:
        bad(f"d_lo>d_up {r}")
    v = r["verdict"]
    if v == "consistent" and not r["d_up"] <= D:
        bad(f"consistent without d_up<=delta {r}")
    if v == "inconsistent" and not r["d_lo"] > D:
        bad(f"inconsistent without d_lo>delta {r}")
Ok = {(r["seed"], r["cell"], r["arm"]): r for r in O}

# B. first vs second full run
O1 = {(r["seed"], r["cell"], r["arm"]): r for r in rows("cal-c04305a/cells.jsonl")}
diff = [(k, O1[k]["verdict"], Ok[k]["verdict"]) for k in Ok if O1[k]["verdict"] != Ok[k]["verdict"]]
print("B. c04305a -> 4e87cd3 verdict changes:", diff)
for k, a, b in diff:
    if a != "undetermined":
        bad(f"a decided verdict changed {k} {a}->{b}")

# C. P2 recomputed
pairs = [(s, c) for s in range(410000, 410050) for c in T.CELLS if c.kind in ADD]
same = sum(Ok[(s, c.name, "E0")]["verdict"] == Ok[(s, c.name, "E1")]["verdict"] for s, c in pairs)
print(f"C. P2 oracle E0==E1 on additive cells: {same}/{len(pairs)}")

# D/E. V0 and P6
V = rows("cal-4e87cd3/V0_P6.jsonl")
print("D. V0 rows", len(V), Counter(r["verdict"] for r in V), "max d_up", max(r["d_up"] for r in V))
for r in V:
    if r["seed"] < 410050 and Ok[(r["seed"], "healthy", r["arm"])]["verdict"] != r["verdict"]:
        bad(f"V0 vs map {r['seed']} {r['arm']}")
    lo, hi = r["interval"]
    olo, ohi = r["outer_interval"]
    if not (olo <= lo <= hi <= ohi):
        bad(f"inner not inside outer {r['seed']} {r['arm']}")


def rule(R, amin, amax):
    """Proposition 2: certifiable iff A_min <= 23+R and A_max >= 27-R; scored only with margin > delta."""
    m1, m2 = (23 + R) - amin, amax - (27 - R)
    if m1 > D and m2 > D:
        return 1
    if m1 < -D or m2 < -D:
        return -1
    return 0


for R in (1, 3):
    P6 = {(r["seed"], r["arm"]): r for r in rows(f"cal-4e87cd3/P6_R{R}.jsonl")}
    tab = Counter()
    for r in V:
        mine = rule(R, r["A_min"], r["A_max"])
        lo, hi = r["interval"]
        olo, ohi = r["outer_interval"]
        if -R <= olo and ohi <= R:
            orc = "certifiable"
        elif lo < -R or hi > R:
            orc = "not_certifiable"
        else:
            orc = "undetermined"
        ref = P6[(r["seed"], r["arm"])]
        if ref["rule"] != mine:
            bad(f"P6 R={R} rule mismatch {r['seed']} {r['arm']} mine={mine} ref={ref['rule']}")
        if ref["oracle"] != orc:
            bad(f"P6 R={R} oracle label mismatch {r['seed']} {r['arm']} mine={orc} ref={ref['oracle']}")
        tab[(mine, orc)] += 1
    scored = {k: v for k, v in tab.items() if k[0] != 0}
    agree = sum(v for (m, o), v in scored.items() if (m == 1 and o == "certifiable") or (m == -1 and o == "not_certifiable"))
    print(f"E. P6 R={R}: (rule, oracle) {dict(tab)}; scored agree {agree}/{sum(scored.values())}")

# F. P7
P7 = rows("cal-4e87cd3/P7.jsonl")
e0 = Counter(r["full"] for r in P7 if r["arm"] == "E0")
e1 = [r for r in P7 if r["arm"] == "E1"]
print("F. P7 E0", dict(e0), "| E1 n", len(e1),
      "| by k+30:", Counter(r["by_k_plus_30"] for r in e1),
      "| before k:", Counter(r["before_change"] for r in e1),
      "| at t_f:", Counter(r["at_tf"] for r in e1))
for r in e1:
    P = T.command(r["seed"], "E1")
    t_f = T.onset(r["seed"])
    k = next(k for k in range(t_f + 1, T.N) if abs(P[k] - P[k - 1]) >= 5.0)
    if (k, t_f) != (r["k_change"], r["t_f"]):
        bad(f"P7 k/t_f mismatch {r['seed']}: mine {k},{t_f} ref {r['k_change']},{r['t_f']}")

# G. latency
L = rows("cal-latency-final/latency.jsonl")
print("G. latency rows", len(L), Counter(r["status"] for r in L))
Lk = {(r["seed"], r["cell"], r["arm"]): r for r in L}
for (s, c, a), r in Lk.items():
    if Ok[(s, c, a)]["verdict"] == "consistent" and r["t_star"] is not None:
        bad(f"latency t* for a consistent run {s} {c} {a}")
    if Ok[(s, c, a)]["verdict"] == "inconsistent" and r["t_star"] is None:
        bad(f"no t* for an inconsistent run {s} {c} {a}")
    if c in ("jump_2", "jump_5") and r["t_star"] != r["t_f"]:
        bad(f"P4 t* != t_f {s} {c} {a}")

# H. machine
M = rows("cal-machine-complete/cells.jsonl")
Mk = {(r["seed"], r["cell"], r["arm"]): r for r in M}
print("H. machine rows", len(M), "unique", len(Mk))
INC = "TUTARSIZ"
h_inc = sum(r["verdicts"]["1"] == INC for r in M if r["cell"] == "healthy")
print("  healthy TUTARSIZ:", h_inc)
sound = gap = 0
for k, o in Ok.items():
    m = Mk[k]
    mi = m["first_inconsistent"] is not None
    if mi and o["verdict"] != "inconsistent":
        bad(f"machine inconsistent but oracle {o['verdict']} {k}")
    if o["verdict"] == "inconsistent" and not mi:
        gap += 1
    sound += 1
print(f"  machine-vs-oracle on {sound} shared runs: machine misses {gap} oracle inconsistencies")
lat = []
for k, r in Lk.items():
    m = Mk[k]
    if r["t_star"] is None:
        continue
    if m["first_inconsistent"] is None:
        bad(f"machine never inconsistent where oracle t* exists {k}")
        continue
    if m["first_inconsistent"] < r["t_star"]:
        bad(f"machine earlier than oracle {k}: {m['first_inconsistent']} < {r['t_star']}")
    lat.append((m["first_inconsistent"] - r["t_star"], k))
lat.sort()
print(f"  machine - oracle latency on {len(lat)} runs: min {lat[0][0]} median {lat[len(lat)//2][0]} max {lat[-1][0]} at {lat[-1][1]}")
Vk = {(r["seed"], r["arm"]): r for r in V}
for (s, a), r in Vk.items():
    m = Mk[(s, "healthy", a)]
    lo, hi = r["interval"]
    if m["offset_outer"] is None or not (m["offset_outer"][0] <= lo and hi <= m["offset_outer"][1]):
        bad(f"machine outer does not contain oracle inner {s} {a}")
    for R in ("1", "3"):
        if m["verdicts"][R] == "TUTARLI" and not (-float(R) <= lo and hi <= float(R)):
            bad(f"P3 TUTARLI vs oracle inner {s} {a} R={R}")

# I. what TUTARLI means on faulty runs
print("I. TUTARLI counts per cell (both arms, 200 seeds each) and the true sensor error on those runs")
for R in ("1", "3"):
    per = defaultdict(list)
    for r in M:
        if r["verdicts"][R] == "TUTARLI":
            per[r["cell"]].append(r)
    for cell, rs in sorted(per.items()):
        c = kind[cell]
        errs = []
        for r in rs:
            t_f = r["t_f"]
            if c.kind == "drift":
                errs.append(c.value * (T.N - 1 - t_f))
            elif c.kind == "offset":
                errs.append(c.value)
            elif c.kind == "jump":
                errs.append(c.value)
            elif c.kind in ("healthy",):
                errs.append(0.0)
            else:
                errs.append(float("nan"))
        print(f"  R={R} {cell:14s} TUTARLI {len(rs):4d}  final |sensor error| min {min(errs):.3f} max {max(errs):.3f}")

print("\nPROBLEMS:", len(problems))
