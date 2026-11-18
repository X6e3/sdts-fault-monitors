"""v3 development scenarios. Never TRAIN, CAL or FINAL seeds of v2; never the reserved v3 validation range.

  DEV seeds        430000-430099  (development: anything may be looked at)
  VALIDATION seeds 440000-440999  (reserved for an independent check of a frozen v3; not generated here)

Same plant, assumptions, faults and arms as v2. Two ambient laws and two noise laws, all admissible:
  ambient "rw"    the v2 law (bounded uniform random walk), with v3-only seed strings
  ambient "ramp"  piecewise ramps at a random fraction of the full rate RHO_A, switching after an exponential
                  time (mean 300 s), turned back at the box: much harder than "rw" for any method that only
                  learned how quiet the v2 ambient is
  noise "uniform" uniform in [-DELTA, DELTA] (v2)
  noise "edge"    +-DELTA exactly, random sign: on the boundary of (a), to stress soundness

VALIDATION seeds use the same laws with their own seed strings ("v3val:" instead of "v3dev:"). They can only
be generated after unlock_validation(), which only run_validation.py calls, and only once the freeze record
is approved and its manifest matches (FREEZE-V1.md). Nothing else in the repository unlocks them.
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generators"))
import thermal as T  # noqa: E402

DEV = range(430000, 430100)
VALIDATION = range(440000, 441000)


_VALIDATION_UNLOCKED = False


def unlock_validation(approved_manifest_sha256):
    """Called by run_validation.py after it has checked the approved freeze record. Not for anything else."""
    global _VALIDATION_UNLOCKED
    if not isinstance(approved_manifest_sha256, str) or len(approved_manifest_sha256) != 64:
        raise ValueError("unlock needs the approved manifest sha256")
    _VALIDATION_UNLOCKED = True


def _prefix(seed):
    if seed in DEV:
        return "v3dev"
    if seed in VALIDATION and _VALIDATION_UNLOCKED:
        return "v3val"
    raise ValueError(f"v3 development uses DEV seeds 430000-430099 only, got {seed}")


def ambient(seed, law, n=T.N):
    rng = random.Random(f"{_prefix(seed)}:{seed}:ambient:{law}")
    ta = [rng.uniform(T.TA_LO, T.TA_HI)]
    if law == "rw":
        for _ in range(n - 1):
            ta.append(min(T.TA_HI, max(T.TA_LO, ta[-1] + rng.uniform(-T.RHO_A, T.RHO_A))))
        return ta
    if law != "ramp":
        raise ValueError(law)
    rate, left = 0.0, 0
    for _ in range(n - 1):
        if left <= 0:
            rate = rng.choice((-1, 1)) * rng.uniform(0.5, 1.0) * T.RHO_A
            left = max(1, int(rng.expovariate(1 / 300)))
        nxt = ta[-1] + rate
        if not T.TA_LO <= nxt <= T.TA_HI:
            rate, nxt = -rate, ta[-1] - rate
        ta.append(min(T.TA_HI, max(T.TA_LO, nxt)))
        left -= 1
    return ta


def noise(seed, law, n=T.N):
    rng = random.Random(f"{_prefix(seed)}:{seed}:noise:{law}")
    if law == "uniform":
        return [rng.uniform(-T.DELTA, T.DELTA) for _ in range(n)]
    if law == "edge":
        return [T.DELTA if rng.random() < 0.5 else -T.DELTA for _ in range(n)]
    raise ValueError(law)


def command(seed, arm, n=T.N):
    if arm == "E0":
        return [T.P0] * n
    rng = random.Random(f"{_prefix(seed)}:{seed}:command")
    P, p = [], T.P0
    for k in range(n):
        if k % T.E1_PERIOD == 0:
            p = rng.uniform(T.P_LO, T.P_HI)
        P.append(p)
    return P


def onset(seed):
    return random.Random(f"{_prefix(seed)}:{seed}:onset").randint(300, 600)


def run(seed, cell, arm, ambient_law="rw", noise_law="uniform", n=T.N):
    P, TA, v, t_f = command(seed, arm, n), ambient(seed, ambient_law, n), noise(seed, noise_law, n), onset(seed)
    Ts = T.simulate(P, TA, T.equilibrium(T.P0, TA[0]))
    y = T.sensor(cell, Ts, v, t_f)
    S = T.known_part(P)
    return {"seed": seed, "cell": cell.name, "arm": arm, "ambient_law": ambient_law, "noise_law": noise_law,
            "P": P, "TA": TA, "v": v, "t_f": t_f, "Ts": Ts, "y": y, "S": S, "z": [a - b for a, b in zip(y, S)]}
