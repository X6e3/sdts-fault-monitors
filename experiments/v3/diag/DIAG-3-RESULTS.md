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

## Phase 2a: S128 and S256 on all DEV rows (OBSERVED; 2026-11-18)

**Run:**
- `diag3_dev.py` at `6c1190f` on Arch, clean tree, 14 workers, 12:12–17:33.
- 13.0 million LPs; 1,367 of them needed a fallback method. 74.7 CPU-hours.
- Outputs are in `results/v3/diag3/dev2a-6c1190f/`: one JSON per row, plus `summary.json`.

**Check:** cyl16p, recomputed online, gives D_paired 0.3858. That is Freeze 1's DEV reference, 0.386.

**Scores** (1320 runs; 1081 with a certified t*; 238 admissible; 1 undetermined):

| | D_paired | bootstrap 95 % | misses | detections equal to t* | largest lag | soundness findings | later than v2 |
|---|---|---|---|---|---|---|---|
| v2 | 0 | – | 8 | 805 | 2880 | 0 | – |
| cyl16p | 0.386 | [0.20, 0.60] | 4 | 897 | 2880 | 0 | 0 |
| S128 | 0.815 | [0.54, 0.99] | 0 | 1063 | 2844 | 0 | 0 |
| **S256** | **0.9992** | **[0.997, 1.0]** | **0** | **1079** | **13** | **0** | **0** |

**Without the ten rows of the five diagnosis runs:** cyl16p 0.512, S128 0.980, S256 0.9987.

**S256 differs from the oracle on two rows only.**
- They are 430027, drift_0.0005, ramp, in both arms: t* = 512, S256 detects at 525. Its margin at t* is +0.232 mC.
- v2, cyl16p and S128 also detect at 525 there.
- The total S256 lag is 26 samples, against v2's 32,925.

**S128's lag** comes almost entirely from 430010 (drift_0.0005, ramp), which S128 detects at 3539. That is 5,688 of
its 6,104 samples.

**The reading rule (amendment 1):**
- S256 reaches D_paired ≥ 0.80 with no soundness finding, so an 80 % gain is reachable at the architecture level, on
  DEV. S256 reaches 0.999.
- This is not a freeze. The window (W = 256, B = 16) was chosen on five of these DEV runs; without them, S256 gives
  0.9987.
- Seeds 440200+ are untouched. A candidate still needs its own freeze and its own validation.

**What this does not show:**
- **S256 folds with the 1e-6 pad, uncertified.** The pilot of amendment 3 found that the dense LP is solved loosely.
  E and N, with certified folds, are running on the same rows (amendment 4).
- **The cost is a desktop cost:** an 822 × 1134 LP and about 4.6 LPs per sample. It says nothing yet about an MCU.

## Amendment 4: E and N on all DEV rows (OBSERVED; 2026-11-18, MacBook Air, Apple M4)

**Run:**
- `diag3_cw_dev.py` at `90d3edc`, from a clean checkout, 8 workers, 16:08–18:54.
- Outputs are in `results/v3/diag3/cwdev-90d3edc/`.
- Scored with `--ref results/v3/diag3/dev2a-6c1190f`.

**The criteria:**
- **D1 passes.** E's detection equals 2a's S256 on all 1320 rows; no row differs.
- **D2 passes.** There is no soundness finding for E or N, and every alarm is certified.

**Scores** (1320 runs; 1081 with a certified t*; 238 admissible):

| | D_paired | bootstrap 95 % | misses | detections equal to t* | largest lag | soundness findings |
|---|---|---|---|---|---|---|
| S256 (2a, dense, pad folds) | 0.9992 | [0.997, 1.0] | 0 | 1079 | 13 | 0 |
| **E** (compressed, exact, certified folds) | **0.9992** | **[0.997, 1.0]** | **0** | **1079** | **13** | **0** |
| N (TA box dropped between nodes) | 0.982 | [0.96, 0.995] | 2 | 1057 | 91 | 0 |

