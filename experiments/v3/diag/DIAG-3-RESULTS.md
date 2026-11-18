# Diagnosis 3: results, phase 1 (DEV only; 2026-11-18)

**Plan:** `DIAG-3-PLAN.md`, commit `c16f7be`, with the phase-1 criteria fixed before any result.

**Run:**
- `diag3.py` at `c16f7be` on Arch, clean tree, 35 jobs, 11:58–12:02.
- Outputs are in `results/v3/diag3/run1-c16f7be/`: one JSON per run and variant, the margins at every step (`.npy`),
  `summary.json`, `meta.json` and `run.log`.

**Freeze 1** and seeds 440200+ are untouched. These five runs were chosen for the diagnosis; nothing here estimates
the gain on DEV as a whole.

**In short:**
- **Phase 1 passes for S128 and S256.**
- **S256 detects at t* in all five runs,** the oracle's time. This is a window of 256–272 samples with one common
  ambient path, folded into cyl16p's 42 directions.
- **Smoothing is what makes it work.** With the filter fold, 430027 is never recovered at any W.

## Checks (OBSERVED, all pass)

- **W = ∞** (the full-history LP) detects at t* in all 5 runs. Its margins at t* equal arm A's: −4.186, −4.101,
  −4.625, −0.389 and −4.509 mC.
- **No variant detects before t*** in any run.
- **LP solver:**
  - Every LP was solved.
  - 22 of the 174,808 LPs needed a fallback method.
  - 10 of those were in the 2,550-variable full-history LP of 430000; no window variant needed more than 2.

## Detection times (OBSERVED)

| run | t* | cyl16p | ∞ | S64 | S128 | S256 | F64 | F128 | F256 |
|---|---|---|---|---|---|---|---|---|---|
| 430007 | 673 | 792 | 673 | **673** | **673** | **673** | 745 | 673 | 673 |
| 430027 | 579 | 1429 | 579 | 1429 | **579** | **579** | 1429 | 1429 | 1429 |
| 430000 | 849 | 2048 | 849 | 2042 | **849** | **849** | 2048 | 849 | 849 |
| 430010 | 695 | 3575 | 695 | 3539 | 3539 | **695** | 3539 | 3539 | 3449 |
| 430019 (control) | 393 | 393 | 393 | 393 | 393 | 393 | 393 | 393 | 393 |

**Margin at t*** (mC; negative = detected):

| run | A | S64 | S128 | S256 | F256 |
|---|---|---|---|---|---|
| 430007 | −4.186 | −2.631 | −4.110 | −4.186 | −4.186 |
| 430027 | −4.101 | 0.513 | −1.423 | −2.190 | 0.897 |
| 430000 | −4.625 | 1.193 | −2.146 | −4.625 | −4.625 |
| 430010 | −0.389 | 2.250 | 2.133 | −0.286 | 0.563 |
| 430019 | −4.509 | −4.493 | −4.508 | −4.509 | −4.509 |

## The criteria (as fixed in the plan)

**R** = (t_cyl16p − t_det) / (t_cyl16p − t*), the share of cyl16p's lag recovered:

| variant | 430007 | 430027 | 430000 | 430010 | R ≥ 0.5 in ≥ 3 of 4 | none before t* | control at t* | passes |
|---|---|---|---|---|---|---|---|---|
| S64 | 1.000 | 0.000 | 0.005 | 0.013 | no | yes | yes | **no** |
| S128 | 1.000 | 1.000 | 1.000 | 0.013 | yes | yes | yes | **yes** |
| S256 | 1.000 | 1.000 | 1.000 | 1.000 | yes | yes | yes | **yes** |

**The filter variants (no criterion; they measure what smoothing is worth):**

| variant | 430007 | 430027 | 430000 | 430010 |
|---|---|---|---|---|
| F64 | 0.395 | 0 | 0 | 0.013 |
| F128 | 1 | 0 | 1 | 0.013 |
| F256 | 1 | 0 | 1 | 0.044 |

## What it shows (INFERRED)

- **Smoothing decides the two runs Sol flagged.**
  - In 430027 and 430010, arm E failed in DIAG-1: the exact recursion from cyl16p's own summary, with every later
    measurement.
  - In those two runs only the smoothing fold recovers t*, at W = 128 for 430027 and at W = 256 for 430010.
  - The filter fold, a B-step block update, never recovers 430027.
  - So the base has to carry what later measurements say about the past, not only what the past measurements said.
- **The window needed is set by the run.**
  - 430010 needs W = 256. Its single +e3 event is 227 samples before t* (DIAG-2, Hydrogen).
  - The others need 64 (430007) or 128.
  - This is consistent with the timing of the decisive +e3 cuts, 83–250 samples before t*. It does not prove that
    timing is the reason.
