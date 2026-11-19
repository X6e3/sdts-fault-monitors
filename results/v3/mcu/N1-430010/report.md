# Neon — Task N1: Verification of Open MCU Numbers (19 Nov 2026)

**Checkout (`OBSERVED`):** `/home/x6e3/Research/sdts-v3-a8-0e28951`, `HEAD = 0e28951f7f7a8103387b84b1a5df8e4925238d1c`, `diag3_cw.py` SHA-256 `e88e2b78a127e49e722edfb2f4e1115ad584c5e30541811b2e833215881763d0`.
**Environment (`OBSERVED`):** Python `3.12.13`, NumPy `2.5.5`, SciPy `1.18.1`, HiGHS `1.12.0` (`scipy.optimize._highspy._core._Highs`, `presolve="off"`).
**Command (`OBSERVED`):** `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -B ~/Research/sdts-runs/v3-neon/N1/run_n1.py` (single process, `162.71 s`).
**Primary dataset (`OBSERVED`):** DEV run `430010` (`drift_0.0005`, `E0`, `ramp`, `uniform`, `t* = 695`), variants `F` (`W=256, B=16, K=64`, `0` evictions, `detect=695`, `cert64_margin=-0.28556 mC`) and `N` (`detect=695`, `cert64_margin=-0.28556 mC`). Peak edge-noise LU check on DEV run `430070` (`healthy`, `E0`, `ramp`, `edge`, `t = 300..359`). Validation seeds `440000+` untouched.
**Data artifact:** `~/Research/sdts-runs/v3-neon/N1/n1_results.json`.

---

## Executive Summary (Check / Correction Table)

| Item | Earlier Unverified Estimate | Neon N1 Result | Verdict |
|---|---|---|---|
| **1. Dense `B⁻¹` (`float32`)** | `669 KB` (`m = 409`) | `669,124 B` = **`653.44 KiB`** (`669.12 kB`) at `m=409`; **`773.54 KiB`** (`792.10 kB`) at edge `m=445`; **`130.82 KiB`** at `N` `m=183` (`OBSERVED`) | Arithmetic confirmed (decimal kB); added binary KiB & edge `m=445` |
| **2. Sparse LU fill & SRAM** | `100–140 KB` (`E`, `m ≤ 409`), `60–80 KB` (`N`, `m ≤ 183`) | Real `COLAMD` LU over `1,842` bases (`430010` `t=300..695`): `F` fill **`3.04×–3.40×`** (`nnz(L+U) ≤ 3,064`), edge `m=445` fill **`2.55×–3.06×`** (`≤ 3,279`), `N` fill **`1.74×–1.92×`** (`≤ 818`) (`OBSERVED`). Static `f32` solver SRAM: **`84.1 KiB`** (`F` `m=409`), **`88.2 KiB`** (`F` edge `m=445`), **`45.9 KiB`** (`N` `m=183`) (`INFERRED`) | **Corrected downward** (`COLAMD` beats `MMD` by `~32–55%`); `~105–115 KiB` incl. transient refactor scratch |
| **3a. Pure `float32` cert (`u=2⁻²⁴`)** | `~1.95 mC` alarm, `~15.6 mC` fold (`E`) | `F` at `t=695`: `up` **`+3.121 mC`**, `dn` **`+2.005 mC`** (margin flips `-0.286` → **`+2.835 mC`**). Across all `1,050` fold LPs (`42` dirs): median `0.153`, p95 **`10.72`**, **max `40.47 mC`** (`N`: alarm `+0.511 mC`, fold max **`8.14 mC`**) (`OBSERVED`) | **Confirmed unusable & corrected upward (`2.6×` worse worst-case fold)** |
| **3b. Mixed precision (`f32` → `f64`/`int64`)** | `~0.0012 mC` | `y_f32` checked in `f64`: `0.00118 mC` at `t=695 up`, but up to **`0.0158 mC`** on folds (`OBSERVED`). Real `f32`-data solve (`tol=1e-6`): raw fold max `0.0134 mC`, **`f64` basis-refined fold max `0.00092 mC`** (`< PAD`); full online replay detects at **`695` (`-0.28548 mC`, `0` raises)** (`OBSERVED`). Exact `int64` `Q30×Q24` cert: **`0` soundness violations**, max `61` bits, alarm `+0.0041 mC`, fold max **`0.0118 mC`** (`OBSERVED`) | **Nuanced & verified end-to-end**: raw `f32` duals reach `0.016 mC` (not `0.0012`); `f64` basis refine hits `< 0.001 mC`; `int64` works at `~0.004–0.012 mC` |
| **4. Warm-start iterations (HiGHS)** | Cold `E`: `278` med / `458` max step, `~405` fold; warm unmeasured | Full `t=1..695` cold `F`: **`387` med / `720` max** step, **`378` med / `530` max** fold (`16,157` med/fold). Warm dual (`2` bases): step **median `0`, mean `0.87`, p95 `3`, max `62`** (`~400×` cut). Warm dual `11.3°` TSP fold: **median `0`, mean `3.36` (`d1..d41`), total `557` med / `678` max per 42-LP fold** (`29×` cut, beats primal TSP!) (`OBSERVED`) | **Cold corrected upward on full run; warm start measured directly — `400×` step & `29×` fold cuts** |