**Without the ten rows of the diagnosis runs:** E 0.9987, N 0.971.

**N against E:**
- **N is never earlier than E.** It is later on 22 rows (11 seeds and cells, both arms).
- **Where:** only drift_0.0005 and drift_0.001. drift_0.0005: 6 rows rw and 2 ramp. drift_0.001: 12 rw and 2 ramp.
- **Misses:** N misses 430006 drift_0.0005 rw, in both arms. E detects it at 3574.
- **So the loss is not confined to the ramp cells.** Under the random-walk ambient, TA also reaches the box walls.

**Size and time over all DEV rows** (Python and HiGHS on the Mac; not MCU figures):

| | kept measurements (median / p95 / max) | nodes, max | variables, max | rows, max | step p95, worst row (ms) | fold step, max (ms) |
|---|---|---|---|---|---|---|
| E | 36 / 43 / 45 | 48 | 643 | 409 | 24 | 574 |
| N | 36 / 43 / 45 | 48 | 417 | 183 | 13 | 376 |

- No fold of E or N needed raising to its dual bound.
- 4 LPs in each needed a fallback method.

### What it shows (INFERRED)

- **E is S256, row for row, on DEV,** with certified folds and at most 409 rows against 1134.
- **At most 45 measurements are kept.** That is a little above the 41 seen on the diagnosis runs.
- **N is not the MCU form, by the reading rule.** The TA box between nodes matters on 22 rows.
- **The next step:** add the TA box rows only when they are needed. An exact way is to solve N, check the TA path
  that the solution implies between nodes, and add the violated rows. An optimum that satisfies them is the optimum of
  E. This would keep E's result at a cost close to N's. It is a proposal, not yet tested.

## Independent score of 2a (T3b) (OBSERVED; 2026-11-18)

**Where:** `results/v3/diag3/indep-2a/`. Every hash matches its `DONE.txt`.

**Method:** a scorer written independently of `diag3_dev.py summary`, run on the same 2a outputs.

**It agrees to the last digit:**

| | all DEV | without the diagnosis runs |
|---|---|---|
| cyl16p | 0.385816 | 0.511835 |
| S128 | 0.814609 | 0.979945 |
| S256 | 0.999210 | 0.998747 |

**Close detections.** `s256-close-detections.csv` lists the 18 S256 detections whose margin is above −0.5 mC.
- The closest are 430009 drift_0.001 ramp (−0.0235 mC) and 430026 drift_0.0005 ramp (−0.0385 mC), both arms each.
- E detects all of them at the same samples, and E's alarms are certified (amendment 4). So none of these 18 rests on
  the dense LP's tolerance.

## Amendment 5, part 1: L (lazy TA rows) on all DEV rows (OBSERVED; 2026-11-18/19, Mac)

**Run:**
- `diag3_cw_dev.py --variants L` at `3c0917c`, from a clean checkout, 8 workers, 23:09–00:11.
- Outputs are in `results/v3/diag3/cwdev-L-3c0917c/`; `score-L.json` compares L with amendment 4's E and N.
- Two short single-process smoke tests ran on the same Mac during the run, so the timings may be slightly high.

**The criteria:**
- **L1 passes.** L's detection equals E's on all 1320 rows.
- **L2 passes.** There is no soundness finding and no uncertified alarm. D_paired is 0.99921, the same as E's.

**Cost** (the same Mac; E and N from amendment 4):

| | rows, max | lazy rows, max | re-solves per LP | step, median of row medians (ms) | step p95, worst row (ms) | fold step, max (ms) | CPU (s) |
|---|---|---|---|---|---|---|---|
| E | 409 | – | – | 15.3 | 23.8 | 574 | 52,833 |
| **L** | **373** | **253** | **0.0086** | **8.8** | **29.5** | **505** | **29,379** |
| N (not exact) | 183 | – | – | 7.2 | 13.1 | 376 | 26,446 |

### What it shows (INFERRED)

