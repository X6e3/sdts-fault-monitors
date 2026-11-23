# BASELINE2: two strengthened baselines on validation 3's block (plan, 2026-11-23)

Status: APPROVED by Can Koç on 2026-11-23 for the DEV grid ("onaylıyorum adamım başlat"). The block runs only after the status
line reads "Status: FROZEN" and quotes the sha256 of the chosen configurations.

## 0. Why

Review r2 (2026-11-23) read the code of the first comparison (BASELINE-PLAN.md, block 9438dffa) and found two
baselines handicapped by their implementation, which the code confirms:
- B4, the interval observer, never intersects its range with the measurement; IM does.
- B1, constrained zonotopes, reduces the lifted matrix [G; A] by a Girard score with the constraint rows unscaled;
  on DEV it was not monotone in memory ("not explained here").
This plan gives both their fix and tests whether the paper's claims still hold. It does not touch the first
comparison: its plan, code, rows and verdicts stay as they are, and the paper reports both.

## 1. Methods (`diag/baselines_strong.py`)

- **B1s**: B1 with each equality row of (A, b) scaled to unit infinity norm before the lifted generator reduction.
  The set is unchanged; only the Girard score sees the constraint rows on one scale.
- **B4s**: B4 with its a_s-range intersected with [z − σ, z + σ] after every check, as IM does.
- Both run in plain binary64 like B1 to B4, with the same prior and decision. B1 and B4 themselves are unchanged
  (subclasses; `baselines.py` and `baselines_cz.py` are not edited).
- Not strengthened here, and said so in the paper: B2's other strip weights, B3, Scott's LP rescaling at block scale
  (48 ms per sample on DEV), and similarity transforms that put an interval observer in cooperative form.

## 2. Data

- DEV: the 1,400 rows of the first comparison (1,320 comparison rows and 80 edge-noise healthy rows).
- Block: validation 3's 9,600 runs (seeds 440400–440599), whose results for WM, IM and the first baselines are known.
  This is a fixed comparison on a used block, not a new validation, as before.

## 3. Grid and tuning (`diag/baselines2_run.py`, reusing `baselines_run.py`'s grid runner, scoring and rule)

- B1s: (n_c, o) in (2, 1), (1, 2), (3, 1), (4, 2), (4, 8), (16, 2), (16, 8), (64, 2), (64, 8); fifo; prior box+err
  (the prior that helped B1 most on DEV). 9 configurations.
- B4s: the 45 gains of B4's grid.
- Rule, as in the first comparison: per family and budget, the configuration with the smallest paired lag on DEV
  among those with no alarm on an admissible row and none before t*. M1: at most 42 reals. M2: no upper limit (as the
  first comparison's tuning did; memory is reported).

## 4. Hypotheses (fixed now; seed bootstrap, 2,000 draws over the 200 seeds, `random.Random(20261123)`)

Each on the paired lag over validation 3's paired events, ours minus the baseline's; **supported** if the upper end of
the 95 % interval is below 0.
- **H-S1**: WM's paired lag is below B1s@M2's.
- **H-S2a**: TS's paired lag is below B1s@M1's.
- **H-S2b**: TS's paired lag is below B4s@M1's.

## 5. Reported either way

For each chosen configuration: D_paired against IM, misses, detections at t*, alarms on admissible runs and before
t* (a soundness finding of that implementation, reported), memory, time per sample; and the same for the first
comparison's B1 and B4 on the same rows. If a hypothesis is not supported, the paper says so and no longer claims that
every baseline lagged; the abstract and the highlights follow the result.

## 6. Order

1. Can approves this plan (status line). 2. DEV grid on Arch, then the tuning rule → `chosen.json`. 3. The plan is
frozen: status FROZEN with the sha256 of `chosen.json`, committed. 4. The block on Arch (only the chosen
configurations). 5. Score; a dated record with the verdicts as they come.

Estimated cost on Arch (14 workers): DEV about 30–40 min, block about 1–1.5 h, after the oracle margin check ends.