---

## 1. Dense `B⁻¹` Memory (`OBSERVED`)

Exact byte counts (`m² × 4` for `float32`, `m² × 8` for `float64`), from `n1_results.json["item1_dense_Binv"]`:

| Case | `m` | `float32` bytes | `float32` KiB (`÷1024`) | `float32` kB (`÷1000`) | `float64` KiB (`÷1024`) |
|---|---:|---:|---:|---:|---:|
| `F` (`430010` observed peak) | `373` | `556,516` | `543.47` | `556.52` | `1,086.95` |
| `F` (DEV max) | `409` | `669,124` | `653.44` | `669.12` | `1,306.88` |
| `F` (`edge`-noise max) | `445` | `792,100` | `773.54` | `792.10` | `1,547.07` |
| `N` (DEV max) | `183` | `133,956` | `130.82` | `133.96` | `261.63` |

Dense `B⁻¹` for `F` (`653–774 KiB` in `float32`) exceeds standard Cortex-M4/M33 internal SRAM (`192–512 KiB`) and is ruled out for `F`.

---

## 2. Real Sparse LU Fill-In and Itemized SRAM Budget

### 2.1 Measured `splu` Fill-In (`OBSERVED`)
Every HiGHS optimal basis `B` (`m × m`, built directly from `h.getBasis()` basic columns and slack unit columns, verified `|basic_cols| + |basic_rows| == m`) was factorized with `scipy.sparse.linalg.splu` over **all `792` step LPs and all `1,050` fold LPs** of `430010` (`t = 300..695`), plus `60` step LPs at edge-noise peak on `430070` (`t = 300..359`):

| Dataset (`n` bases) | `m` (med/max) | `nnz(A)` (med/max) | `nnz(B)` (med/max) | `COLAMD` `nnz(L+U)` (med/p95/max) | `COLAMD` fill (med/max) | `MMD_AT_PLUS_A` `nnz(L+U)` (med/max) | `NATURAL` `nnz(L+U)` (med/max) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `430010` `F` step (`792`) | `364.5 / 381` | `1,552 / 1,612` | `874 / 924` | **`2,658 / 2,816 / 2,992`** | `3.04× / 3.39×` | `3,434 / 4,208` (`4.80×`) | `2,737 / 3,912` |
| `430010` `F` fold (`1,050`) | `375 / 381` | `1,597 / 1,612` | `901 / 927` | **`2,771 / 2,894 / 3,064`** | `3.07× / 3.40×` | `3,661 / 4,496` (`4.90×`) | `2,878 / 3,895` |
| `430070` `F` edge (`60`) | `437.5 / 445` | `1,735 / 1,772` | `1,067 / 1,089` | **`2,721 / 3,127 / 3,279`** | `2.55× / 3.06×` | `4,444 / 4,954` (`4.64×`) | — |
| `430010` `N` step (`792`) | `126 / 141` | `1,078 / 1,132` | `396 / 444` | **`684 / 757 / 790`** | `1.74× / 1.86×` | `1,295 / 1,938` (`4.56×`) | `1,798 / 2,222` |
| `430010` `N` fold (`1,050`) | `132 / 141` | `1,111 / 1,132` | `412 / 447` | **`728 / 780 / 818`** | `1.77× / 1.92×` | `1,377 / 2,088` (`4.90×`) | `1,870 / 2,348` |