- **L gives E's result at close to N's average cost:** 44 % less CPU than E, and only 11 % more than N.
- **The worst case is another matter.**
  - When TA rides the wall, up to 253 lazy rows are needed. L's largest LP (373 rows) is then nearly E's (409).
  - L's worst p95 step time (29.5 ms) is higher than E's (23.8 ms), because of the re-solves.
  - For a fixed worst-case time on an MCU, L is not clearly better than E. This is what the review predicted.
- **The choice between E and L** for an MCU is a question of worst-case time and memory, not of the result. Both give
  the same result on DEV.

## Amendment 6, part 1: the certificate audit (OBSERVED; 2026-11-19, Mac)

**Run:** `diag3_cw.py --variants Fa` at `66429e2`, on the five diagnosis runs, 00:11–00:12. Outputs are in
`results/v3/diag3/audit-66429e2/`.

**A1 passes.**
- 5,676 bounds were audited: every fold bound, every alarm bound, and every eighth as-range bound.
- On every one, the float bound is at least its exact rational evaluation. The smallest slack is 4.4e-15 °C.
- The coefficient-enclosure term is at most 1.8e-12 °C.
- Every certified bound lies within 3.2e-7 °C of its LP value.

**A2 passes.**
- F with no cap detects as the pilot's E in all five runs (673, 579, 849, 695 and 393).
- The margins at t* agree within 9e-9 mC.
- Every alarm is certified.

| run | audited bounds | violations | smallest slack (°C) | coefficient term, max (°C) |
|---|---|---|---|---|
| 430007 | 1220 | 0 | 1.2e-14 | 5.0e-14 |
| 430027 | 986 | 0 | 2.1e-14 | 2.0e-13 |
| 430000 | 1726 | 0 | 4.4e-15 | 1.7e-13 |
| 430010 | 1308 | 0 | 1.8e-14 | 1.8e-12 |
| 430019 | 436 | 0 | 1.5e-14 | 4.9e-14 |

**What it shows (INFERRED):**
- The float evaluation of the certificate is conservative, with a narrow but positive margin.
- Enclosing the coefficient rounding costs nothing measurable, so the bounds now cover the LP with exact
  coefficients.

## Amendment 5, part 2: the window length, E with W = 64, 128 and 192 on all DEV rows (OBSERVED; 2026-11-18/19, Arch)

**Run:**
- `diag3_cw_dev.py --variants E --W ...` at `3c0917c` on Arch, 14 workers, 23:10–01:04.
- Outputs are in `results/v3/diag3/cwdev-W{64,128,192}-3c0917c/`. All of them are scored in
  `results/v3/diag3/score-W-curve-3c0917c.json`, together with W = 256 (amendment 4) and 2a.
- Other processes were running on Arch at the same time (load 15–19 on 16 threads). The times below are therefore
  not comparable with the Mac's. Rows and kept measurements are the size measures.

**The criteria:**
- **W1 passes.** E at W = 128 detects as 2a's S128 on all 1320 rows.
- **W2 passes.** There is no soundness finding and no uncertified alarm, for any W.

**The size–loss curve** (1081 detection events; 1071 without the ten diagnosis rows):

| window | D_paired | without the diagnosis runs | bootstrap 95 % | misses | detections equal to t* | kept measurements (median / max) | LP rows, max |
|---|---|---|---|---|---|---|---|
| none (cyl16p template only) | 0.386 | 0.512 | [0.20, 0.60] | 4 | 897 | – | – |
| W = 64 | 0.643 | 0.904 | [0.40, 0.92] | 0 | 1037 | 14 / 18 | 159 |
| W = 128 | 0.815 | 0.980 | [0.54, 0.995] | 0 | 1063 | 21 / 28 | 245 |
| W = 192 | 0.824 | 0.986 | [0.56, 0.999] | 0 | 1073 | 29 / 35 | 325 |
| W = 256 | 0.9992 | 0.9987 | [0.997, 1.0] | 0 | 1079 | 36 / 45 | 409 |

