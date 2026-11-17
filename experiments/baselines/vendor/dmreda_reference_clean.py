"""
DMREDA clean reference implementation.

How to use:
1. Prepare a 1-D numpy array or Python sequence representing the signal.
2. Import `compute_dmreda_reference` from this module.
3. Call it with optional `mode`, `regime_tick`, `profiles`, or `debug=True`.
4. The returned `DMREDAResult` stores every internal trace as length-N arrays.
5. `result.event_times` contains confirmed event indices.
6. `result.confirmed[t]` is True exactly at confirmed event samples.
7. `result.pending[t]` marks samples while a candidate event is under validation.
8. `result.state[t]` is the regime FSM state at sample `t`.
9. `result.d` is normalized deviation and `result.g` is smoothed growth.
10. `result.m_eff` and `result.confirm_len_eff` show active adaptive parameters.
11. The implementation is causal: trailing median, trailing energy, no look-ahead.
12. Debug mode prints internal status every `debug_every` samples.
13. Running `python3 dmreda_reference_clean.py` executes a small self-test suite.
14. The self-tests cover constant signal, step response, random noise sanity,
    and a regime-tick behavior check.
15. This file is intended as a research-grade reference, not an MCU port.
16. Only Python stdlib and numpy are required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class DMREDAProfile:
    """Spec v0.5 profile for one regime state."""

    w1: int
    w2: int
    beta: float
    rho: float
    m_set: Tuple[int, ...]
    m_base: int
    lam: float
    th_d: float
    th_g: float
    th_d2: float
    th_a: float
    n_min: int
    e_floor: float
    confirm_base: int
    confirm_min: int
    confirm_max: int
    alpha: float
    g_ref: float
    refractory: int
    hold_up: int
    hold_down: int
    eta: float = 0.25


@dataclass(frozen=True)
class RegimeTransition:
    """Regime hysteresis thresholds for a single state."""

    up_threshold: Optional[float] = None
    down_threshold: Optional[float] = None


@dataclass
class DMREDAResult:
    """Spec v0.5 full trace output with one array per internal signal."""

    mu: np.ndarray
    e: np.ndarray
    e1: np.ndarray
    e_baseline: np.ndarray
    e_baseline_safe: np.ndarray
    d: np.ndarray
    g_raw: np.ndarray
    g: np.ndarray
    r: np.ndarray
    a: np.ndarray
    a_slow: np.ndarray
    state: np.ndarray
    m_eff: np.ndarray
    confirm_len_eff: np.ndarray
    pending: np.ndarray
    confirmed: np.ndarray
    event_active: np.ndarray
    event_times: List[int]
    warmup_samples: int
    mode: str


DEFAULT_PROFILES: Dict[int, DMREDAProfile] = {
    0: DMREDAProfile(
        w1=7,
        w2=16,
        beta=1.0 / 32.0,
        rho=1.0 / 64.0,
        m_set=(2, 4),
        m_base=4,
        lam=1.0 / 8.0,
        th_d=0.35,
        th_g=0.10,
        th_d2=0.20,
        th_a=1.8,
        n_min=6,
        e_floor=2e-2,
        confirm_base=20,
        confirm_min=12,
        confirm_max=30,
        alpha=0.50,
        g_ref=0.20,
        refractory=80,
        hold_up=200,
        hold_down=400,
    ),
    1: DMREDAProfile(
        w1=9,
        w2=24,
        beta=1.0 / 24.0,
        rho=1.0 / 48.0,
        m_set=(3, 6),
        m_base=6,
        lam=1.0 / 10.0,
        th_d=0.45,
        th_g=0.13,
        th_d2=0.28,
        th_a=2.6,
        n_min=8,
        e_floor=4e-2,
        confirm_base=28,
        confirm_min=18,
        confirm_max=40,
        alpha=0.45,
        g_ref=0.25,
        refractory=100,
        hold_up=250,
        hold_down=450,
    ),
    2: DMREDAProfile(
        w1=11,
        w2=32,
        beta=1.0 / 16.0,
        rho=1.0 / 32.0,
        m_set=(4, 8),
        m_base=8,
        lam=1.0 / 12.0,
        th_d=0.60,
        th_g=0.18,
        th_d2=0.40,
        th_a=3.6,
        n_min=10,
        e_floor=8e-2,
        confirm_base=40,
        confirm_min=28,
        confirm_max=60,
        alpha=0.40,
        g_ref=0.30,
        refractory=140,
        hold_up=300,
        hold_down=500,
    ),
}


DEFAULT_TRANSITIONS: Dict[int, RegimeTransition] = {
    0: RegimeTransition(up_threshold=0.35),
    1: RegimeTransition(up_threshold=0.60, down_threshold=0.20),
    2: RegimeTransition(down_threshold=0.40),
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ema_update(prev: float, value: float, alpha: float) -> float:
    return alpha * value + (1.0 - alpha) * prev


def _median_trailing(signal: np.ndarray, t: int, width: int) -> float:
    start = max(0, t - width + 1)
    return float(np.median(signal[start : t + 1]))


def _select_m(m_set: Sequence[int], a_slow: float) -> int:
    ordered = sorted(int(v) for v in m_set)
    if len(ordered) == 1:
        return ordered[0]

    scaled = (1.0 - a_slow) * (len(ordered) - 1)
    index = int(np.floor(scaled + 0.5))
    return ordered[index]


def _compute_confirm_len(profile: DMREDAProfile, a_slow: float) -> int:
    raw = profile.confirm_base * (1.0 - profile.alpha * a_slow)
    return int(
        round(
            _clamp(
                raw,
                float(profile.confirm_min),
                float(profile.confirm_max),
            )
        )
    )


def _normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in {"d_only", "g_only", "d_or_g"}:
        raise ValueError("mode must be one of: D_only, G_only, D_or_G")
    return normalized


def _validate_profiles(profiles: Mapping[int, DMREDAProfile]) -> None:
    if not profiles:
        raise ValueError("profiles must not be empty")

    keys = sorted(profiles)
    if keys != list(range(keys[0], keys[-1] + 1)):
        raise ValueError("profile state keys must form a contiguous integer range")

    for state_id, profile in profiles.items():
        if profile.w1 <= 0 or profile.w2 <= 0:
            raise ValueError(f"profile {state_id}: w1 and w2 must be positive")
        if profile.w1 % 2 != 1:
            raise ValueError(f"profile {state_id}: w1 must be odd")
        if not profile.m_set:
            raise ValueError(f"profile {state_id}: m_set must not be empty")
        if any(int(v) <= 0 for v in profile.m_set):
            raise ValueError(f"profile {state_id}: all m_set values must be positive")
        if int(profile.m_base) not in tuple(int(v) for v in profile.m_set):
            raise ValueError(f"profile {state_id}: m_base must belong to m_set")
        if profile.confirm_min <= 0 or profile.confirm_base <= 0 or profile.confirm_max <= 0:
            raise ValueError(f"profile {state_id}: confirm lengths must be positive")
        if not (profile.confirm_min <= profile.confirm_base <= profile.confirm_max):
            raise ValueError(
                f"profile {state_id}: confirm_min <= confirm_base <= confirm_max must hold"
            )
        if profile.n_min <= 0:
            raise ValueError(f"profile {state_id}: n_min must be positive")
        if profile.refractory < 0 or profile.hold_up < 0 or profile.hold_down < 0:
            raise ValueError(f"profile {state_id}: refractory/hold values must be non-negative")
        for name in ("beta", "rho", "lam", "alpha", "g_ref", "eta", "e_floor"):
            value = float(getattr(profile, name))
            if not np.isfinite(value):
                raise ValueError(f"profile {state_id}: {name} must be finite")
        if profile.g_ref <= 0.0:
            raise ValueError(f"profile {state_id}: g_ref must be positive")
        if profile.e_floor <= 0.0:
            raise ValueError(f"profile {state_id}: e_floor must be positive")


def _validate_transitions(
    profiles: Mapping[int, DMREDAProfile],
    transitions: Mapping[int, RegimeTransition],
) -> None:
    unknown = set(transitions) - set(profiles)
    if unknown:
        raise ValueError(f"transitions reference unknown states: {sorted(unknown)}")

    for state_id, transition in transitions.items():
        if transition.up_threshold is not None and not np.isfinite(transition.up_threshold):
            raise ValueError(f"transition {state_id}: up_threshold must be finite")
        if transition.down_threshold is not None and not np.isfinite(transition.down_threshold):
            raise ValueError(f"transition {state_id}: down_threshold must be finite")


def _validate_result_shapes(result: DMREDAResult, n: int) -> None:
    for field_name, field_value in result.__dict__.items():
        if isinstance(field_value, np.ndarray) and field_value.shape != (n,):
            raise AssertionError(f"result field {field_name} has shape {field_value.shape}, expected {(n,)}")


def _debug_print(
    *,
    t: int,
    state: int,
    d: float,
    g: float,
    a: float,
    a_slow: float,
    pending: bool,
    confirmed: bool,
    refractory_remaining: int,
    current_m: int,
    current_confirm_len: int,
) -> None:
    print(
        f"[DMREDA] t={t:6d} state={state:d} "
        f"d={d: .6f} g={g: .6f} a={a: .6f} a_slow={a_slow: .6f} "
        f"pending={int(pending)} confirmed={int(confirmed)} "
        f"refractory_remaining={refractory_remaining:4d} "
        f"current_m={current_m:2d} current_confirm_len={current_confirm_len:3d}"
    )


def compute_warmup_samples(profiles: Mapping[int, DMREDAProfile]) -> int:
    max_w1 = max(profile.w1 for profile in profiles.values())
    max_w2 = max(profile.w2 for profile in profiles.values())
    max_confirm = max(profile.confirm_max for profile in profiles.values())
    return max(max_w1, max_w2) + max_confirm


def compute_dmreda_reference(
    signal: Sequence[float],
    *,
    regime_tick: int = 50,
    initial_state: int = 0,
    profiles: Optional[Mapping[int, DMREDAProfile]] = None,
    transitions: Optional[Mapping[int, RegimeTransition]] = None,
    d_bounds: Tuple[float, float] = (-5.0, 5.0),
    mode: str = "D_or_G",
    warmup_samples: Optional[int] = None,
    debug: bool = False,
    debug_every: int = 500,
) -> DMREDAResult:
    """Spec v0.5 causal reference implementation.

    State variables:
    - `mu`: trailing median baseline.
    - `e`: instantaneous L1 deviation from baseline.
    - `e1`: trailing energy sum over `w2`.
    - `e_baseline`: EMA of `e1`.
    - `d`: normalized deviation, clamped to `d_bounds`.
    - `g_raw`: finite-lag growth of `d`.
    - `g`: EMA-smoothed growth.
    - `r`: regime metric used only on regime ticks.
    - `a`: instantaneous aggressiveness from |g| / g_ref.
    - `a_slow`: slow aggressiveness committed on regime ticks.
    - `state`: regime FSM state.
    - `pending`/`confirmed`: 2-stage validation traces.
    """

    x = np.asarray(signal, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("signal must be 1-D")
    if x.size == 0:
        raise ValueError("signal must not be empty")
    if regime_tick <= 0:
        raise ValueError("regime_tick must be positive")
    if debug and debug_every <= 0:
        raise ValueError("debug_every must be positive when debug=True")

    profiles = dict(DEFAULT_PROFILES if profiles is None else profiles)
    transitions = dict(DEFAULT_TRANSITIONS if transitions is None else transitions)
    _validate_profiles(profiles)
    _validate_transitions(profiles, transitions)

    if initial_state not in profiles:
        raise ValueError(f"unknown initial_state: {initial_state}")
    if d_bounds[0] > d_bounds[1]:
        raise ValueError("d_bounds must satisfy low <= high")

    mode_normalized = _normalize_mode(mode)
    if warmup_samples is None:
        warmup_samples = compute_warmup_samples(profiles)
    if warmup_samples < 0:
        raise ValueError("warmup_samples must be non-negative")

    n = x.size
    mu = np.zeros(n, dtype=np.float64)
    e = np.zeros(n, dtype=np.float64)
    e1 = np.zeros(n, dtype=np.float64)
    e_baseline = np.zeros(n, dtype=np.float64)
    e_baseline_safe = np.zeros(n, dtype=np.float64)
    d = np.zeros(n, dtype=np.float64)
    g_raw = np.zeros(n, dtype=np.float64)
    g = np.zeros(n, dtype=np.float64)
    r = np.zeros(n, dtype=np.float64)
    a = np.zeros(n, dtype=np.float64)
    a_slow = np.zeros(n, dtype=np.float64)
    state = np.zeros(n, dtype=np.int64)
    m_eff = np.zeros(n, dtype=np.int64)
    confirm_len_eff = np.zeros(n, dtype=np.int64)
    pending = np.zeros(n, dtype=bool)
    confirmed = np.zeros(n, dtype=bool)
    event_active = np.zeros(n, dtype=bool)
    e_prefix = np.zeros(n + 1, dtype=np.float64)

    current_state = int(initial_state)
    initial_profile = profiles[current_state]
    current_m = int(initial_profile.m_base)
    current_confirm_len = int(initial_profile.confirm_base)

    min_state = min(profiles)
    max_state = max(profiles)

    up_counter = 0
    down_counter = 0
    refractory_remaining = 0

    pending_start = -1
    pending_elapsed = 0
    pending_area = 0.0
    pending_count = 0
    pending_confirm_len = current_confirm_len
    pending_th_d2 = initial_profile.th_d2
    pending_th_a = initial_profile.th_a
    pending_n_min = initial_profile.n_min
    pending_refractory = initial_profile.refractory

    event_times: List[int] = []

    for t in range(n):
        profile = profiles[current_state]

        mu[t] = _median_trailing(x, t, profile.w1)
        e[t] = abs(x[t] - mu[t])
        e_prefix[t + 1] = e_prefix[t] + e[t]
        e_start = max(0, t - profile.w2 + 1)
        e1[t] = e_prefix[t + 1] - e_prefix[e_start]

        if t == 0:
            e_baseline[t] = e1[t]
            r[t] = e[t]
            a_slow[t] = 0.0
        else:
            e_baseline[t] = _ema_update(e_baseline[t - 1], e1[t], profile.beta)
            r[t] = _ema_update(r[t - 1], e[t], profile.rho)
            a_slow[t] = a_slow[t - 1]

        e_baseline_safe[t] = max(e_baseline[t], profile.e_floor)
        d_raw = (e1[t] - e_baseline_safe[t]) / e_baseline_safe[t]
        d[t] = _clamp(d_raw, d_bounds[0], d_bounds[1])

        g_raw[t] = d[t] - d[t - current_m] if t >= current_m else 0.0
        g[t] = g_raw[t] if t == 0 else _ema_update(g[t - 1], g_raw[t], profile.lam)
        a[t] = _clamp(abs(g[t]) / max(profile.g_ref, 1e-9), 0.0, 1.0)

        if refractory_remaining > 0:
            refractory_remaining -= 1

        if pending_start >= 0:
            pending[t] = True
            pending_elapsed += 1
            pending_area += max(0.0, d[t] - pending_th_d2)
            pending_count += int(d[t] > pending_th_d2)

            if (pending_area > pending_th_a) and (pending_count >= pending_n_min):
                confirmed[t] = True
                event_active[t] = True
                event_times.append(t)
                refractory_remaining = pending_refractory
                pending_start = -1
                pending_elapsed = 0
                pending_area = 0.0
                pending_count = 0
            elif pending_elapsed >= pending_confirm_len:
                pending_start = -1
                pending_elapsed = 0
                pending_area = 0.0
                pending_count = 0

        if mode_normalized == "g_only":
            fast_trigger = g[t] > profile.th_g
        elif mode_normalized == "d_only":
            fast_trigger = d[t] > profile.th_d
        else:
            fast_trigger = (d[t] > profile.th_d) or (g[t] > profile.th_g)

        if pending_start < 0 and refractory_remaining == 0 and fast_trigger:
            pending_start = t
            pending[t] = True
            pending_elapsed = 0
            pending_area = 0.0
            pending_count = 0
            pending_confirm_len = current_confirm_len
            pending_th_d2 = profile.th_d2
            pending_th_a = profile.th_a
            pending_n_min = profile.n_min
            pending_refractory = profile.refractory

            pending_elapsed += 1
            pending_area += max(0.0, d[t] - pending_th_d2)
            pending_count += int(d[t] > pending_th_d2)

            if (pending_area > pending_th_a) and (pending_count >= pending_n_min):
                confirmed[t] = True
                event_active[t] = True
                event_times.append(t)
                refractory_remaining = pending_refractory
                pending_start = -1
                pending_elapsed = 0
                pending_area = 0.0
                pending_count = 0

        if ((t + 1) % regime_tick) == 0:
            transition = transitions.get(current_state, RegimeTransition())

            if transition.up_threshold is not None and r[t] > transition.up_threshold:
                up_counter += regime_tick
            else:
                up_counter = 0

            if transition.down_threshold is not None and r[t] < transition.down_threshold:
                down_counter += regime_tick
            else:
                down_counter = 0

            if transition.up_threshold is not None and up_counter >= profile.hold_up:
                current_state = min(current_state + 1, max_state)
                up_counter = 0
                down_counter = 0
            elif transition.down_threshold is not None and down_counter >= profile.hold_down:
                current_state = max(current_state - 1, min_state)
                up_counter = 0
                down_counter = 0

            profile = profiles[current_state]
            a_slow[t] = _ema_update(a_slow[t], a[t], profile.eta)

            if pending_start < 0:
                current_m = _select_m(profile.m_set, a_slow[t])
                current_confirm_len = _compute_confirm_len(profile, a_slow[t])

        state[t] = current_state
        m_eff[t] = current_m
        confirm_len_eff[t] = current_confirm_len

        if t + 1 < n:
            a_slow[t + 1] = a_slow[t]

        if debug and (t % debug_every == 0 or confirmed[t]):
            _debug_print(
                t=t,
                state=int(state[t]),
                d=float(d[t]),
                g=float(g[t]),
                a=float(a[t]),
                a_slow=float(a_slow[t]),
                pending=bool(pending[t]),
                confirmed=bool(confirmed[t]),
                refractory_remaining=int(refractory_remaining),
                current_m=int(current_m),
                current_confirm_len=int(current_confirm_len),
            )

    result = DMREDAResult(
        mu=mu,
        e=e,
        e1=e1,
        e_baseline=e_baseline,
        e_baseline_safe=e_baseline_safe,
        d=d,
        g_raw=g_raw,
        g=g,
        r=r,
        a=a,
        a_slow=a_slow,
        state=state,
        m_eff=m_eff,
        confirm_len_eff=confirm_len_eff,
        pending=pending,
        confirmed=confirmed,
        event_active=event_active,
        event_times=event_times,
        warmup_samples=warmup_samples,
        mode=mode_normalized,
    )
    _validate_result_shapes(result, n)

    confirmed_indices = np.flatnonzero(result.confirmed).tolist()
    if confirmed_indices != result.event_times:
        raise AssertionError("event_times must match confirmed indices")

    return result


def _self_test() -> None:
    print("Running dmreda_reference_clean self-test...")

    # Test 1: Constant zero signal should stay quiet.
    x0 = np.zeros(512, dtype=np.float64)
    r0 = compute_dmreda_reference(x0)
    assert r0.event_times == [], "constant signal should not confirm events"
    assert np.allclose(r0.d, -1.0, atol=1e-12), "constant signal should keep D at the normalized floor"
    assert np.allclose(r0.g, 0.0, atol=1e-12), "constant signal should keep G near zero"
    print("  [ok] constant signal sanity")

    # Test 2: Step signal should produce at least one event after warm-up.
    x1 = np.zeros(1024, dtype=np.float64)
    x1[400:] = 1.0
    r1 = compute_dmreda_reference(x1, mode="D_or_G")
    assert len(r1.event_times) >= 1, "step signal should confirm at least one event"
    assert all(t > r1.warmup_samples for t in r1.event_times), "step event should occur after warm-up"
    print("  [ok] step signal event detection")

    # Test 3: Random low-noise signal should not generate excessive events.
    rng = np.random.default_rng(7)
    x2 = rng.normal(0.0, 0.05, size=2048).astype(np.float64)
    r2 = compute_dmreda_reference(x2)
    assert len(r2.event_times) < int(len(x2) * 0.01), "noise sanity event count too high"
    print("  [ok] random noise sanity")

    # Test 4: Regime tick changes should keep types/shapes valid and may accelerate transitions.
    x3 = rng.normal(0.0, 0.3, size=2048).astype(np.float64)
    x3[700:1300] += 0.6
    r3_fast = compute_dmreda_reference(x3, regime_tick=10)
    r3_slow = compute_dmreda_reference(x3, regime_tick=100)
    assert r3_fast.state.shape == x3.shape and r3_slow.state.shape == x3.shape
    assert np.issubdtype(r3_fast.state.dtype, np.integer)
    assert np.issubdtype(r3_slow.state.dtype, np.integer)
    fast_changes = np.flatnonzero(r3_fast.state != r3_fast.state[0])
    slow_changes = np.flatnonzero(r3_slow.state != r3_slow.state[0])
    if fast_changes.size > 0 and slow_changes.size > 0:
        assert fast_changes[0] <= slow_changes[0], "smaller regime_tick should not delay first change"
    print("  [ok] regime_tick sanity")

    print("All self-tests passed.")


if __name__ == "__main__":
    _self_test()
