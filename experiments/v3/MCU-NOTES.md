# SDTS v3: MCU feasibility notes (phase 2b, exploratory; 2026-11-19)

**Status:** exploratory. These are not pre-registered, and every row below is labelled.
- **Source:** an independent analysis on 430010 (t = 300–695, plus one edge-noise run, 430070), at `0e28951`, on Arch,
  single process, HiGHS 1.12.0.
- **Outputs:** `results/v3/mcu/N1-430010/` (report, results JSON, script, DONE.txt hashes checked).
- **Spot-checked against the results file:** the warm-start counts and the mixed-precision replays.

## Numbers

**Dense B⁻¹ (OBSERVED, arithmetic):**

| | float32 | float64 |
|---|---|---|
| F, m = 409 | 669 kB (653 KiB) | 1307 KiB |
| F under edge noise, m = 445 | 774 KiB | – |
| N, m = 183 | 131 KiB | – |

So a dense inverse is out for F.

**Sparse LU fill** (OBSERVED, scipy `splu`, on the optimal bases, COLAMD ordering):

| | nnz(L+U), median / max | fill |
|---|---|---|
| F step | 2,658 / 2,992 | about 3× |
| F fold | 2,771 / 3,064 | about 3× |
| F under edge noise, max | 3,279 | – |
| N step | 684 / 790 | about 1.8× |

The MMD ordering is about 30 % worse.

**Static solver SRAM** (INFERRED, an estimate, not measured on a device): uint16 indices, a 1.25× LU margin, a
50-pivot eta file, and two warm bases.

| | float32 | float64 |
|---|---|---|
| F | 84 KiB, about 105–115 KiB with the refactorisation workspace | 140 KiB |
| N | 46 KiB, about 60–70 KiB | – |

**Warm-started dual simplex iterations** (OBSERVED, HiGHS with `setBasis`; 430010, t = 1–695; all 1,334 consecutive
bases mapped, with no failure):

| | median | mean | p95 | max |
|---|---|---|---|---|
| F step, cold | 387 | 347 | 498 | 720 |
| **F step, warm** (separate bases for up and dn) | **0** | **0.87** | **3** | **62** |
| F step, warm, one shared basis | 36 | 38.5 | – | 119 |
| N step, warm | 0 | 0.71 | 2 | 43 |
| F fold, 42 LPs, cold | 16,157 | – | 16,603 | 16,906 |
| **F fold, 42 LPs, warm, directions in a nearest-neighbour order** | **557** | – | **651** | **678** |

- Warm primal is slower than warm dual.
- Warm primal also hit a non-optimal status once, in F and in N.

**Certificates on 430010** (OBSERVED):
- **A pure float32 certificate is unusable.** It adds up to +3.1 mC at the alarm (its margin is −0.286 mC) and up to
  40 mC at a fold.
- **A float32 solve with a float64 certificate works.**
  - The LP data is quantised to float32 and solved at tol 1e-6.
  - One float64 basis back-solve, Bᵀπ = c_B, refines the duals.
  - The end-to-end online replay detects at 695 with a margin of −0.28548 mC, and no fold needed raising.
- **An int64 fixed-point certificate (Q30 × Q24)** shows no soundness violation over 1,842 LPs. Its accumulator peaks
  at 61 bits, and it adds at most 0.012 mC at a fold.

## Reading (INFERRED, to be tested)

- **The obstacle looked like the LP solver. With warm starts it mostly goes away.** A step is about one pivot on
  average, and a whole fold about 560 pivots.
- **F's SRAM of roughly 100–115 KiB in float32** fits Cortex-M4 and M7 parts with 192 KiB or more.
- **Not yet shown:**
  - a real float32 (or fixed-point) dual simplex on a device;
  - the worst case over all of DEV, not one run;
  - measured cycles;
  - the warm start of the fold's first direction.

  These are the 2b items, together with a WCET-certified solver (the DAQP or EIQP line).