**Row by row:**
- W = 64 is later than W = 128 on 26 rows, and W = 128 later than W = 192 on 12.
- W = 192 is later than W = 256 on 6 rows: 430010 drift_0.0005 ramp (3449 against 695), 430009 drift_0.001 ramp
  (1481 against 1452) and 430023 drift_0.001 ramp (681 against 580), each in both arms.

### What it shows (INFERRED)

- **Even W = 64 detects every event,** which neither v2 nor cyl16p does, and keeps 90 % of the gain outside the
  diagnosis runs.
- **Outside the diagnosis runs the curve is smooth:** 0.904, 0.980, 0.986 and 0.9987.
- **The jump between 192 and 256 on all of DEV is 430010.** Its deciding +e3 cut comes 227 samples before t*
  (DIAG-2), so only a window longer than that holds it.
- **For a candidate, W sets the size:** the kept measurements and the rows grow roughly linearly with W, from 18 and
  159 to 45 and 409.

## Amendment 6, part 2: F with a cap on kept measurements, K = 64 and K = 40, on all DEV rows (OBSERVED; 2026-11-19)

**Runs:**
- `diag3_cw_dev.py --variants F --K ...` at `66429e2`.
  - K = 64 on Arch (14 workers, 01:03–02:02), from the clean checkout `~/Research/sdts-v3-f-66429e2`.
  - K = 40 on the Mac (8 workers, 00:12–02:08).
- Outputs are in `results/v3/diag3/cwdev-F-K64-66429e2/` and `cwdev-F-K40-66429e2/`; the score is in
  `score-K64-K40-66429e2.json`.

**The criteria:**
- **K1 passes.** F with K = 64 detects as amendment 4's E on all 1320 rows, with no eviction: DEV never keeps more
  than 45.
- **K2 passes** (K = 64, 40 and 32). There is no soundness finding and no uncertified alarm, and no fold needed
  raising.
- **K = 32** (informational; the Mac, 8 workers, 02:08–04:08; `cwdev-F-K32-66429e2/`, `score-K32-66429e2.json`) also
  detects as E on all 1320 rows. It evicted 21,821 measurements on 960 rows.

| | D_paired | without the diagnosis runs | misses | detections equal to t* | later than v2 | evictions (rows) | kept, max | LP rows, max |
|---|---|---|---|---|---|---|---|---|
| E (no cap, amendment 4) | 0.99921 | 0.99875 | 0 | 1079 | 0 | – | 45 | 409 |
| F, K = 64 | 0.99921 | 0.99875 | 0 | 1079 | 0 | 0 (0) | 45 | 409 |
| F, K = 40 | 0.99921 | 0.99875 | 0 | 1079 | 0 | 420 (161) | 41 | 399 |
| F, K = 32 | 0.99921 | 0.99875 | 0 | 1079 | 0 | 21,821 (960) | 33 | 383 |

**What it shows (INFERRED):**
- **The hardened certificate and the outward slabs change nothing on DEV.**
- **The eviction rule costs nothing at K = 40.** F evicted 420 measurements on 161 rows and still detects as E on
  every row. The measurements that have been inactive longest are the ones the window can do without.
- **K = 64 leaves a margin of 19 over the DEV maximum,** and K = 40 shows that the rule works below it.
- **Even K = 32 loses nothing on DEV,** with the cap binding on 960 of the 1320 rows. On DEV, the measurements a
  window of 256 samples needs fit in 32 slots, and the eviction rule finds them. It is DEV only, and K stays 64 for
  freeze 2.

## Amendment 7: F on edge noise (OBSERVED; 2026-11-19, Arch)

**Run:**
- `diag3_cw_edge.py` at `ca407ca`, from a clean checkout, 14 workers, 02:02–02:19.
- 80 healthy runs with edge noise: DEV seeds 430070–430089, both arms, rw and ramp.
- Outputs are in `results/v3/diag3/edge-ca407ca/`.