**Key observation (`OBSERVED`):** Unsymmetric column ordering (`COLAMD`, the closest standard proxy to Markowitz pivoting) produces **32% less fill than `MMD_AT_PLUS_A` on `F`** and **55–61% less fill on `N`**. Even under full-cap `edge` noise (`m = 445`), `nnz(L+U)` stays `≤ 3,279` (`fill ≤ 3.06×`), because bound-active measurements remove `(ac, as)` columns from the basis.

### 2.2 Itemized Cortex-M Static Solver SRAM Model (`INFERRED`)
Using `uint16` indices (`2 B`), `1.25×` static `L+U` capacity headroom over scaled/observed `COLAMD` max, `50`-pivot Forrest–Tomlin / PFI eta buffer (`45` nnz/pivot for `F` DEV, `55` for `F` edge, `30` for `N`), `5` col + `7` row simplex vectors, and `2` saved warm-start basis arrays (`up` + `dn`), from `n1_results.json["item2_sram_budgets_estimated"]`:

| Configuration | `A` CSC | `L+U` + perms | Eta (`50` piv) | Vectors | `2` Warm Bases | **Total Static SRAM** |
|---|---:|---:|---:|---:|---:|---:|
| `F` DEV (`m=409, n=643`, `f32`) | `12.4 KiB` | `29.4 KiB` | `13.4 KiB` | `26.8 KiB` | `2.1 KiB` | **`84.1 KiB`** (`86.1 kB`) |
| `F` edge (`m=445, n=679`, `f32`) | `11.7 KiB` | `29.2 KiB` | `16.3 KiB` | `28.7 KiB` | `2.2 KiB` | **`88.2 KiB`** (`90.3 kB`) |
| `F` DEV (`m=409, n=643`, `f64`) | `19.8 KiB` | `45.8 KiB` | `22.2 KiB` | `50.6 KiB` | `2.1 KiB` | **`140.4 KiB`** (`143.8 kB`) |
| `N` DEV (`m=183, n=417`, `f32`) | `10.2 KiB` | `10.7 KiB` | `9.0 KiB` | `14.9 KiB` | `1.2 KiB` | **`45.9 KiB`** (`47.0 kB`) |
| `N` DEV (`m=183, n=417`, `f64`) | `16.4 KiB` | `16.3 KiB` | `14.8 KiB` | `28.1 KiB` | `1.2 KiB` | **`76.8 KiB`** (`78.7 kB`) |

**Caveat (`INFERRED`):** Adding `~15–25 KiB` of transient refactorization workspace + window measurement ring buffer (`< 2 KiB`) places total `float32` `F` solver SRAM around **`~105–115 KiB`** (and `float64` `F` around **`~165–175 KiB`**) — fitting comfortably inside a `256 KiB` Cortex-M4F/M33 or `512 KiB` Cortex-M7.

---

## 3. `float32`, Mixed-Precision, and `int64` Certificates on `430010` (`OBSERVED`)

### 3.1 Pure `float32` `certified_max(harden=True)` (`u = 2⁻²⁴`)
True `float64` certified alarm margin on `430010` (`t = 695`) is **`-0.28556 mC`**.

| Variant | Alarm `t=695` `up` err | Alarm `t=695` `dn` err | Resulting Alarm Margin | Step LPs `t=300..695` (med / p95 / max) | All `1,050` Fold LPs (med / p95 / max) |
|---|---:|---:|---:|---:|---:|
| `F` (`u=2⁻²⁴` formula) | **`+3.121 mC`** | `+2.005 mC` | **`+2.835 mC`** (lost) | `0.374 / 2.877 / 4.144 mC` | `0.153 / 10.720 /` **`40.470 mC`** |
| `F` (actual `f32` arith) | **`+3.122 mC`** | `+2.006 mC` | **`+2.836 mC`** (lost) | `0.374 / 2.878 / 4.146 mC` | `0.153 / 10.726 /` **`40.482 mC`** |
| `N` (`u=2⁻²⁴` formula) | **`+0.511 mC`** | `+0.427 mC` | **`+0.226 mC`** (lost) | `0.160 / 0.510 / 0.885 mC` | `0.095 / 2.172 /` **`8.141 mC`** |

