"""The existing P1 fixtures, with paired measurements and commands on CAL."""
import random


def open_twins(T, seed, arm, ambient, noise, offset):
    command = T.command(seed, arm)
    shifted = [a + offset for a in ambient]
    first = T.simulate(command, ambient, T.equilibrium(T.P0, ambient[0]))
    second = T.simulate(command, shifted, T.equilibrium(T.P0, shifted[0]))
    return ([y + offset + v for y, v in zip(first, noise)], command,
            [y + v for y, v in zip(second, noise)], command)


def closed_run(T, ambient, noise, offset):
    tc, ts = T.equilibrium(T.P0, ambient[0])
    samples, command = [], []
    for ta, v in zip(ambient, noise):
        y = ts + offset + v
        p = min(T.P_HI, max(T.P_LO, T.P0 + 3.0 * (50.0 - y)))
        samples.append(y)
        command.append(p)
        tc, ts = T.step(tc, ts, p, ta)
    return samples, command


def pairs(T):
    open_rng = random.Random('P1-offsets')
    closed_rng = random.Random('P1-closed')
    for seed in range(410000, 410200):
        ambient, noise = T.ambient(seed), T.noise(seed)
        for arm in T.ARMS:
            for draw, b in enumerate((1.0, 3.0, open_rng.uniform(-5, 5))):
                yield seed, 'offset_open', arm, draw, b, open_twins(T, seed, arm, ambient, noise, b)
        for draw, b in enumerate((1.0, 3.0, closed_rng.uniform(-5, 5))):
            left = closed_run(T, ambient, noise, b)
            right = closed_run(T, [a + b for a in ambient], noise, 0.0)
            yield seed, 'offset_closed', 'closed', draw, b, (*left, *right)
        p = T.command(seed, 'E0')
        constant = [ambient[0]] * T.N
        ts = T.simulate(p, constant, T.equilibrium(T.P0, constant[0]))
        tf = T.onset(seed)
        stuck = T.sensor(T.Cell('stuck', 'stuck', additive=False), ts, noise, tf)
        healthy = T.sensor(T.CELLS[0], ts, noise, tf)
        yield seed, 'stuck_rest', 'E0', 0, None, (stuck, p, healthy, p)