- **Close to the boundary, the result is fragile:** S256's margin in 430010 is −0.286 mC, against the oracle's
  −0.389.

## Hydrogen's predictions, written before the results, against the outcome

| prediction | outcome |
|---|---|
| F64 is not enough, or trails S | right: F64 trails S64 in 430007 (745 against 673) |
| the main split is between S64 and S128/S256; S128/S256 come closest to the oracle | right |
| S64 may catch 430010 (468 → 518 is 50 samples apart) | wrong: S64 detects at 3539 |
| S64 may loosen in 430007 (+e3 events 82 samples apart) | wrong: S64 detects at t* |
| phase 2 must not drop non-cut measurement bands blindly | open; it is a design rule for phase 2 (see below) |

## Cost, as run (OBSERVED; Python and HiGHS on Arch, x86, float64; not an MCU figure)

| variant | largest LP (variables × rows) | LPs per sample | time per LP |
|---|---|---|---|
| S128 | 438 × 622 | about 4.6 (2 per step + 42 per 16-step fold) | about 10 ms |
| S256 | 822 × 1134 | about 4.6 | about 20–25 ms |

## Next (phase 2; written as an amendment before it runs; Can decides)

Two different questions remain open.

**2a. What does the architecture give on DEV as a whole?**
- S128 and S256, online, on DEV seeds not used for this diagnosis.
- Measured against cyl16p and v2: D_paired, misses, healthy runs, soundness.
- This answers the "can it reach 80 %?" question at the architecture level, before any MCU work.
- **Cost:** several hours on Arch at this speed, mostly in the folds.

**2b. Can it be made MCU-sized?**
- **Kept measurements:** at most K. Only measurements that are redundant when they arrive may be dropped. This is
  Hydrogen's warning, and it is exact: a measurement whose slab contains the predicted set adds nothing.