**E1 passes.** There is no alarm on any of the 80 runs.

**The cap is binding throughout, and that is new.**
- Under edge noise no measurement is redundant at arrival: each sits on its slab boundary.
- F keeps every measurement until the cap is reached (64 in the window, 65 with τ). It then evicts one per sample:
  3535 evictions in every run, one per sample after the 64th.
- **This is the opposite of uniform noise,** where 88 % are redundant and DEV never keeps more than 45.

**Size and time under edge noise:**
- LP rows at most 445, against 409 on the DEV rows. The kept measurements are at the cap.
- The step p95 is at most 32 ms and the fold step at most 670 ms (Arch, a shared machine).
- 78 LPs needed a fallback method, and no fold was raised.

**What it shows (INFERRED):**
- **Soundness holds with the memory full and an eviction at every sample.** This was the case the cap was meant
  for.
- **For an MCU, K is the size to plan for, not the DEV median.** Noise at its bound, or a sensor that saturates the
  slab, fills the window.
- **This check says nothing about detection under such noise.** Every run here is healthy.

## Amendment 8: F raises certified alarms only (OBSERVED; 2026-11-19, Arch)

**Runs:**
- At `0e28951`, from the clean checkout `~/Research/sdts-v3-a8-0e28951`, with 14 workers.
- F with K = 64 on all 1320 DEV rows (02:48–03:51), then amendment 7's 80 edge-noise runs (03:51–04:07).
- Outputs are in `results/v3/diag3/cwdev-F-K64-0e28951/` and `edge-0e28951/`. The pairing with amendment 6's F is in
  `score-K64-a8-vs-a6-0e28951.json`.

**T1 passes.** F's detection equals amendment 6's F (K = 64) on every DEV row: 0 rows differ.
- 1082 alarms, all certified. The certified margin closest to zero is −0.023 mC.
- **Unproved LP alarms: 0.** The LP never pointed to an alarm that the bound could not prove.
- No eviction; at most 45 measurements kept.

**T2 passes.** There is no alarm on the 80 edge-noise runs, and no unproved LP alarm.
- As in amendment 7, the cap binds: 3535 evictions per run, at most 65 kept (with τ), and at most 445 LP rows.
- The step p95 is at most 33 ms and the fold step at most 749 ms (Arch, a shared machine).

**What it shows (INFERRED):**
- **The three changes are safeguards that DEV never triggers.** The outcome is the same as before on every row. On
  validation, an LP value that the bound cannot prove would now drop z_t and be counted, instead of failing the
  whole run.

## Amendment 9: the exact recurrence as F's model, and the data allowance (OBSERVED; 2026-11-19, Arch)

**Runs:**
- At `42252a3`, from the clean checkout `~/Research/sdts-v3-a9-42252a3`, with 14 workers.
- F with K = 64 on all 1320 DEV rows (05:05–06:07), then amendment 7's 80 edge-noise runs (06:07–06:24).
- Outputs are in `results/v3/diag3/cwdev-F-K64-42252a3/` and `edge-42252a3/`. The pairing with amendment 8's F is in
  `score-K64-a9-vs-a8-42252a3.json`.

**The model checks pass** (`check_model.py`, `results/v3/diag3/check-model/`):
- the exact rows sum to 1;
- each of F's powers is the exact power rounded once;
- all 42 clamps hold under the exact recurrence, with the smallest slack 2.2e-15 °C;
- the data error is at most 1.2e-13 °C on 64 healthy DEV runs, 8,000 times below η.

**T1′ passes.** F's detection equals amendment 8's F on every DEV row: 0 rows differ.
- 1082 alarms, all certified. No unproved LP alarm.
- No eviction; at most 45 measurements kept and 409 LP rows.
- D_paired 0.99921, 0 misses, 1079 detections at t*, lag at most 13 s, as before.
- **The certified margins move by less than 1 µC.**
  - 1073 of the 1082 move towards zero, by at most 0.20 µC.
  - 9 move away from it, by at most 0.08 µC.
  - The margin closest to zero is still −0.023 mC.
  - The U row (430003, drift_0.001, E1, rw) still alarms at 1956, with −10.93 mC.
