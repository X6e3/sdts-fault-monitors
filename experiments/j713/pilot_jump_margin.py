"""J713 pilot (development data): the oracle's smallest noise bound d* on step 2 with an upward jump at k = 900, for
prefixes ending before and after the jump. Same plant and settings as pilot_monitors.py (delta 0.3, rho 0.002, box
19-25 degC). Run from the repository root: python3 -I -B experiments/j713/pilot_jump_margin.py ATTEMPT_DIR
"""
import sys, numpy as np
sys.path.insert(0, "experiments/j713")
import pilot_monitors as PM
P, y = PM.load("step2")
off = PM.set_plant(0.3, 0.002, [19.0, 25.0], PM.p0_of(P, "mean60"), len(P))
O, V, IM, CWD = PM.import_monitors()
S = PM.command_part(P)
k = np.arange(len(y))
for size in (0.0, 0.3, 0.4, 0.5):
    z = y + off + size * (k >= 900) - S
    out = []
    for m in (900, 901, 1000, 1500, len(z)):
        lo, up = O.margin(z, m, attempt_dir=sys.argv[1])
        out.append(f"m={m}: d*={up:.4f}")
    print(f"jump +{size}:", ", ".join(out), flush=True)