- **Transitions:** compressed between the kept ones, keeping the ambient path common (GPT's q_Δ summaries).
- **Resources:** RAM, flash, worst-case time per sample, float32.
- **Fold:** a cheaper fold, e.g. fewer directions or a longer B.

My suggestion is 2a first, because it tells us whether 2b is worth building.

## Independent check of phase 1 (T3a) and what the window really needs (T3c) (OBSERVED; 2026-11-18)

**Where the outputs are:** `results/v3/diag3/indep-T3a/` and `indep-T3c/`. Every hash matches its `DONE.txt`.

**Method:** an independent implementation of S256 written from the plan's text, sharing no code with `diag3.py`. It
adds dual bounds for every fold support and a certified enclosure of the alarm.

**T3a: S256 reproduced on all five runs.**
- **Same detection times:** 673, 579, 849, 695 and 393.
- **Margins at t*:** they agree with `run1-c16f7be` within 5e-14 °C.
- **The alarm at t*:** its separation is certified in all five runs.
- **The fold supports.** In four runs every written support lies at or above its certified dual upper bound.
  - In 430010, three supports at the folds from sample 657 on fell short of it by up to 7.3e-6 °C. That is more than
    the 1e-6 pad.
  - A replay from the last certified fold (641) raised them to their dual bounds, or kept a valid clamp. In that
    replay the alarm is still certified at 695, with a margin of −0.2855 mC.
  - So the 1e-6 pad is not always enough. A certified candidate needs dual-checked folds, not a fixed pad.

**T3c: most measurements are redundant when they arrive.**

| run | measurements redundant at arrival | largest number non-redundant in the window |
|---|---|---|
| 430007 | 592 of 673 | 41 |
| 430027 | 520 of 579 | 34 |
| 430000 | 751 of 849 | 39 |
| 430010 | 623 of 695 | 32 (33 with eviction) |
| 430019 | 347 of 393 | 31 |

- **About 88 % are redundant.** Dropping the redundant ones changes no detection, and no margin by more than 3.2e-8 °C.
- **So K ≈ 41 kept measurements loses nothing on these runs.** The number of variables, 3 per sample of the window, is
  not reduced by this. That still needs the compressed transitions.

**Cost as run** (Python and HiGHS, x86):
- a fold sample takes 1.2–1.6 s at its peak (44 LPs);
- an ordinary sample takes 50–70 ms (median, 2 LPs).

## Amendment 3: the compressed-window pilot (OBSERVED; 2026-11-18, MacBook Air, Apple M4)

**Run:**
- `diag3_cw.py` at `975f2b4`, from a clean checkout, 15:35–15:55.
- The check was rerun after a fix at `459075d`.
- Outputs are in `results/v3/diag3/cw-pilot-975f2b4/`.

**In short:**
- **C1, C2 and C3 pass.**
- **C0 fails as fixed.** One cause was a bug in the check itself. The other is the dense reference's own LP error.
- **E**, the exact compressed form, detects with A in all five runs. It uses about a third of the rows and steps about
  four times faster.
- **N** also matches E in all five runs.

### Detections and margins

| run | t* | A | E | N | margin at t*, A / E / N (mC) |
|---|---|---|---|---|---|
| 430007 | 673 | 673 | 673 | 673 | −4.1861 / −4.1861 / −4.1861 |
| 430027 | 579 | 579 | 579 | 579 | −2.1903 / −2.1903 / −2.1903 |
| 430000 | 849 | 849 | 849 | 849 | −4.6249 / −4.6249 / −4.6249 |
| 430010 | 695 | 695 | 695 | 695 | −0.2855 / −0.2856 / −0.2856 |
| 430019 | 393 | 393 | 393 | 393 | −4.5091 / −4.5091 / −4.5091 |

- Every alarm of every variant is certified.
- **In A, 4 fold supports in 430010 were raised to their dual bound,** by up to 8.8e-6 °C. No other run, and no fold
  of E or N, needed it.

### The criteria

| criterion | result |
|---|---|
| C0: E with every measurement equals the dense LP within 1e-6 °C | **fails** (see below) |
| C1: A at t* in all five; 430010 within 0.01 mC of the independent certified replay (−0.2855) | passes |
| C2: E's detections are A's, with margins at t* within 1e-3 mC | passes (largest difference 1.6e-5 mC) |
| C3: no alarm before t*; every alarm of A and E certified | passes |

### C0

**First run (`975f2b4`).** The check stopped in 430007 and 430000.
- The check added the measurement at t*, which is the alarm, and folded with it.
- In those two runs a fold falls exactly on t* (673 and 849), so that fold LP is empty, as it should be.
- The runs themselves never add the alarming measurement. The check was fixed to stop at t*, as the runs do
  (`459075d`). The tolerance was not changed.

**After the fix,** all five complete:

| run | largest difference, as-range (°C) | largest difference, fold supports (°C) |
|---|---|---|
| 430007 | 7.9e-10 | 1.8e-8 |
| 430027 | 8.5e-8 | 2.2e-7 |
| 430000 | 3.9e-8 | 3.3e-8 |
| 430010 | 5.6e-8 | **2.8e-6** |
| 430019 | 1.2e-9 | 1.0e-8 |

So C0 still fails, in 430010.

**A post-hoc probe of that support** (fold at t = 673, direction (1, −1, 0)/√2; `check-fix-459075d/cw_probe.py`)
shows that the error is the dense LP's:

| | value | equality residual | inequality violation | value at tight tolerances | dual-bound gap |
|---|---|---|---|---|---|
| dense | −0.0136717 | 6.2e-5 | 1.7e-6 | −0.0136745 | 7.3e-6 |
| E | −0.0136746 | 4.9e-15 | 2.6e-15 | −0.0136746 | 8.6e-12 |

- **The dense LP is solved loosely.** At the default tolerances its solution violates its chained equality rows by up
  to 6.2e-5. Its value is therefore too high, which is the sound direction.
- **Tightened, the dense LP moves to within 5e-8 °C of E.** The rest is the 2.7e-6 °C difference between the two
  bases, carried from the dense LP's earlier folds.
- **E's value lies within 1e-11 of its certified bound.**
- **The same three dense supports** fall short of their own dual bound by more than the pad. That is the shortfall the
  independent check found (folds from 657 on). Here at least, the dense support was above the value of the same LP
  solved accurately. The shortfall reflects loose dense duals, so it is not evidence that the support was unsound.
- **Certification is still the rule,** because it is the only guarantee. With E it is tight.

### Size and time (Python and HiGHS on the Mac; not MCU figures)

| | variables | rows | kept measurements | nodes | step, median (ms) | step, p95 (ms) | fold step, largest (ms) |
|---|---|---|---|---|---|---|---|
| A | 822 | 1134 | all | – | 45–57 | 70–77 | 1146–1381 |
| E | 613–633 | 375–393 | 31–41 | 33–43 | 9–14 | 16–18 | 303–332 |
| N | 372–402 | 132–159 | 31–41 | 33–43 | 5–6 | 9–10 | 155–163 |

- The kept counts are the independent check's (T3c) counts: 41, 34, 38 (39 there), 32 and 31.
- No variant needed a fallback LP, apart from one in A on 430010.

### What it shows (INFERRED)

- **On these runs, E is S256 with a third of the rows,** about four times faster per step, and numerically more
  accurate: no chained equalities over 272 steps.
- **N loses nothing here.** These five runs are not enough to say whether the TA box between nodes ever matters. The
  ramp cells, where TA runs close to the walls, are the test.
- **The reading rule needs a decision.** It asks for C0–C3 to pass, and C0 fails as fixed. The probe places the
  failure in the reference, not in E. Whether to go on to the DEV comparison (E and N against 2a's S256) on that basis
  is Can's call.
