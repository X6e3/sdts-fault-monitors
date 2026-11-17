"""Sensor-only score traces for the frozen thermal protocol's two baselines."""
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
