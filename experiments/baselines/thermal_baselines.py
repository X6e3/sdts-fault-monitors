"""Sensor-only baselines for thermal protocol v2 with addendum A1.

Variants (A1.1, A1.3), all calibrated by A1.2 (per arm, 1.05 x the TRAIN healthy maximum on k >= 300):
  cusum_a0          primary    two-sided CUSUM on first differences, allowance 0
  cusum_rhoA        secondary  the same with allowance RHO_A
  dmreda_native     primary    the unchanged core's fast gate + confirmation; one scale s on th_d, th_g,
                               th_d2, th_a of every profile; an alarm is a confirmed event
  dmreda_fast_gate  ablation   max(d/th_d, g/th_g) at the active profile, no confirmation
"""
import dataclasses
import hashlib
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generators"))
import thermal as T
from vendor import dmreda_reference_clean as core

CORE_SHA256 = "0b8bffc7466b7dc67f353415a610edc668c50ac21db0d239fe885c49bbceef3e"


@dataclass(frozen=True)
class ScoreTrace:
    values: np.ndarray
    evaluate_from: int


def verify_reference():
    digest = hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest()
    if digest != CORE_SHA256:
        raise ValueError("DMREDA reference differs from the pre-registered file")
    return digest


def _samples(y):
    signal = np.asarray(y, dtype=float)
    if signal.ndim != 1 or signal.size == 0 or not np.all(np.isfinite(signal)):
        raise ValueError("expected a nonempty, finite sensor sequence")
    return signal


def dmreda_score(y):
    """Score the reference D-or-G trigger in units of its active profile thresholds."""
    result = core.compute_dmreda_reference(_samples(y))
    # The reference stores the updated regime at t, after scoring the sample.
    used_regime = np.concatenate(([0], result.state[:-1]))
    d_threshold = np.array([core.DEFAULT_PROFILES[i].th_d for i in used_regime])
    g_threshold = np.array([core.DEFAULT_PROFILES[i].th_g for i in used_regime])
    score = np.maximum(0.0, np.maximum(result.d / d_threshold, result.g / g_threshold))
    return ScoreTrace(score, max(T.T_WARM, result.warmup_samples))


def cusum_score(y, *, allowance):
    """Two-sided CUSUM on first differences, with a supplied allowance in °C/sample."""
    if not math.isfinite(allowance) or allowance < 0:
        raise ValueError("CUSUM allowance must be finite and nonnegative")
    signal = _samples(y)
    scores = np.zeros_like(signal)
    positive = negative = 0.0
    for k, difference in enumerate(np.diff(signal), start=1):
        positive = max(0.0, positive + difference - allowance)
        negative = max(0.0, negative - difference - allowance)
        scores[k] = max(positive, negative)
    return ScoreTrace(scores, T.T_WARM)


def training_threshold(healthy_traces):
    """Apply the protocol's 5% margin to supplied, eligible healthy TRAIN scores."""
    maxima = []
    for trace in healthy_traces:
        scores = trace.values[trace.evaluate_from:]
        if scores.size == 0 or not np.all(np.isfinite(scores)):
            raise ValueError("each training trace must contain finite eligible scores")
        maxima.append(float(np.max(scores)))
    if not maxima:
        raise ValueError("expected healthy training traces")
    return 1.05 * max(maxima)


def first_alarm(trace, threshold):
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("threshold must be finite and nonnegative")
    alarms = np.flatnonzero(trace.values[trace.evaluate_from:] > threshold)
    return trace.evaluate_from + int(alarms[0]) if alarms.size else None


# ---- addendum A1 -------------------------------------------------------------------------------------

EVAL_FROM = T.T_WARM
SCAN_RATIO = 0.995
VARIANTS = {"cusum_a0": "primary", "cusum_rhoA": "secondary",
            "dmreda_native": "primary", "dmreda_fast_gate": "ablation"}


def scaled_profiles(s):
    """The default profiles with their four threshold levels multiplied by s (A1.3)."""
    if not math.isfinite(s) or s <= 0:
        raise ValueError("scale must be finite and positive")
    return {i: dataclasses.replace(p, th_d=p.th_d * s, th_g=p.th_g * s, th_d2=p.th_d2 * s, th_a=p.th_a * s)
            for i, p in core.DEFAULT_PROFILES.items()}


def native_events(y, s):
    """Confirmed DMREDA events (all samples) at scale s."""
    return core.compute_dmreda_reference(_samples(y), profiles=scaled_profiles(s)).event_times


def _has_event(y, s):
    return any(t >= EVAL_FROM for t in native_events(y, s))


def fast_gate_bound(y):
    """s_fast: max over all samples of max(d/th_d, g/th_g) at the native profile."""
    return float(np.max(dmreda_score(y).values))


def native_statistic(y):
    """s* of A1.3: the largest scale with a confirmed event at a sample >= 300 (scan, then bisection)."""
    s_fast = fast_gate_bound(y)
    if s_fast <= 0:
        return 0.0
    top, floor = 2.0 * s_fast, 1e-3 * s_fast
    if _has_event(y, top):
        raise RuntimeError(f"event at 2*s_fast = {top}: the A1.3 scan bound does not hold for this run")
    above, s = top, top * SCAN_RATIO
    while s >= floor:
        if _has_event(y, s):
            lo, hi = s, above            # event at lo, none at hi
            while (hi - lo) > 1e-6 * lo:
                mid = 0.5 * (lo + hi)
                if _has_event(y, mid):
                    lo = mid
                else:
                    hi = mid
            return lo
        above, s = s, s * SCAN_RATIO
    return 0.0


def score_trace(variant, y):
    if variant == "cusum_a0":
        return cusum_score(y, allowance=0.0)
    if variant == "cusum_rhoA":
        return cusum_score(y, allowance=T.RHO_A)
    if variant == "dmreda_fast_gate":
        return dmreda_score(y)
    raise ValueError(f"{variant} has no score trace")


def statistic(variant, y):
    """The quantity A1.2 takes the TRAIN maximum of."""
    if variant == "dmreda_native":
        return native_statistic(y)
    trace = score_trace(variant, y)
    return float(np.max(trace.values[EVAL_FROM:]))


def alarm_times(variant, y, threshold):
    """All samples k >= 300 at which the variant alarms with this threshold (A1.4)."""
    if variant == "dmreda_native":
        return [t for t in native_events(y, threshold) if t >= EVAL_FROM]
    trace = score_trace(variant, y)
    return (EVAL_FROM + np.flatnonzero(trace.values[EVAL_FROM:] > threshold)).tolist()


def outcome(variant, y, threshold, t_f=None):
    """First alarm, pre-onset alarm and A1.4 'flagged' (some alarm at k >= t_f)."""
    times = alarm_times(variant, y, threshold)
    out = {"first_alarm": times[0] if times else None, "alarm": bool(times)}
    if t_f is not None:
        out["pre_onset_alarm"] = any(t < t_f for t in times)
        out["flagged"] = any(t >= t_f for t in times)
        after = [t for t in times if t >= t_f]
        out["first_alarm_after_onset"] = after[0] if after else None
    return out
