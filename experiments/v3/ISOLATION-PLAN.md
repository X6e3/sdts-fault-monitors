# ISOLATION: F3 with its LPs in a child process, under simulated solver failures (plan, 2026-11-21)

Status: DRAFT

Author: Can Koç. Written 2026-11-21 on branch `sdts-v3/template-state`, before any run of it. DEV seeds only.

## 0. Why

An independent review of `df40c058` noted that F3's LPs run in its own worker process: if the solver ends that
process (as HiGHS's interior point did 8 times in freeze 3's oracle, by SIGSEGV), the run ends, and F3's documented
fallbacks never see it. The oracle already runs each attempt in a process of its own. This is an engineering change:
F3's decisions do not change, and freeze 3's verdict is not revisited.

## 1. The variant F3-iso (`diag/f3_iso.py`)

- F3 unchanged, with `diag3_cw.linprog` replaced by a call to a long-lived child process that solves the LP and
  returns its answer (status, value, solution, the four multiplier arrays).
- If the child ends while solving, or does not answer in 120 s, it is replaced and the call raises `RuntimeError`.
  That is one of `SOLVER_ERRORS`, so `solve_f3` counts the attempt as failed ("exception"); after three failed
  attempts F3's fallbacks apply, exactly as for any other failed LP.
- The child is started by `fork` on Linux and `spawn` elsewhere.

## 2. Simulated solver failure

On a hash-chosen subset of LPs (per row key, role and LP index), the child ends itself before solving, in all
three attempts of that LP: half of them by `os._exit`, half by `SIGSEGV`. Rates per role: fold 0.2 %, as-range
0.1 %, certificate 50 %, implied bound 20 % (certificate and implied-bound LPs are rare, so their rates are high
enough to reach them in most fault runs).

## 3. Rows

MCU-2E's 1400 DEV rows (1320 comparison rows, 80 edge-noise healthy rows), with their DEV oracle.

## 4. Checks (fixed)

- **I1 identity:** without injection, F3-iso equals F3 in every field but wall-clock time on the 6 DEV rows of the
  H-FB rehearsal (the smallest sha256 keys).
- **I2 complete:** a record for each of the 1400 rows; no run ended by a process failure.
- **I3 sound:** no alarm on an admissible row, none before the oracle's certified t\*, every alarm certified.
- **I4 counters:** on every row, F3's failsafe counters of kind "exception", role by role, equal the injection log;
  and the child was restarted three times per injected LP (plus any natural failure, reported).
- **I5 memory and slab:** at most 65 measurements kept; no empty-slab failure.

**Verdict:** PASS if I1–I5 hold; FAIL if I3, I4 or I5 fails on a complete run, or I1 fails; INCOMPLETE otherwise.

## 5. Reported, not deciding

Detections against F3 without injection (DEV R1, amendment 10), the cost of isolation (CPU time against F3), natural
solver failures if any.

## 6. What a PASS shows, and what it does not

- **Shows:** with its LPs isolated, F3 survives the solver ending its process, and the documented fallbacks then keep
  it sound and correctly counted.
- **Does not show:** how often a real solver ends its process; anything about the MCU (F3 is not on the board).