- The step p95 is at most 28 ms and the fold step at most 762 ms (Arch, a shared machine).

**T2′ passes.** There is no alarm on the 80 edge-noise runs, and no unproved LP alarm.
- As in amendments 7 and 8, the cap binds: at most 65 kept (with τ) and at most 445 LP rows.
- 3535 evictions per run, except 430074 ramp, both arms, with 3534: 282,798 in all, against 282,800 at `0e28951`.
- The step p95 is at most 33 ms and the fold step at most 805 ms (Arch, a shared machine).

**S1 passes.** The 10 scorer tests (`tests/test_v3_freeze2_scorer.py`) pass:
- the scorer reproduces the `bc2a051` rehearsal: PASS, with the same numbers;
- a missing row, a duplicate, an extra key, a wrong rows sha, an environment mismatch or a wrong manifest give
  INCONCLUSIVE;
- validation mode without the seed block and the approval gives INCONCLUSIVE;
- a soundness violation with a missing row gives FAIL, and so does an uncertified alarm.

**What it shows (INFERRED):**
- **The correction costs nothing on DEV.** No detection, alarm or eviction changes, and the margins move by less than
  1 µC, against a smallest margin of 23 µC.
- **The certified margin is the dual bound of the solver's solution.** When the LP changes, that bound can move a
  little either way. That is why 9 margins move away from zero, although the slabs widen and the coefficients
  change only at the level of u.
- **The two missing evictions** mean that one more measurement was redundant at arrival in each of those two runs.
  Under edge noise every measurement sits on its slab boundary, and the slab is now η wider. This was not traced to
  the sample.

## Review of the freeze-2 draft: checks at the frozen code (OBSERVED; 2026-11-19, Mac)

**The certificate audit A1, rerun** (`diag3_cw.py --variants Fa` at `f774155b`, the frozen code; clean checkout
`~/Downloads/sdts-runs/v3-mac-src-f774155b`, 06:45–06:46; `results/v3/diag3/audit-f774155b/`):
- the same five diagnosis runs and the same 5,676 bounds as at `66429e2`;
- no violation; the smallest slack is 4.4e-15 °C, and per run it equals the earlier value to within 2e-17 °C;
- the coefficient-enclosure term is at most 1.8e-12 °C;
- the detections are the same (673, 579, 849, 695 and 393), and the margins at t* move by less than 0.003 µC.

**`check_model.py` at `46633b62`** (`results/v3/diag3/check-model/check-model-46633b62.json`, pass):
- **The clamps in exact rationals.** All 42 hold under the exact recurrence, with no decimal rounding and no
  allowance. The smallest slack is 2.2e-15 °C, as with 60-digit decimals.
- **The oracle's model gap.** For any admissible ambient path, the oracle's float matrix and the exact recurrence
  give as values within 5.0e-13 °C of each other over 3600 steps. η is 2,000 times that.
- **The ambient rounding.** On the 16 DEV paths used, no increment exceeds ρ (the largest is ρ − 5.0e-9) and the box
  holds. A priori, an increment can exceed ρ by half an ulp of 27, 1.8e-15 °C; projecting the path then moves it by
  at most 6.4e-12 °C.
- The earlier checks are unchanged: exact rows, powers rounded once, a data error of at most 1.2e-13 °C.

**What it shows (INFERRED):**
- The certificate at the frozen code is as conservative as it was at `66429e2`. Amendment 9 changed its inputs,
  not its margin.
- F's slab δ + η covers both links of the soundness claim with room: the data's float error (a priori under 5e-11 °C)
  and the oracle's float matrix (under 5.0e-13 °C).

## After the freeze-2 approval: the certificate audit on every DEV row (OBSERVED; 2026-11-19, Mac)

