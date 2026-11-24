"""J713 monitor pilot (development data only: step 1 and step 2; step 3 is not read).

Question: do the paper's oracle and monitors (IM, TS, WM) run on a real device's record with the device's own model,
without redesign, and what noise bound does a healthy record need? Nothing here is a test; it informs whether a
preregistered test on a fresh run is worth planning.

The plant is the J713 two-node model with the four rate parameters frozen from step 1 (experiments/j713/
step3-eval.json, Ts0P), mapped onto experiments/generators/thermal.py: CC = 1/bc, K = kc CC, CS = K/ks, H = hs CS.
The constants of thermal.py are replaced in this process before any monitor module is imported; no frozen file is
changed. The oracle normally solves each LP in a fresh interpreter, which would rebuild the simulated plant; here
the LP is built and solved in this process instead (same builder, same solver attempts).

The data are shifted by OFF = 25 - (box centre) degC, so that the box sits where the code's shift of 25 degC puts
it; the dynamics are shift invariant, so this changes nothing but the coordinates. TS's start supports are
computed for the box (the frozen code assumes the half-width 2).

  python3 -I -B experiments/j713/pilot_monitors.py healthy OUT.json [--rho R ...] [--box LO HI] [--p0 first|mean60]
  python3 -I -B experiments/j713/pilot_monitors.py faults OUT.json --delta D --rho R --box LO HI [--p0 ...] [--no-wm]
"""
import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data" / "j713"
for sub in ("experiments/generators", "experiments/oracle", "experiments/machine", "experiments/v3",
            "experiments/v3/diag"):
    sys.path.insert(0, str(ROOT / sub))
import thermal as T  # noqa: E402

PARAMS = json.loads((HERE / "step3-eval.json").read_text())["sensors"]["Ts0P"]["dev_fit"]["params"]


def set_plant(delta, rho, box, p0, n):
    kc, bc, ks, hs = (PARAMS[k] for k in ("kc", "bc", "ks", "hs"))
    T.CC = 1.0 / bc
    T.K = kc * T.CC
    T.CS = T.K / ks
    T.H = hs * T.CS
    T.DT = 1.0
    off = 25.0 - (box[0] + box[1]) / 2
    T.DELTA, T.RHO_A = delta, rho
    T.TA_LO, T.TA_HI = box[0] + off, box[1] + off
    T.P_LO, T.P_HI, T.P0, T.N = 0.0, 100.0, p0, n
    return off


def load(step):
    rows = list(csv.DictReader(open(DATA / f"{step}.csv")))
    return np.array([float(r["PSTR"]) for r in rows]), np.array([float(r["Ts0P"]) for r in rows])


def p0_of(P, mode):
    return float(P[0]) if mode == "first" else float(np.mean(P[:60]))


def command_part(P):
    """S: the response of Ts to the command from the steady state of P0 at zero ambient (as the monitors compute it)."""
    tc, ts = T.equilibrium(T.P0, 0.0)
    out = np.empty(len(P))
    for k, p in enumerate(P):
        out[k] = ts
        tc, ts = T.step(tc, ts, p, 0.0)
    return out


def import_monitors():
    """Import after set_plant: these modules read thermal.py's constants at import."""
    import thermal_oracle as O
    from scipy.optimize import linprog

    def attempt_in_process(z, m, box, rate, mode, sense, method, presolve, attempt_dir):
        c, Aub, bub, Aeq, beq, bounds, _ = O._build(np.asarray(z[:m], dtype=float), m, box, rate, mode, sense)
        try:
            return linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, method=method,
                           options={"presolve": presolve})
        except Exception:                      # counted as a failed attempt, as the subprocess version does
            return None
    O._attempt = attempt_in_process
    import template_state as V
    from thermal_machine import ThermalMachine
    import diag3_cw_dev as CWD
    return O, V, ThermalMachine, CWD