Breakdown of the `F` worst-case fold (`40.47 mC`): `col_err = 39.47 mC` (`97.5%`), `harden_err = 0.94 mC` (`2.3%`), `outer_err = 0.056 mC`. The previous `15.6 mC` figure only sampled the last of the `42` fold directions; across all `42` directions the worst-case fold overhead is **`40.47 mC`**. Pure `float32` certification is decisively unusable.

### 3.2 Mixed Precision (`float32` Solve → `float64` Certificate) and Exact `int64` Certificate
Measured gap `cert_bound - v64_exact` (`mC`, positive = sound loosening) on `430010` (`F`):

| Method | Alarm `t=695` (`up` / `dn`) | Alarm Margin (`mC`) | Step LPs (med / p95 / max) | Fold LPs (med / p95 / max) |
|---|---:|---:|---:|---:|
| Exact `f64` duals rounded to `f32` → `f64` cert | `0.00118 / 0.00110` | `-0.28437` | `0.00026 / 0.00113 / 0.00627` | `0.00018 / 0.00499 /` **`0.01580`** |
| `f32`-data HiGHS (`tol=1e-6`), raw `f32` duals → `f64` cert | `0.00130 / 0.00087` | `-0.28425` | `0.00035 / 0.00139 / 0.00288` | `0.00028 / 0.00470 / 0.01344` |
| `f32`-data HiGHS (`tol=1e-6`) + **`f64` `B^T π = c_B`** → `f64` cert | **`0.00007 / 0.00002`** | **`-0.28549`** | `0.00000 / 0.00060 / 0.00283` | `0.00000 / 0.00017 /` **`0.00092`** |
| `f32`-data HiGHS (`tol=1e-5`), raw `f32` duals → `f64` cert | `0.00130 / 0.00087` | `-0.28425` | `0.00037 / 0.01333 /` **`0.03111`** | `0.00032 / 0.00470 / 0.01344` |
| `f32`-data HiGHS (`tol=1e-5`) + **`f64` `B^T π = c_B`** → `f64` cert | **`0.00007 / 0.00002`** | **`-0.28549`** | `0.00000 / 0.01294 / 0.03096` | `0.00001 / 0.00077 / 0.00276` |
| **Exact `int64` `Q30×Q24` cert** (on `f64` duals, `0` violations, max `61` bits) | `0.00407 / 0.00422` | `-0.28149` | `0.00433 / 0.00487 / 0.01061` | `0.00064 / 0.00576 / 0.01184` |

*(Note: on `N`, exact `int64` `Q30×Q24` had `0` soundness violations, max `61` bits, alarm gap `0.00258 / 0.00273 mC`, step max `0.00369 mC`, fold max `0.00544 mC`.)*

### 3.3 Full End-to-End Mixed-Precision Online Replay of `430010` (`OBSERVED`)
Every step LP and every fold LP (`t = 1..695`) solved on `float32`-quantized LP data at relaxed tolerance, with every fold & alarm certified in `float64` against exact `float64` data (`n1_results.json["mixed_precision_online_replays_430010"]`):

| Replay Config | `detect` | `margin@695` (`mC`) | Folds Raised (`> PAD`) | Max Raise (`mC`) | Solver Fallbacks |
|---|---:|---:|---:|---:|---:|
| `tol=1e-6`, raw `f32` duals | **`695`** | `-0.28425` | `95` | `0.0181` | `0` |
| `tol=1e-6`, **`f64` basis refine** | **`695`** | **`-0.28548`** | **`0`** | **`0.0`** | `0` |
| `tol=1e-5`, raw `f32` duals | **`695`** | `-0.28400` | `93` | `0.0180` | `0` |
| `tol=1e-5`, **`f64` basis refine** | **`695`** | **`-0.28522`** | **`0`** | **`0.0`** | `0` |

**Caveat (`HYPOTHESIS`):** HiGHS on `float32`-quantized data still executes internal pivots in `float64` arithmetic; an authentic `float32` embedded simplex kernel may experience slightly larger pivot/basis drift on `0.02–0.04 mC` tight rows (`430009`, `430026`). Even then, `float64` basis refinement (`B^T π = c_B`, one sparse solve per LP) recovers nearly exact multipliers from any near-optimal basis.

---

## 4. Warm-Start vs Cold-Start Simplex Iterations in HiGHS 1.12.0 (`OBSERVED`)