`audit_dev.py` at `0ce1b3f7` (clean checkout; criteria AF1 and AF2 fixed in the script before the run), Fa on all
1320 DEV comparison rows, 8 workers, 07:11–10:38 (27.5 CPU-hours); `results/v3/diag3/audit-dev-0ce1b3f7/`
(one file per row, `summary.json`, `meta.json`, `run.log`). DEV only; the validation on Arch was not touched.

- **AF1 holds.** 3,548,402 bounds were audited, from 204 to 9,634 per row, with no violation. The smallest slack
  is 8.2e-16 °C. The coefficient-enclosure term is at most 1.8e-11 °C. The certified bound lies at most 7.1e-6 °C
  above the solver's value.
- **AF2 holds.** Fa detects at the same sample as F (K_cap = 64, `cwdev-F-K64-42252a3`) on all 1320 rows. Its 1,082
  alarms, all on fault rows, are all certified. The 120 healthy rows raise none.

**What it shows (INFERRED):**
- The amendment-6 audit covered 5,676 bounds on five runs. This covers 625 times as many, on every DEV row, at the
  frozen certificate. The float bound never fell below its exact rational value.
- The smallest slack, 8.2e-16 °C, is smaller than on the five runs (4.4e-15 °C), but it is still positive. The audit
  is a check, not part of the soundness argument: the argument rests on the certificate's construction (FREEZE-V2
  §1).

## Amendment 10: F3, F with a sound path for solver failures (OBSERVED; in progress, 2026-11-20)

Code `0ce80072` (F3), criteria and summary `6c3af845`. Plan: `DIAG-3-PLAN.md`, amendment 10 and its three addenda.
DEV only, except R4, which replays freeze 2's deciding row with the validation seeds unlocked by freeze 2's manifest
(the diagnosis of 2026-11-19; that block is no longer a holdout).

**R0, the path tests (U0): 13 of 13 pass.** Mac, at `6c3af845`, on 430000 healthy E0 rw and 430000 jump_0.2 E0 rw.
The cases are:
- range_one_side, range_both_sides, range_overshoot, overshoot_online;
- box_alarm, cert_one_side, cert_both_sides;
- fold_implied, fold_apriori, full_reset, full_reset_continues;
- z0_outside_box, slab_empty.

The box-proved alarm has a certified margin of −700.0 mC on both sides.

**R4, 440243 with F3a (U4): passes.** Arch, at `0ce80072`, clean tree, 191 s.
- All 3599 steps run, with no alarm.
- At t = 945, direction 40 fails, as in freeze 2. The fallback takes the P_J bound −0.20897 °C from the 41 solved
  faces, against an a priori support of 1.683 °C.
- This is the run's only fallback (`fold_dir_fallbacks` {4: 1}, `fold_implied` 1). No other failure, reset or box
  alarm occurred.
- The exact audit checked 9,634 bounds, one of them the P_J bound, with no violation. The smallest slack is 1.1e-14 °C
  overall and 3.9e-14 °C on the P_J bound.
- Re-evaluated at `6c3af845` under the strict U4 of the second addendum: passes.

**R1–R3:** running (R1, R2 on Arch; R3 on the Mac). Not read yet.

**Third addendum, I1a: passes.** Mac, 2026-11-20 02:10–02:50. The old code (`0ce80072`) and the new (`000cd215`) ran
side by side, two processes at nice 19, while R3 ran. Inputs: 4 healthy edge rows (430070 E0/E1 × rw/ramp) and 4
DEV fault rows (indices 0, 100, 200 and 300 of the fault rows sorted by key), under settings none and d.
Outputs are in `results/v3/diag3/amend10-i1a-000cd215/`; scripts `diag/amend10_i1a.py` and
`diag/amend10_i1_compare.py`.
- **Records:** all 16 pairs are equal in every field except `seconds`, `step_ms` and `fold_step_ms`.
- **Memory, new code:**
  - |zs| is at most 65 at every check (after each keep, evict and fold);
  - |last_active| is at most |zs|;
  - keys(last_active) ⊆ keys(zs) at all 48,460 checks.
