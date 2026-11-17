"""Two-node thermal plant, faults and runs for
experiments/specs/thermal_single_sensor_consistency.md (protocol v2).

Pure Python and deterministic. Every random stream has its own string seed, so the ambient path, the
noise and the fault onset of a seed are identical across cells and excitation arms (the paired design
P2 needs).
"""
import random
from dataclasses import dataclass

CC, CS, K, H = 30.0, 12.0, 2.0, 0.8
DT = 1.0
DELTA = 0.3          # (a) noise bound
RHO_A = 0.002        # (b) ambient rate bound per sample
TA_LO, TA_HI = 23.0, 27.0   # (c) ambient box
P_LO, P_HI, P0 = 0.0, 42.0, 20.0
N = 3600
T_WARM = 300
E1_PERIOD = 15


def step(tc, ts, p, ta):
    return (tc + DT * (p - K * (tc - ts)) / CC,
            ts + DT * (K * (tc - ts) - H * (ts - ta)) / CS)


def equilibrium(p, ta):
    """(Tc, Ts) at steady state for command p and ambient ta."""
    ts = ta + p / H
    return ts + p / K, ts


def simulate(P, TA, x0):
    """Ts[k] for k = 0..len(P)-1, starting at x0 = (Tc, Ts); Ts[0] = x0[1]."""
    tc, ts = x0
    out = []
    for p, ta in zip(P, TA):
        out.append(ts)
        tc, ts = step(tc, ts, p, ta)
    return out


def command(seed, arm, n=N):
    if arm == "E0":
        return [P0] * n
    rng = random.Random(f"{seed}:command")
    P, p = [], P0
    for k in range(n):
        if k % E1_PERIOD == 0:
            p = rng.uniform(P_LO, P_HI)
        P.append(p)
    return P


def ambient(seed, n=N):
    """Bounded random walk: start uniform in the box, steps uniform in [-RHO_A, RHO_A], clipped."""
    rng = random.Random(f"{seed}:ambient")
    ta = [rng.uniform(TA_LO, TA_HI)]
    for _ in range(n - 1):
        ta.append(min(TA_HI, max(TA_LO, ta[-1] + rng.uniform(-RHO_A, RHO_A))))
    return ta


def noise(seed, n=N):
    rng = random.Random(f"{seed}:noise")
    return [rng.uniform(-DELTA, DELTA) for _ in range(n)]


def onset(seed):
    return random.Random(f"{seed}:onset").randint(300, 600)


@dataclass(frozen=True)
class Cell:
    name: str
    kind: str        # healthy, offset, jump, drift, noise, stuck, gain
    value: float = 0.0
    additive: bool = True


CELLS = (
    [Cell("healthy", "healthy")]
    + [Cell(f"offset_{b:g}", "offset", b) for b in (1.0, 3.0)]
    + [Cell(f"jump_{j:g}", "jump", j) for j in (0.2, 0.5, 1.0, 2.0, 5.0)]
    + [Cell(f"drift_{r:g}", "drift", r) for r in (0.0005, 0.001, 0.002, 0.005, 0.02, 0.1)]
    + [Cell(f"noise_x{m:g}", "noise", m) for m in (2.0, 4.0)]
    + [Cell("stuck", "stuck", additive=False)]
    + [Cell(f"gain_{g:g}", "gain", g, additive=False) for g in (0.01, 0.05)]
)
ARMS = ("E0", "E1")


def sensor(cell, Ts, v, t_f):
    """The sensor reading y[k] for a cell, given the true Ts, the base noise v and the onset t_f."""
    y = []
    for k, (ts, vk) in enumerate(zip(Ts, v)):
        after = k >= t_f
        if cell.kind == "healthy":
            y.append(ts + vk)
        elif cell.kind == "offset":                     # from t = 0
            y.append(ts + cell.value + vk)
        elif cell.kind == "jump":
            y.append(ts + (cell.value if after else 0.0) + vk)
        elif cell.kind == "drift":
            y.append(ts + (cell.value * (k - t_f) if after else 0.0) + vk)
        elif cell.kind == "noise":
            y.append(ts + (cell.value * vk if after else vk))
        elif cell.kind == "stuck":
            y.append((Ts[t_f] if after else ts) + vk)
        elif cell.kind == "gain":
            y.append(((1.0 + cell.value) * ts if after else ts) + vk)
        else:
            raise ValueError(cell.kind)
    return y


def known_part(P):
    """S[k]: the command response from the P0 steady state at zero ambient. Known to the machine."""
    return simulate(P, [0.0] * len(P), equilibrium(P0, 0.0))


def ambient_part(TA):
    """A[k]: the ambient response with zero command, started at equilibrium at TA[0]."""
    return simulate([0.0] * len(TA), TA, (TA[0], TA[0]))


def run(seed, cell, arm, n=N):
    P = command(seed, arm, n)
    TA = ambient(seed, n)
    v = noise(seed, n)
    t_f = onset(seed)
    Ts = simulate(P, TA, equilibrium(P0, TA[0]))
    y = sensor(cell, Ts, v, t_f)
    S = known_part(P)
    z = [a - b for a, b in zip(y, S)]
    return {"seed": seed, "cell": cell.name, "arm": arm, "P": P, "TA": TA, "v": v, "t_f": t_f,
            "Ts": Ts, "y": y, "S": S, "z": z}