Measured directly with `_core._Highs` (`presolve="off"`) on `430010` (`t = 1..695`, `1,390` step LPs, `1,334` non-fold warm-started step transitions, `27` folds × `42` = `1,134` fold LPs). Every warm-started basis mapped cleanly (`1,334 / 1,334`, `0` mapping failures) and matched cold-start objectives (`max_obj_diff = 3.24e-8` step, `1.10e-7` fold in `F`; `4.04e-9` step, `5.64e-8` fold in `N`):

### 4.1 Consecutive Step LPs (`t − 1 → t`)

| Mode (`430010`, `t = 1..695`) | `F` iters (med / mean / p95 / max) | `N` iters (med / mean / p95 / max) |
|---|---:|---:|
| Cold-start dual simplex (`n=1,390`) | `387 / 346.8 / 498 / 720` | `109 / 107.4 / 173.6 / 326` |
| **Warm dual, separate `up`/`dn` bases (`n=1,334`)** | **`0 / 0.87 / 3 / 62`** | **`0 / 0.71 / 2 / 43`** |
| — when `z_{t-1}` dropped (`n=1,198`, `90%`) | **`0 / 0.26 / 1 / 22`** | **`0 / 0.39 / 1 / 37`** |
| — when `z_{t-1}` kept (`n=136`, `10%`) | `1 / 6.20 / 36.5 / 62` | `1 / 3.60 / 16.3 / 43` |
| Warm primal, separate `up`/`dn` bases (`n=1,334`) | `0 / 1.79 / 10 / 107` | `0 / 1.61 / 10.4 / 102` |
| Warm dual, single shared basis `up(t)→dn(t)` (`n=695`) | `36 / 38.5 / 75 / 119` | `26 / 28.9 / 67 / 201` |

### 4.2 Fold LPs (`42` Directions Across `27` Folds)

| Fold Strategy (`27` folds, `1,107` `d_1..d_41` solves) | `F` per-LP `d_1..d_41` (med / mean / p95 / max) | `F` total / 42-LP fold (med / p95 / max) | `N` per-LP `d_1..d_41` (med / mean / p95 / max) | `N` total / 42-LP fold (med / p95 / max) |
|---|---:|---:|---:|---:|
| Cold-start dual (`42` fresh solves) | `378 / 384.9 / 434 / 530` | `16,157 / 16,603 / 16,906` | `111 / 113.0 / 140 / 166` | `4,742 / 5,058 / 5,124` |
| Warm dual, default `D0` order | `13 / 15.6 / 35 / 62` | — | `14 / 13.8 / 23 / 34` | — |
| **Warm dual, `11.3°` spherical TSP order** | **`0 / 3.36 / 17 / 44`** | **`557 / 651 / 678`** | **`0 / 3.38 / 15 / 29`** | **`264 / 325 / 366`** |
| Warm primal, `11.3°` spherical TSP order | `0 / 3.96 / 22 / 373` (`1` stall) | `573 / 642 / 927` | `0 / 3.75 / 22 / 115` (`1` stall) | `275 / 346 / 405` |

**Key findings (`OBSERVED` & `INFERRED`):**
1. **Consecutive step warm start cuts mean pivots by `~400×` in `F`** (`346.8 → 0.87` iters/LP, median `0`, p95 `3`), provided `up` and `dn` maintain two separate saved basis arrays (`2.1 KiB`). Sharing one basis across `up → dn` degrades performance `44×` (`38.5` mean pivots).
2. **Correction to prior advisor's prediction on fold simplex mode:** **Warm Dual Simplex along the `11.3°` spherical TSP tour beat Warm Primal Simplex** on both speed (`mean 3.36, max 44` vs `mean 3.96, max 373`) and reliability (`0` non-optimal statuses vs `1` `HighsModelStatus.kUnknown` stall at `t = 641, pos = 9, dir = 30` in both `F` and `N`).
3. **Single-engine MCU implication (`INFERRED`):** One embedded **Dual Simplex** kernel handles both step updates (`~1` pivot avg) and full 42-direction folds (`~557` pivots total = `29×` less than cold start, of which `~419` pivots are solely the cold start on `d_0`!). Warm-starting `d_0` from the step basis (`up(t)`) should compress the entire 42-direction fold further toward `~150–200` pivots total (`HYPOTHESIS`, not yet measured).
