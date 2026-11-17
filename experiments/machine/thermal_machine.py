"""Online consistency and offset bounds from section 4 of the thermal protocol."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generators"))
import thermal as T


def _advance(interval, low, high, radius):
    lo, hi = interval
    if lo > hi:
        return interval
    return (max(low, math.nextafter(lo - radius, -math.inf)),
            min(high, math.nextafter(hi + radius, math.inf)))


class ThermalMachine:
    def __init__(self, *, box=True, rate=True):
        self._box = box
        self._radius = T.RHO_A if rate else math.inf
        self._tc, self._ts = T.equilibrium(T.P0, 0.0)
        self._free = (-math.inf, math.inf)
        self._feasible = (T.TA_LO, T.TA_HI) if box else self._free
        self._offset = self._free

    def observe(self, y, power):
        """Consume one measurement and the command applied after that measurement."""
        if not math.isfinite(y) or not T.P_LO <= power <= T.P_HI:
            raise ValueError("expected a finite measurement and an admissible command")
        z = y - self._ts
        low = math.nextafter(math.nextafter(z, -math.inf) - T.DELTA, -math.inf)
        high = math.nextafter(math.nextafter(z, math.inf) + T.DELTA, math.inf)
        self._tc, self._ts = T.step(self._tc, self._ts, power, 0.0)

        self._free = _advance(self._free, low, high, self._radius)
        if self._box:
            self._feasible = _advance(self._feasible, max(low, T.TA_LO), min(high, T.TA_HI), self._radius)
            free_lo, free_hi = self._free
            self._offset = (max(self._offset[0], math.nextafter(free_lo - T.TA_HI, -math.inf)),
                            min(self._offset[1], math.nextafter(free_hi - T.TA_LO, math.inf)))
        else:
            self._feasible = self._free
        return self.inconsistent

    @property
    def inconsistent(self):
        return self._feasible[0] > self._feasible[1]

    @property
    def offset_outer(self):
        """A sound outer interval, or None when every constant offset is excluded."""
        if self._free[0] > self._free[1] or self._offset[0] > self._offset[1]:
            return None
        return self._offset

    def verdict(self, radius):
        if not math.isfinite(radius) or radius < 0:
            raise ValueError("offset radius must be finite and nonnegative")
        if self.inconsistent:
            return "TUTARSIZ"
        outer = self.offset_outer
        if outer is not None and outer[0] >= -radius and outer[1] <= radius:
            return "TUTARLI"
        return "AYIRT EDİLEMEZ"