- **Memory, old code, same rows:**
  - |zs| reaches 66 on every edge row;
  - |last_active| reaches 317 on 430000 drift_0.0005 E0 ramp;
  - the subset fails at 6,860 of 7,342 checks on an edge row under setting none.
- On edge noise every z_t cuts the range, so each edge row keeps a measurement at every step. That gives 3,535
  evictions and 15,934 LPs on all four rows. The data differ between the rows: `n_retry` is 0 on rw and 1 on ramp.
- **I1b** (all of R-none on Arch with the new code) follows after all.done.

**Fourth addendum (the solver boundary, M1's G1 and G2), at `8c55e19e`** (U5 at `1c0439cd`, which adds only its
script). Mac, 2026-11-20 04:10–05:30, nice 19, while R3 ran. Outputs in `results/v3/diag3/amend10-fourth-8c55e19e/`.
- **U0b: passes, 10 of 10** (`diag/amend10_u0b.py`, R0's healthy and fault rows):
  - an exception on the first attempt only: solved by the second, `n_retry` 0 → 1, no failsafe counter;
  - an exception on all three attempts of a fold direction: `fold_dir_fallbacks` {exception: 1}, the P_J bound taken;
  - status 0 with a NaN inequality multiplier (t = 289): {nonfinite: 1}; finite multipliers of −1.5e308 that make
    the certified bound overflow: {nonfinite: 1}, solved on the first attempt, so the certificate is what failed;
  - a non-finite "up" certificate at the fault row's detection (t = 420): `cert_fallbacks` {nonfinite: 1}, "up" in
    `box_sides`, the alarm unproved there; the row detects at 425, certified;
  - an exception on all attempts of one as-range side: {exception: 1}, that z_t not kept;
  - a NaN in our own LP input raises `ValueError`; a `TypeError` in our own fold code and a `MemoryError` inside the
    solver call both propagate out of `online()`; the kinds read `exception` and `nonfinite`.
- **R0 at `8c55e19e`: 13 of 13.**
- **I2a: passes.** The 16 records of I1a with the new code against the `0ce80072` records already on the Mac: all 16
  equal in every field except `seconds`, `step_ms` and `fold_step_ms`. Memory as I1a: |zs| ≤ 65 and
  keys(last_active) ⊆ keys(zs) at all 48,460 checks.
- **U5: fails as written, on 2 of its 7 criteria; the cause is the test's row choice, not F3.**
  - Passes: no alarm on the 16 healthy rows; at every checked fold of the 20 forced rows (3,388 folds; on fault rows
    only before the onset) the generator's true state lies in the new base on all 42 directions (largest
    d_i·x − base_i: −0.00023 °C); each forcing gives slab failures and
    exactly one full reset (healthy: resets 5, 9 and 1 samples after the forcings at 300, 1000 and 2000; fault: 23
    samples after 250), with 42 slab fold failures per reset; the exact audit finds no violation (smallest slack
    3.7e-15 °C).
  - Fails: "every alarm on a fault row certified" and "every fault row detects after its last forced reset". The two
    `stuck` rows (430000 and 430001, E0 rw uniform) have no oracle detection: the full-history oracle certifies the
    whole record consistent (t* = None). F3 raises no alarm on them, forced or not, which is what soundness requires.
    The rows were chosen without checking the oracle; under E0 a stuck sensor reads a value the model can explain.
  - The two `drift_0.002` rows detect at 506 and 652, certified: the oracle's t* exactly, and the same sample as the
    unforced run.
  - The certificate-coverage check was never exercised: no alarm certificate was computed before an onset.
- **U5b** (DIAG-3-PLAN, proposed after U5's result, not run): the fault part again with rows the oracle detects.
- **I2b and I2c:** not run. Can, 2026-11-20 04:40: no big runs on Arch without his go; I2b's size is his to set.