def template(V):
    t = V.Template(V.directions("cyl", L=16, N=4), name="cyl16-j713", invariant=True)
    sigma = t.D @ np.ones(3)
    t.h0 = np.array([math.nextafter(max(s * V.LO, s * V.HI) * (1 + 4 * V.EPS), math.inf) for s in sigma])
    return t


def first_alarm(machine, y, P):
    for k, (a, b) in enumerate(zip(y, P)):
        if machine.observe(float(a), float(b)):
            return k
    return None


def healthy(args):
    out = []
    for rho in args.rho:
        for step in ("step1", "step2"):
            P, y = load(step)
            off = set_plant(1.0, rho, args.box, p0_of(P, args.p0), len(P))
            O, *_ = import_monitors()
            z = y + off - command_part(P)
            t0 = time.monotonic()
            d_lo, d_up = O.margin(z, attempt_dir=args.attempts)
            out.append({"step": step, "rho": rho, "box": args.box, "p0": args.p0, "P0": T.P0, "samples": len(z),
                        "d_lo": d_lo, "d_up": d_up, "seconds": round(time.monotonic() - t0, 1)})
            print(json.dumps(out[-1]), flush=True)
    return {"phase": "healthy", "params": PARAMS, "rows": out}


FAULTS = [("drift", r, s) for r in (0.0005, 0.001, 0.002, 0.005) for s in (1, -1)] + \
         [("jump", a, s) for a in (0.5, 1.0) for s in (1, -1)]


def faults(args):
    P, y = load(args.step)
    off = set_plant(args.delta, args.rho[0], args.box, p0_of(P, args.p0), len(P))
    O, V, IM, CWD = import_monitors()
    tp = template(V)
    rows = []
    for onset in args.onsets:
        for kind, size, sign in [("none", 0.0, 1)] + FAULTS:
            k = np.arange(len(y))
            if kind == "drift":
                f = sign * size * np.maximum(0, k - onset)
            elif kind == "jump":
                f = sign * size * (k >= onset)
            else:
                f = np.zeros(len(y))
            yf = y + off + f
            z = yf - command_part(P)
            t0 = time.monotonic()
            t_star, status = O.first_inconsistent(z, attempt_dir=args.attempts)
            row = {"onset": onset, "fault": kind, "size": size, "sign": sign, "t_star": t_star, "status": status,
                   "oracle_s": round(time.monotonic() - t0, 1)}
            row["IM"] = first_alarm(IM(), yf, P)
            row["TS"] = first_alarm(V.TemplateMachine(tp), yf, P)
            if args.wm:
                t0 = time.monotonic()
                r = CWD.online("F3", list(z - V.SHIFT), 256, 64, t_star, tp=tp)
                row["WM"] = r["detect"]
                row["WM_certified"] = (r.get("alarm_certificate") or {}).get("certified")
                row["WM_s"] = round(time.monotonic() - t0, 1)
            rows.append(row)
            print(json.dumps(row), flush=True)
    return {"phase": "faults", "step": args.step, "params": PARAMS, "delta": args.delta, "rho": args.rho[0],
            "box": args.box, "p0": args.p0, "P0": T.P0, "offset": off, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("healthy", "faults"))
    ap.add_argument("out")
    ap.add_argument("--rho", type=float, nargs="+", default=[0.0005])
    ap.add_argument("--box", type=float, nargs=2, default=[19.0, 25.0])
    ap.add_argument("--p0", choices=("first", "mean60"), default="mean60")
    ap.add_argument("--delta", type=float, default=0.4)
    ap.add_argument("--step", default="step2", choices=("step1", "step2"))
    ap.add_argument("--onsets", type=int, nargs="+", default=[300])
    ap.add_argument("--no-wm", dest="wm", action="store_false")
    ap.add_argument("--attempts", default=None)
    args = ap.parse_args()
    if args.phase == "healthy" and len(args.rho) > 1:
        print("note: one process per rho would be cleaner; constants are reset before each import", file=sys.stderr)
    res = healthy(args) if args.phase == "healthy" else faults(args)
    Path(args.out).write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
