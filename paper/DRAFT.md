# How much of the record does a sound fault monitor need? Bounded-memory set-membership sensor-fault detection measured against the exact oracle

Draft v0.1, 2026-11-21. Not for circulation. Superseded by `preprint/main.tex` (v0.2); kept as it was.

Can Koç, independent researcher. Contact: TBD.

<!--
Rules for this draft:
- Every number carries its source in an HTML comment: src = a dated record in experiments/v3/ (or a results file).
- [PENDING: ...] marks results not yet in. [CHECK: ...] marks a claim to verify against a primary text before submission.
- No team names, no "first", no claims beyond the records. Failures are told in the text, not in footnotes.
-->

## Abstract

A set-membership fault detector raises an alarm when no admissible explanation of the sensor record exists. For a
linear plant with bounded noise and a bounded unknown input, the exact detector keeps a convex polytope whose
description is not bounded in advance, so an embedded detector keeps a bounded outer approximation and detects later.
We measure that loss directly. On a two-node thermal plant with one temperature sensor, a known heat input, an unknown
ambient temperature and ten sensor-fault classes, a certified full-history linear program gives the exact detection
time of every run. Bounded monitors are compared with it under the same assumptions and the same decision rule, so
every difference is information that the representation discarded. We study two tiers. The first is a
template-polyhedron state whose support computations are replaced by offline LP bases and bounded by reachable-set
clamps: it needs no solver, is proved sound and never later than the interval monitor it extends, and its C
implementation runs on an ESP32 bit-identically to the PC on 5.04 million development samples. On 9,600 fresh,
pre-registered runs it removed 38.7 % of the interval monitor's paired detection lag. The second is a 256-sample
window LP whose base is updated by a smoothing rule, with a weak-duality certificate on every alarm and every base
update. On a second fresh block of 9,600 runs it removed 99.5 % of the lag with no missed event (the interval monitor
missed 27), and all 7,258 alarms were certified. A previous freeze of the same window failed its validation, because a
single LP the solver could not solve became an uncertified alarm; we report that failure, the sound fallback that
replaced it, and its test under injected solver failures. We also show that no memory budget can certify the error of
a sensor drift that an admissible ambient path reproduces. [PENDING: one sentence on baselines B1–B5.]

<!-- src: 38.7 % = D_paired 0.387, RECORD-2026-11-18-validation.md; 99.5 %, 27, 7,258 = RECORD-2026-11-21-validation.md;
5.04 M samples = MCU-NOTES 2e; freeze 2 failure = RECORD-2026-11-19-validation.md -->

## 1 Introduction

A set-membership fault detector treats the noise and the unknown inputs as unknown but bounded. It declares a fault
when the measured record has no explanation that respects the model and the bounds. Within those bounds it cannot
raise a false alarm [Ingimundarson et al. 2005; Scott et al. 2016; Puig 2010]. The exact detector keeps the set of
states that some admissible past explains, the information state of Witsenhausen [1968] and Schweppe [1968]. For a
linear plant with bounded noise and inputs it is a convex polytope, and its complexity is not bounded a priori
[Sznaier et al. 2011; Blanchini and Sznaier 2012]. Practical detectors therefore keep a bounded outer approximation:
intervals, parallelotopes, zonotopes, constrained zonotopes, or the data of a moving window. An outer approximation
keeps the guarantee against false alarms. What it gives up is detection: an alarm that comes later, or not at all.

How much does it give up? The usual answer compares the size of the estimated set with the exact set
[Scott et al. 2016, Sec. 5; Casini et al. 2024, Sec. 6]. Detection studies sweep the complexity of the bounded
estimator, but without the exact detector as reference: Scott et al. [2016, p. 133] leave the exact observer out of
their fault-detection comparison because of its cost. Set size is not detection time, and a detection-time curve
without the exact reference cannot say how much is left to gain.

This paper measures the loss in detection time against the exact detector, run by run. The exact detection time t*
of each run comes from a full-history LP whose verdicts carry certificates in both directions (Section 2.5). The
bounded monitors use the same assumptions and the same decision as that LP: the first sample at which no admissible
explanation exists. So a monitor can only be later than t*, and every sample of delay is information its
representation discarded (Corollary 1). We report the delay as the share of a reference monitor's lag that a
candidate removes, on pre-registered validation blocks of fresh seeds.

The plant is a two-node lumped thermal model, core and surface, with a known heat input. One sensor reads the
surface temperature. The ambient temperature is unknown; its range and its rate of change are bounded. The sensor
noise is bounded. Ten fault classes (jumps, drifts at five rates, a gain error, increased noise, a stuck sensor) are
simulated over records of 3,600 samples.

**Contributions.**
1. *An exact yardstick.* For this problem class the information state is a polytope in three dimensions
   (Proposition 1), and a certified full-history LP decides consistency for every run. Every bounded monitor below is
   scored against it under identical semantics.
2. *A solver-free tier.* A template-polyhedron state with 42 directions, whose support computations are replaced by
   LP bases enumerated offline and whose drift is bounded by reachable-set clamps. It is sound (Theorem 2) and never
   later than the interval monitor (Theorem 3). Validated on 9,600 fresh runs: 38.7 % of the interval monitor's
   paired lag removed, 16 missed events against 24. Its C implementation runs on an ESP32 at 3.6 ms per sample and on
   an 8-bit AVR at 75 ms per sample (Section 7.6).
3. *A window tier.* A 256-sample window LP with a smoothing update of its base, at most 65 kept measurements, and a
   certified weak-duality bound on every alarm and every base update. Validated on another 9,600 fresh runs: 99.5 %
   of the paired lag removed, no missed event, every alarm certified. On development data the memory-loss curve runs
   from 0.39 (template only) through 0.64, 0.82 and 0.82 to 0.999 for windows of 0, 64, 128, 192 and 256 samples.
4. *Failures, reported.* The first validation of the window tier failed on one unsolved LP. We report the failure,
   its diagnosis, the sound fallback path that replaced it and its test under injected solver failures, together with
   the precision gaps we found in our own implementations and how they were closed (Section 8).
5. *A limit no budget removes.* When an admissible ambient path reproduces a sensor drift, no state of any size can
   certify the drift's error (Proposition 4). We give development runs where this happens.
6. [PENDING: baselines B1–B5 on the window tier's validation block.]

<!-- src: 16 vs 24 = RECORD-2026-11-18-validation.md Verdicts; 3.6 ms = MCU-NOTES 2e; 75 ms = MCU-NOTES 2c/2f;
curve = DIAG-3-RESULTS.md "size–loss curve" (DEV); 65 kept = FREEZE-V3 §1 memory bound -->

**Not claimed.** One plant, with known parameters, in simulation. The ambient box is an assumption the results lean
on (Section 7.8). The window tier needs an LP solver and runs on a desktop; no worst-case execution time is shown for
either tier. None of the ingredients is new on its own (Section 9).

## 2 Problem

### 2.1 Plant

With sampling time 1 s, core temperature T_c, surface temperature T_s, heat input P and ambient T_A:

    T_c[k+1] = T_c[k] + (P[k] − K (T_c[k] − T_s[k])) / C_c
    T_s[k+1] = T_s[k] + (K (T_c[k] − T_s[k]) − H (T_s[k] − T_A[k])) / C_s
    y[k]     = T_s[k] + v[k]

with C_c = 30, C_s = 12, K = 2, H = 0.8 and P[k] ∈ [0, 42] W. The discrete eigenvalues are 0.98437 and 0.71563
(time constants 63.5 and 3.0 samples). The response of T_s to T_A is nonnegative and sums to one.

<!-- src: experiments/generators/thermal.py; experiments/specs/thermal_single_sensor_consistency.md §1–2 -->

### 2.2 Assumptions

- (a) noise: |v[k]| ≤ δ = 0.3 °C;
- (b) ambient rate: |T_A[k+1] − T_A[k]| ≤ ρ = 0.002 °C per sample;
- (c) ambient box: 23 ≤ T_A[k] ≤ 27 °C;
- (d) the command P is known (it is the controller's own);
- (e) the record starts at the steady state of P = 20 W at the unknown initial ambient.

No distribution is assumed anywhere. Assumption (e) gives no absolute temperature.

### 2.3 Reduction to the ambient part

The plant is linear and P is known, so y = S + a_s + v, where S is the response to the command from the steady state
at zero ambient and a_s is the surface's response to the ambient. The monitor sees z = y − S. Shift temperatures by
−25 °C, so that the box (c) is [−2, 2], and write the ambient part as s = (a_c, a_s, T_A):

    s_{k+1} = M s_k + e_3 w_k,   |w_k| ≤ ρ,   −2 ≤ (s_k)_3 ≤ 2,
    z_k = (s_k)_2 + v_k,         |v_k| ≤ δ,
    s_0 = t (1, 1, 1),           t ∈ [−2, 2],

with M = [[1 − K/C_c, K/C_c, 0], [K/C_s, 1 − (K+H)/C_s, H/C_s], [0, 0, 1]]. The first two rows of M sum to one, so
a_c and a_s are convex combinations of past ambient values and of their start.

**Exact model.** All exact computations below use the recurrence of the simulator with its floating-point
parameters taken as exact rationals. The matrix built entry by entry in binary64 differs from it: read as rationals,
its rows sum to 1 + 2⁻⁵⁶ and 1 + 3·2⁻⁵⁶. Section 8 tells how this mattered.
<!-- src: FREEZE-V2.md §1 "The model" (DIAG-3 amendment 9) -->

### 2.4 Decision

A prefix z_0..z_k is *consistent* if some admissible start, ambient path and noise explain it under (a)–(e). The
exact detection time t* of a record is the first k at which the prefix is inconsistent; t* does not exist if the
whole record is consistent. A monitor that flags at t_m is *sound* if it never flags a consistent prefix, that is,
t_m ≥ t*, and never flags an admissible record.

The decision does not identify a fault. An inconsistent record proves that the model and the assumptions do not hold
for it; a consistent one only proves that some admissible explanation exists (Section 3.4).

### 2.5 The oracle

The oracle decides a prefix with the LP d* = min d such that a_s from the plant's own dynamics, an ambient path with
(b) and (c), and the start (e) satisfy |z_j − (a_s)_j| ≤ d for every j. It does not take the solver's word:
- *consistent* needs an upper certificate: the solver's ambient path is projected onto the admissible set (each step
  clipped to the rate bound, then to the box), run forward through the plant independently of the LP, and the
  largest residual it leaves must be at most δ;
- *inconsistent* needs a lower certificate: a weak-duality bound from sign-corrected multipliers, with the
  stationarity residual's worst case over an enclosing box subtracted, must exceed δ;
- otherwise the prefix is *undetermined*, reported and never guessed.

t* is found by bisection over prefixes (consistency of prefixes is monotone). It is *certified* when the final
inconsistent prefix is certified. Each solver attempt runs in its own process. Undetermined runs are excluded from the
scored sets, and their number is bounded by the validation rules (Section 6).

<!-- src: experiments/oracle/thermal_oracle.py docstring and first_inconsistent() -->

### 2.6 Scenarios

Development seeds and validation seeds use separate string namespaces of the same generators.
- **Excitation:** E0, constant P = 20 W; E1, P redrawn uniformly in [0, 42] W every 15 s.
- **Ambient:** *rw*, a bounded uniform random walk; *ramp*, piecewise ramps at 50–100 % of ρ with exponential
  switching times (mean 300 s), turned back at the box.
- **Noise:** *uniform* in [−δ, δ]; *edge*, ±δ exactly with random sign, on the boundary of (a), to stress soundness.
- **Faults**, from an onset uniform in [300, 600]: jumps of 0.2 and 0.5 °C; drifts of 0.0005, 0.001, 0.002, 0.005
  and 0.02 °C/s; a gain error of 1 %; noise doubled; a stuck sensor.

A validation block of 200 seeds has 48 runs per seed: 40 fault runs (10 faults × 2 arms × 2 ambient laws, uniform
noise) and 8 healthy runs (2 arms × 2 ambient laws × 2 noise laws), 9,600 runs in all.

<!-- src: experiments/v3/dev_scenarios.py; RECORD-2026-11-21-validation.md "Data" and per-cell table -->

### 2.7 Metric

The reference monitor is the interval monitor IM of Section 3.2. For a candidate m, the paired set B holds the
certified detection events that IM detects. The paired lag is L_m = Σ_{r∈B} (t_m(r) − t*(r)), with a miss of m in B
counted as N − t*, N = 3,600. The score is

    D_paired = 1 − L_m / L_IM,

the share of IM's lag that m removes. D_paired = 1 means detection at t* on every paired event. Misses over all
certified events are reported separately and are part of every hypothesis.

<!-- src: FREEZE-V3.md §4 (freeze 2's rules) -->

## 3 The information state, and what an interval monitor keeps

### 3.1 The exact state is three-dimensional

**Proposition 1.** Define X_0 = {t (1,1,1) : t ∈ [−2, 2]} ∩ {s : |z_0 − s_2| ≤ δ} and

    X_{k+1} = (M X_k ⊕ ({0} × {0} × [−ρ, ρ])) ∩ {s : −2 ≤ s_3 ≤ 2} ∩ {s : |z_{k+1} − s_2| ≤ δ}.

X_k is the set of states at k that some admissible past explains. The prefix z_0..z_k is consistent if and only if
X_k ≠ ∅, so t* = min{k : X_k = ∅}.

*Proof.* An admissible past is a start t and increments w_0..w_{k−1} with (b) and (c); together with (e) they fix
s_0..s_k. Every constraint at time j (the noise bound, the box, and the rate between j and j + 1) involves s_j, or
s_j and s_{j+1}. By induction on k, s_{k+1} is explained if and only if s_{k+1} = M s_k + e_3 w for some explained s_k
and some |w| ≤ ρ, and s_{k+1} meets the box and the measurement at k + 1. The oracle's LP is the same feasibility
problem with the intermediate states written out. ∎

This is the classical set-membership recursion [Witsenhausen 1968; Schweppe 1968; Bertsekas and Rhodes 1971]. Its
use here is as a yardstick: nothing in the history beyond X_k bears on any future consistency decision, so a
bounded monitor loses only through the coarser description of a polytope in R³. X_k is compact and convex; its
number of vertices is not bounded a priori. On five development runs the exact polytope, kept in vertex form (a
floating-point diagnostic, not certified), had a median of 3,156 to 7,190 vertices per run and at most 16,066, and
its first empty sample equalled the oracle's t* on all five.

<!-- src: V3_NOTES.md §2; vertex counts = results/v3/exact_vrep_dev.txt (2026-11-18) -->

### 3.2 The interval monitor

The interval monitor keeps an interval I_k ⊇ π_2(X_k), the projection of the exact set on a_s:

    I_{k+1} = (I_k ⊕ [−ρ, ρ]) ∩ [z_{k+1} − δ, z_{k+1} + δ] ∩ [−2, 2].

It rests on |a_s[k+1] − a_s[k]| ≤ ρ, which holds because the response of a_s to T_A is nonnegative with unit sum
and (e) starts at a steady state. It flags when the interval is empty. It is the reference of every score in this
paper.

**Corollary 1.** IM and the exact detector use the same assumptions and the same decision. X_k ⊆ {s : s_2 ∈ I_k}, so
IM can only be later than t*, and every sample of its delay is information its representation discarded.

What IM discards is the error state e = (a_c − T_A, a_s − T_A). In particular the a_s-velocity v·s_k =
a_s[k+1] − a_s[k], with v = Mᵀe_2 − e_2, is itself a state with dynamics: a surface that has risen at the full rate
cannot fall at the full rate one sample later, because the core lags. The interval allows ±ρ at every step
independently.

### 3.3 The reachable error set

**Lemma 1.** The error e = (a_c − T_A, a_s − T_A) obeys e_{k+1} = F e_k + g w_k with F the upper-left 2 × 2 block of
M, g = (−1, −1) and e_0 = 0. Every reachable e therefore lies in E_∞ = ⊕_{j≥0} F^j g [−ρ, ρ], with support
h_E(q) = ρ Σ_j |q · F^j g|.

For this plant |a_c − T_A| ≤ 0.135, |a_s − T_A| ≤ 0.105 and |a_c − a_s| ≤ 0.030 °C, and in the a_s-velocity direction
h_E = ρ exactly: IM's lemma is one face of E_∞. The supports are computed offline with a bounded tail, and checked in
exact rational arithmetic against the exact model (smallest slack 2.2e-15 °C over all 42 clamps).

<!-- src: V3_NOTES.md Lemma 2; slack = FREEZE-V2.md §1 "The clamps" (check_model.py) -->

### 3.4 What no memory can certify

**Proposition 4.** Let a record come from a faulty sensor with an additive error ε(t). If an admissible ambient path
T_A′ reproduces the record as a healthy one (the plant's response to T_A′ − T_A equals ε within the noise slack),
then every method whose output is a function of the record and the command gives the faulty record an output it also
gives a healthy record. In particular, no state of any size, the full history included, can bound the sensor error
below sup|ε| over such twins.

*Proof.* The faulty record is, sample for sample, a record of the healthy plant under T_A′. ∎

The statement is elementary; its use is to separate representation loss from a limit of the hypothesis class. A
slow drift can have such a twin, but a rate at most ρ and room in the box are not enough: whether a twin exists
depends on the onset, the noise and the plant's lag. From the steady state (e), every healthy explanation has
a_s[1] = a_s[0]; a drift of rate 0 < r ≤ ρ from sample 1, with noise −δ at sample 0 and +δ at sample 1, needs
a_s[0] ≤ 0 and a_s[1] ≥ r (shifted units), so that record is inconsistent at sample 1. Twins do exist on development
runs 430056 and 430059 (drift 0.001 °C/s, E0): the oracle's exact constant-offset interval over the whole record is
[−0.70, 0.12] and [−0.48, 0.24] °C, while the true error at the end is 3.17 and 3.18 °C.

<!-- src: V3_NOTES.md Theorem 4 (corrected 2026-11-21) and its DEV witness -->

## 4 Tier 1: a template state without a solver

### 4.1 Template polyhedra with offline bases

Fix unit directions D = {d_1, …, d_n} that include ±e_1, ±e_2, ±e_3. The state is a vector h ∈ R^n representing
P = {s : D s ≤ h}. The support of P in a direction g is, by LP duality,

    supp_P(g) = min {λ · h : λ ≥ 0, Dᵀλ = g},

exact for nonempty P. The optimum lies at a basic solution, a triple of directions. Since M and D are fixed, every
needed g (Mᵀd_i for each i, and ±e_2) and every feasible triple with its multipliers λ can be enumerated offline. At
run time a support is the minimum over stored triples of a three-term dot product: no LP, no allocation. A subset of
the triples gives an upper bound, which is all soundness needs.

**Per sample k:**
1. The a_s-range of P is [−supp(−e_2), supp(e_2)]. If it misses [z_k − δ, z_k + δ], flag (absorbing).
2. Tighten h(±e_2) with the measurement.
3. Predict h′_i = supp(Mᵀ d_i) + ρ |(d_i)_3|.
4. Clamp each h′_i with the box (c) and with the reachable-set support h_E of Lemma 1 where it applies.

Template polyhedra come from reachability analysis [Sankaranarayanan et al. 2008]; offline enumeration of LP bases
from parametric programming. The clamps are what make the combination work here (Theorem 3 and Table 1).

### 4.2 Guarantees

**Theorem 2 (soundness).** For any D containing the axis directions, any subset of each direction's bases, and outward
rounding of every computed support, P_k ⊇ X_k for all k. Hence the template state never flags before t* and never
flags an admissible record.

*Proof.* By induction. P_0 ⊇ X_0, because the start supports are those of the start segment. Intersecting both sides
with the slab keeps the inclusion. A minimum over fewer bases is at least the exact support, and the exact support of
M(P ∩ slab) ⊕ (the w segment) in direction d_i is supp(Mᵀ d_i) + ρ |(d_i)_3|; a polytope given by upper bounds on the
supports of a superset is a superset. The clamps hold for every reachable state (Lemma 1 and (c)). Every computed
support is an upper bound after the pads, which cover the dot product's rounding, the stored residual of each basis,
and the rounding of λ to the stored precision. ∎

**Theorem 3 (never later than IM).** Suppose ±e_2 and ±v̂ ∈ D, with v̂ = v/|v|, the clamps are applied, and for the
targets ±Mᵀe_2 a basis {±e_2, ±v̂, x} is kept. Then π_2(P_k ∩ slab_k) ⊆ I_k for all k, so the template state flags no
later than IM.

*Proof.* Mᵀe_2 = e_2 + v. With the kept basis, supp_{P_{k+1}}(e_2) ≤ h(e_2) + |v| h(v̂). By induction h(e_2) ≤ max I_k,
and the clamp gives |v| h(v̂) ≤ h_E(v) = ρ. So the upper end is at most max I_k + ρ; the lower end is symmetric, and
intersecting with the slab and the box gives π_2 ⊆ I_{k+1}. The direction e_2 carries no w term. ∎

Theorem 3 holds in the arithmetic of the proof. Section 7.6 shows that a float32 build, sound by Theorem 2, is later
than IM on some runs.

### 4.3 The frozen template

The validated template TS (*cyl16p* in the records) has 42 directions: the six axis directions, four differences of
coordinates, ±v̂, eight directions in the error plane {d : d_1 + d_2 + d_3 = 0}, and 16 angles in the (a_c, a_s)
plane with both signs, after removing duplicates. The last family has normals orthogonal to e_3, as do the faces that
the Minkowski sum with the ambient segment creates. Its base tables were pruned to the bases used on 120 selection runs
(development seeds outside the evaluation range): 1,318 entries, about 20 KB of float32 tables. A smaller template
(*inv4p*: the axis and difference directions, ±v̂ and four error-plane directions; 16 numbers, 231 entries, 3.7 KB)
was validated alongside it.

<!-- src: template_state.py directions("cyl"); RESULTS.md budget table (selection runs: 430050–052 for cyl16p,
430050–069 for inv4p; evaluation 430000–430029); FREEZE-V1.md -->

On development data, without the clamps, templates are worse than IM; directions orthogonal to T_A keep improving
detection as they are added (8 angles: −23 % total lag, 16: −38 %, 24: −39 % at 2.5 MB of tables).

<!-- src: RESULTS.md (DEV): "Templates without invariants are worse than v2"; cyl8/16/24 rows -->

## 5 Tier 2: a window LP with a smoothing base

### 5.1 Why a window, and why smoothing

Diagnosis runs on development data located the template state's loss. At the separating facet at t*, the exact set
is cut by template directions; what the template loses is mostly the lower bound on T_A, wrapped outward at every
measurement cut. Over 63 such cuts on five runs, 95 % of the loss occurs even for the tightest template hull of the
exact set, so it is geometry, not recursion slack. Two larger direction families (72 and 94 directions) recovered
little of it and failed their pre-registered criteria. Keeping the measurements themselves, over a window, avoids the hull.

<!-- src: DIAG-1-RESULTS.md; DIAG-2-RESULTS.md (T1: 556.5 of 582.9, 95 %; families B1/B2 FAIL) -->

### 5.2 The window

The window monitor WM (*F3* in the records) keeps, between samples,
- a base at time τ: the 42 supports of the template TS, with its clamps;
- the measurements kept since τ, at most K_cap = 64;
- τ itself.

At each sample t it solves LPs over the samples τ … t, at most W + B + 1 = 273 transitions, with W = 256 and B = 16:
- **Exact steps between nodes.** x_b = M^L x_a + Σ_{k<L} M^k e_3 w_{b−1−k}, with every |w_j| ≤ ρ explicit. M^L and
  M^k e_3 are the exact powers of the exact model, each rounded once. (a_c, a_s) appear at the nodes only (τ, the kept
  measurements, τ + 16 and the objective sample) and T_A at every sample. Between nodes, a_c and a_s stay in the box by
  convexity, so only T_A's box rows are needed. Apart from dropped measurements, the window is exact.
- **Measurements.** A measurement redundant at arrival is dropped. Above K_cap kept measurements, the one inactive
  longest is evicted. Both only remove constraints.
- **The alarm.** At t the as-range of the window given z up to t − 1 is computed. WM flags only when a *certified*
  bound separates it from [z_t − δ − η, z_t + δ + η], with η = 1e-9 °C and the slab rounded outward. A primal value
  that points to an alarm the certificate cannot prove raises nothing; z_t is then dropped.
- **The fold, every B = 16 samples.** The base moves from τ to τ + 16. Each of the 42 new supports is the maximum of
  d_i · x_{τ+16} over the window *with every measurement up to the current sample t*, raised to at least its certified
  bound and then clamped. This is the smoothing rule: the new base carries what later measurements say about the past
  state. The filtering rule would use the measurements up to τ + 16 only.

η encloses the floating-point error of the data. The simulator computes z from two binary64 simulations; an a priori
bound puts the data of every healthy run within 5e-11 °C of data that an admissible exact-model run explains with
|v| ≤ δ. η is 20 times that.

<!-- src: FREEZE-V2.md §1 (window LP, fold, η and its a priori bound); FREEZE-V3.md §1 -->

### 5.3 Certificates

Every alarm bound and every fold bound is a weak-duality bound computed from the solver's multipliers, with every
variable boxed, the floating-point rounding of the bound's own evaluation bounded explicitly, and each LP
coefficient's rounding enclosed (each is its exact value rounded once). The bound therefore holds for the LP with
exact coefficients, whatever the solver's tolerance [Neumaier and Shcherbina 2004; Jansson 2004]. With every
variable boxed it holds for *any* multiplier vector: a solver stopped early gives a looser bound, never an unsound
one. The floating-point model is IEEE binary64 with round-to-nearest and gradual underflow; a product's error beyond
the relative model is at most 2⁻¹⁰⁷⁵, and the bound includes that term.

An audit variant evaluates every bound again in exact rational arithmetic. Over all development rows, 3,548,402
bounds were audited with no violation; the smallest slack was 8.2e-16 °C. Under simulated solver failures a further
12,572,172 bounds, 425,757 of them fallback bounds, were audited with no violation.

<!-- src: FREEZE-V2.md §1 "The certificate"; FREEZE-V3.md §1 floating-point model; DIAG-3-RESULTS.md AF1 (3,548,402,
8.2e-16) and amendment 10 R3 table (a, b 4,319,122 each, e 3,933,928; implied 39,033 + 386,724) -->

**Proposition 5 (soundness of WM).** Under the model, WM never flags an admissible record and never flags before t*,
and every flag carries a certificate.

*Proof sketch.* Let 𝔛(t | t − 1) be the exact-model explanations of the measurements up to t − 1, as states at t,
with slabs δ + η. The window LP with exact coefficients contains 𝔛 when its base at τ contains the projection of the
explanations at τ: its rows are the model's dynamics, the a_c and a_s boxes hold by convexity, and the w and T_A
boxes are the model's. The certificate bounds the ideal window, not the solver's rounded one. The start is the
template's start. Dropping and evicting only remove constraints. Each fold support is at least the maximum over the
ideal window and the clamps hold for every reachable state, so the new base contains the explanations at τ + 16. An
alarm needs a certified separation. The full proof, checked line by line against the code, is in the repository
[CHECK: decide whether it goes into an appendix]. ∎

### 5.4 When the solver does not solve

Every LP of WM has two outcomes: *solved* (status optimal, after at most three attempts: dual simplex without
presolve, interior point without presolve, dual simplex with presolve) or *failed* (any other status, an exception
from the solver call, or a non-finite answer). WM never uses a value from a failed LP. A solver's "infeasible" is one
more failure, not a proof: an alarm needs a certified separation. The fallbacks are outer bounds:

| failed LP | fallback | why it is sound |
|---|---|---|
| one side of the a_s-range | that side's box bound; z_t not kept | the box contains every state |
| one side of the alarm certificate | that side's box bound | the same |
| one direction of a fold | the certified maximum over P_J ∩ box, J the solved faces of the same fold; if that 3-variable LP fails too, the a priori clamp | the window's states lie in P_J ∩ box |
| every direction of a fold | reset: base = the a priori clamps, no kept measurements, τ += B | the clamps hold under the exact model |

This path was added after the failure of Section 7.3. Its test is Section 7.5.

<!-- src: FREEZE-V3.md §1 tables -->

## 6 Protocol

All development (design, diagnosis, tuning) used seeds 430000–430099. Validation seeds 440000–440999 were reserved,
and the generator refuses them unless a freeze record is approved and its manifest matches.

Each validation followed the same order:
1. A freeze document fixes the hypothesis, the candidate, the scoring rules and the seed block, and a manifest pins
   every file the run uses by sha256.
2. The full pipeline is rehearsed on development seeds.
3. A commit that changes only the document's status line approves it. The runner refuses to start without that line,
   a matching manifest, a clean tree and the fixed environment.
4. The run generates the block once; the scorer applies the fixed rules in a fixed order: integrity, then soundness
   (an alarm on an admissible run, an alarm before t*, or an uncertified alarm is a FAIL), then completeness
   (undetermined fault runs at most 1 %), then misses and the target.
5. Nothing is rerun except after an infrastructure failure as defined in advance; the verdict is recorded as it came
   out, with a dated record.

Every score was reproduced byte for byte on a second machine and again by an independent scorer written from the
rules alone, using only the Python standard library. Each block was used once. A failed candidate is not repaired on
its block: a new candidate needs a new freeze and the next unused block.

The environment was CPython 3.12.13, numpy 2.5.5, scipy 1.18.1 and HiGHS 1.12.0.

<!-- src: FREEZE-V1/V2/V3.md; RECORD-2026-11-19 and -21 "Provenance" -->

## 7 Results

### 7.1 Development: the memory-loss curve

Table 1 (development, 1,081 certified detection events; not validation).

| monitor | state | D_paired | misses | detections at t* |
|---|---|---|---|---|
| template TS only | 42 numbers | 0.386 | 4 | 897 |
| window W = 64 | ≤ 18 kept | 0.643 | 0 | 1037 |
| window W = 128 | ≤ 28 kept | 0.815 | 0 | 1063 |
| window W = 192 | ≤ 35 kept | 0.824 | 0 | 1073 |
| window W = 256 | ≤ 45 kept | 0.9992 | 0 | 1079 |

The curve is not smooth: between W = 192 and 256 the gain comes from a few slow-drift runs whose separating
information lies far back. On 430010 (drift 0.0005 °C/s, ramp ambient), W = 192 detects at 3,449 and W = 256 at t* = 695.
With a cap of 64, development data never kept more than 45 measurements, so nothing was evicted. Caps of 40 and 32
detected identically on all 1,320 rows, with 420 and 21,821 evictions.

<!-- src: DIAG-3-RESULTS.md "size–loss curve"; amendment 6 part 2 (K1, K2, K = 40 table, K = 32) -->

**Smoothing against filtering.** On the four diagnosis runs, the filtering fold never recovers run 430027 at any W
(it stays at 1,429 against t* = 579), and recovers 430010 only to 3,449 at W = 256 (t* = 695). The smoothing fold
detects both at t* (at W = 128 and W = 256). [PENDING: B5, the forward-only window, on the validation block.]

<!-- src: DIAG-3-RESULTS.md phase 1 tables -->

### 7.2 Validation 1: the template tier

Block 440000–440199 (9,600 runs; 7,201 certified events, 4 undetermined fault runs).

| | target | D_paired | seed bootstrap 95 % | misses (IM: 24) | soundness | later than IM | verdict |
|---|---|---|---|---|---|---|---|
| inv4p (16 numbers) | 0.10 | 0.152 | [0.107, 0.205] | 20 | 0 | 0 | PASS |
| TS / cyl16p (42 numbers) | 0.25 | 0.387 | [0.323, 0.452] | 16 | 0 | 0 | PASS |

No monitor flagged any of the 2,395 admissible runs. The C float64 builds equal the Python implementation on all
9,600 runs.

<!-- src: RECORD-2026-11-18-validation.md Verdicts -->

### 7.3 Validation 2: the window tier fails on one LP

Block 440200–440399. The window (then without the fallback path of Section 5.4) reached D_paired 0.995 with no miss
(IM missed 14). On one healthy run with edge noise (440243, E0, ramp), one fold LP ended unsolved in HiGHS in all three
attempts at t = 945, and the frozen code recorded an uncertified alarm. Under the frozen order, that row is a
soundness violation and an uncertified alarm, and the verdict is **FAIL** before any accuracy rule is reached. The
accuracy numbers are reported with the failure and are not a validation.

A diagnosis afterwards, outside the scored run, replayed the row deterministically. The failure was confined to one
of the 42 fold directions; the other 41 solved faces bound that direction at −0.209 °C (its previous base bound was
−0.187 and its clamp 1.683). That observation became the fallback of Section 5.4.

<!-- src: RECORD-2026-11-19-validation.md (verdict, diagnosis) -->

### 7.4 Validation 3: the window tier with its fallback path

Block 440400–440599.

| | target | D_paired | seed bootstrap 95 % | misses (IM: 27) | soundness | uncertified | verdict |
|---|---|---|---|---|---|---|---|
| WM / F3 (W = 256, B = 16, K_cap = 64) | 0.80 | 0.9952 | [0.9899, 0.9995] | 0 | 0 | 0 | PASS |

- 7,255 certified events; 7,243 detected exactly at t* (IM: 5,257). Lag p90 0 s and maximum 212 s (IM: 55 s and
  2,215 s). No run was later than IM.
- 7,258 alarms, all certified, the largest certified margin −0.0147 mC; three of them on fault runs the oracle left
  undetermined.
- The remaining lag sits in three cells: drift 0.0005 and 0.001 °C/s with ramp ambient, and drift 0.002 °C/s with rw
  ambient. Drifts carry 99.8 % of IM's lag.
- **The fallback path never ran on this block.** WM solved 53,968,652 LPs; 722 needed a retry, and every LP was
  solved within its three attempts. The validation therefore supports the window's accuracy and the soundness of its
  normal path; the fallback path rests on its proof and on Section 7.5.
- At most 65 measurements kept, at most 445 LP rows and 679 variables.

<!-- src: RECORD-2026-11-21-validation.md -->

### 7.5 The fallback path under injected solver failures

A separate pre-registered test injected solver failures into WM on 1,200 fresh runs (25 seeds of a separate
namespace) in six settings: 1 % and 10 % of fold-direction LPs; 1 % of a_s-range and certificate LPs; every direction
of every fourth fold; 10 % of fold directions together with every P_J LP; every upper-side certificate LP. All
criteria held in every setting: no alarm on an admissible run, none before t*, every alarm certified, at most 65
kept measurements, the fallback counters equal to the injection log, and every fallback path reached (for example
375,725 implied P_J bounds and 22,600 full resets). The exact audit of two settings checked 7,300,179 bounds with no
violation.

The cost is in detection, as expected: with every fourth fold reset, 30 events were missed and D_paired was −5.21;
with every upper certificate failing, 174 were missed and D_paired −29.24. With 1 % and 10 % fold failures nothing was
missed. One detection in the 10 % setting came 45 samples later than without injection.

<!-- src: RECORD-2026-11-21-fb.md; settings = FB-PLAN.md table -->

**The solver's process.** In the runs above the LPs run in WM's own process. A solver that ends its process (as the
interior-point solver did in 8 of the oracle's 117,606 attempts in validation 3, by a segmentation fault) would end
the run before any fallback could see it. In a variant, WM's LPs run in a long-lived child process; if the child ends
or does not answer in 120 s, it is replaced and the attempt counts as failed, so the fallbacks of Section 5 apply.
Without injection the variant equals WM in every recorded field on 6 development rows. On the 1,400 development rows
the child then ended itself before 15,320 LPs, in all three attempts of each (half by exit, half by a segmentation
fault; two per thousand fold LPs, one per thousand a_s-range LPs, a fifth of the implied-bound LPs and half of the
certificate LPs). Every run completed. No alarm came on an admissible run or before t*, every alarm was certified,
the fallback counters equalled the injection log on every row, and at most 65 measurements were kept. The price was
again in detection: 497 detections came later (median 5 samples) and 3 slow-drift events were missed; none came
earlier. Two documented paths lead there: an alarm whose certificate cannot be computed is not raised, and a
measurement checked against a failed a_s-range LP is not kept. Their shares were not computed.

<!-- src: RECORD-2026-11-21-iso.md; ISOLATION-PLAN.md section 2 (rates); RECORD-2026-11-21-validation.md lines
193-200 (8 of 117,606 oracle attempts, all highs-ipm) -->

### 7.6 Precision and microcontrollers

**float32 keeps soundness and loses the gain.** Built with float32 tables, the template state was sound on the first
validation block, including the 800 healthy runs with noise exactly at ±δ. But TS in float32 reached D_paired 0.212
(target 0.25) and was later than IM on 52 runs; inv4p in float32 reached 0.004 with 28 misses and was later than IM on
130 runs. Theorem 3 holds in exact arithmetic, not in float32. Neither float32 build was the object of a hypothesis.

<!-- src: RECORD-2026-11-18-validation.md lines 92–105 -->

**ESP32, float64 tables.** The C implementation of TS with the validated float64 tables ran on an ESP32 (240 MHz)
on all 1,400 development rows, 5,040,000 samples. On every sample the alarm flag and a 16-byte hash of the full state
equalled the PC build's (pre-registered; negative controls detected a 1e-6 change of one input and a single flipped
bit). Per sample: 3.63 ms median, 4.56 ms maximum over these runs; a float32 build takes 0.49 ms.

<!-- src: MCU-NOTES 2d, 2e -->

**8-bit AVR, float32 tables.** On an ATmega328P (16 MHz, 2 KB SRAM) the float32 build used at most 602 bytes of SRAM
and 28,064 bytes of flash, at 74–76 ms per sample. On 30 pre-registered development rows its first flagged sample
equalled the PC float32 build's on every row. Its state is not bit-equal: the board's binary64 is faithful but not
correctly rounded, and the largest measured difference in a support was 7.2e-7 °C, far below the margins at which the
test turns but not covered by the pads by construction.

<!-- src: MCU-NOTES 2c, 2f -->

**The C state against the exact model.** A check in exact rational arithmetic found two gaps in the frozen C state.
(i) The command part S is computed in binary64 and its rounding is covered by no pad: the frozen C state is sound
against the exact model for |v| ≤ δ − ε, with ε = 4.85e-13 °C (9.9e-13 °C on the AVR). (ii) Two start supports were
1.11e-16 °C short; the first step absorbs the shortfall. A revised C state closes both by construction, with the
slab δ + η and exact start sums, so that it is sound for |v| ≤ δ. Pre-registered checks accepted it: the same first
flag as the frozen C state on all 1,400 development rows, bit-equality with its PC build on the ESP32 over 5,040,000
samples, and the same first flag as its PC build on the AVR on 30 rows. On development data the fix cost no
detection. It is not validated on fresh seeds. The same check of the validated Python template is open at the 1e-21
level (two rate pads 2.1e-21 °C below their exact value).

<!-- src: MCU-NOTES 2g, 2h; C1-PLAN.md -->


### 7.7 Baselines

[PENDING: B1 constrained zonotopes [Scott et al. 2016], B2 strip-intersection zonotopes [Alamo et al. 2005],
B3 constant-gain zonotopic observer [Combastel 2015], B4 interval observer, B5 forward-only window
[Kesavan and Lee 2001 style], tuned on development rows and frozen before the window tier's validation block;
BASELINE-PLAN.md. Report memory against D_paired and misses, with WM and TS.]

### 7.8 How much the results lean on the ambient box

A descriptive study on development seeds, pre-registered without pass or fail, asked two questions.

*A wider assumed box.* On the 1,320 development rows (true ambient within [23, 27]), widening the assumed box to
[22, 28] multiplied IM's lag against the frozen-box t* by 2.9 and TS's by 4.1; to [21, 29], by 3.5 and 5.2. Misses
rose from 8 to 32 and 55 (IM) and from 4 to 28 and 51 (TS). The whole increase is in the three slowest drift cells;
jumps, faster drifts, gain, noise and stuck faults do not depend on the box. TS stays about 17,500 s of lag ahead of
IM at every box, so its relative gain falls from 40 % to 14 % and 11 %. No monitor flagged an admissible row or flagged
before t*, at any box. These lags mix two losses: what a monitor discards, and what the weaker assumption no longer
gives (the exact detector is later too; its wider-box t* was not computed). WM was not run with a wider box, since
the box enters its LP, certificates and fallbacks.

*Broken assumptions, healthy sensor.* With the frozen assumptions and healthy sensors, an ambient rate twice the bound
caused no alarm in any monitor on 60 runs. A rate five times the bound caused certified alarms of WM on 4 of 60 runs
(two paths, both arms) and none of IM or TS: the most informed monitor is the first to prove that the model is
violated. A 1 °C step in the ambient was flagged by all three on every run, 1 to 10 samples after the step. An
ambient path starting outside the box was flagged by all three within 3 samples of the start; a slow excursion out of
the box was not tested. Every one of these alarms is correct about the model and wrong about the sensor.

<!-- src: RECORD-2026-11-21-ambient.md; results/v3/ambient/amb-443d8b30-mac/ (summary.json, report.json) -->

Development data had already shown why slow-drift detection leans on the box. In those cells the alarm often comes when z exceeds the top of the
box plus δ, so that every healthy explanation has to push T_A against the wall: on every development run where a
window variant without T_A box rows between nodes was later than the full window, z reached 2.22–2.30 (shifted
units) in the 256 samples before t*.

<!-- src: FREEZE-V2.md §1 "The ambient box matters to the result" (DIAG-3 amendment 5) -->

## 8 What went wrong

The records keep every failure. The ones that changed the method:

1. **One unsolved LP failed a validation** (Section 7.3). The window's rules said an unsolved fold is an uncertified
   alarm. The rule was sound; it was not complete. The fallback path of Section 5.4 is the result, tested on a new
   block and under injection.
2. **The model in floating point was not the model.** The first window LP and the template tables were built
   against the binary64 matrix, whose rows do not sum to one, and against data with their own simulation error. A
   later revision moved every exact computation to the simulator's recurrence with its parameters read as rationals,
   and added η for the data. Before that revision the template state came within 1.9e-14 to 3.0e-14 °C of a false
   alarm on 48 of the 80 development runs with edge noise: observed, not proved impossible.
3. **The C state had two gaps of order 1e-13 and 1e-16** (Section 7.6), found by a check written after the
   microcontroller runs. One more, at 2.1e-21 in the Python template, is still open.
4. **float32 breaks dominance** (Section 7.6). The development rehearsal before the first validation already showed
   it: the float32 build of the 16-number template detected 430098 drift 0.002 °C/s rw at 906, 240 s after IM.
   The validation was then written to claim Theorem 3 for float64 only.
5. **Claims corrected after review.** An earlier note read as if a drift rate within ρ and room in the box were enough
   for a healthy twin (Proposition 4 gives a counterexample). Another said that "no alarm" means an admissible
   explanation exists; that holds for the exact test only, not for an outer approximation. "A measurement redundant
   at arrival stays redundant" is false once the base is folded: a looser base can make it active again, so dropping
   it is sound but lossless only empirically.
6. **The dense reference was the less accurate one.** When the compressed window was first checked against the dense
   window LP, it disagreed by 2.8e-6 °C on one support. The dense LP had been solved loosely (equality residual
   6.2e-5); the compressed window was exact to 1e-11.

<!-- src: RECORD-2026-11-19-validation.md; FREEZE-V2.md §1; RECORD-2026-11-18-validation.md addendum; MCU-NOTES 2g;
V3_NOTES §4, §8; DIAG-3-RESULTS.md (amendment 3, C0); item 4 = FREEZE-V1.md §8 rehearsal -->

## 9 Related work

**Set-membership fault detection.** Consistency-based detection with unknown-but-bounded uncertainty is reviewed by
Puig [2010]. Parallelotope consistency tests [Ingimundarson et al. 2005], zonotope-based tests [Ingimundarson et al.
2009] and constrained zonotopes [Scott et al. 2016] give sound detectors with bounded complexity; set-valued observers
do the same for LTV and LPV systems [Rosa et al. 2010; Silvestre et al. 2017]. Interval observers are the other main
family [Pourasghar et al. 2019; Tang et al. 2019]. Saccani et al. [2022] apply a set-based approach to thermal faults
of a lithium-ion cell and report earlier detection than an interval method based on constraint propagation. These
works compare detectors with one another; here every detector is compared with the exact detection time.

**Bounded memory and the exact set.** The complexity of the exact set cannot be bounded a priori, which motivates
bounded-complexity filters [Sznaier et al. 2011; Blanchini and Sznaier 2012]. Casini et al. [2024] plot the volume of
bounded-memory estimators against memory depth relative to the exact feasible set, for state estimation. Scott et al.
[2016] compare constrained zonotopes with the exact set on estimation volume, and sweep complexity against detection
time without the exact observer.

**Moving windows.** Kesavan and Lee [2001] detect faults with a moving horizon whose initial set is an outer bound
propagated forward [as summarized by Ingimundarson et al. 2005; CHECK primary text]. Set-valued moving-horizon
estimation appears in output-feedback MPC [Brunner et al. 2018; Köhler et al. 2021] and in distributed estimation
[Segovia et al. 2022]. The arrival cost of quadratic MHE has filtering and smoothing forms [Rao et al. 2001;
Haseltine and Rawlings 2005]; set-membership smoothing exists for state estimation [Garulli et al. 1999; Li et al.
2026]. WM's base update is the smoothing form, used for detection in a bounded window.

**Certified LP bounds.** Rigorous bounds from approximate duals with boxed variables are due to Neumaier and
Shcherbina [2004] and Jansson [2004], reviewed by Guilbeau et al. [2017]; they are used in exact MIP [Cook et al.
2013] and in program analysis with template polyhedra [Wang et al. 2021].

**Embedded solvers.** DAQP [Arnström et al. 2022] and EIQP [Wu et al. 2025] target embedded LPs and QPs with bounded
iteration counts; they are dense, and WM's sparse LP of up to 445 rows and 679 variables does not fit them as is.
Because the certificate holds for any multiplier vector, a solver stopped at an iteration cap would keep WM sound and
cost only delay (Section 5.3); its worst-case time is not shown.

## 10 Limitations and open problems

- One plant with known parameters, in simulation, under assumed noise and ambient laws. With uncertain parameters
  the exact set is no longer convex.
- The ambient box (c) carries slow-drift detection (Section 7.8). A wrong box can make a healthy record inconsistent.
- WM runs on a desktop with HiGHS. An embedded LP solver with a bounded iteration count is the open step; the
  certificate makes early stopping safe but not free.
- No worst-case execution time for either tier; the microcontroller times are maxima over the runs shown.
- WM's fallback path was never exercised on validation seeds; it rests on its proof and on injected failures.
- The facet count of X_k, and a principled minimal template, are open.
- The undetermined oracle runs (healthy runs with noise exactly at ±δ, about half of them) are judged by ground
  truth, not by the oracle.

## 11 Reproducibility

The code, the frozen documents, the manifests and every record cited are in the project repository [TBD: public URL
after release]. Each validation is identified by its approval commit and manifest hash:
- validation 1: approval 8e589911, manifest e8dd60f1…;
- validation 2: approval 35b344df, manifest cc7adffa…;
- validation 3: approval 948b46b0, manifest 0a40cbdf….

## Declarations

- Funding: none.
- Competing interests: none.
- Use of AI tools: [TBD by the author; required by Elsevier and Wiley policies, Section 3 of RELATED-WORK-NOTES.md].

## References

To be converted to BibTeX. Labels as in experiments/v3/RELATED-WORK-NOTES.md, which records for each whether the full
text was read. Added after that file:
- G. Saccani, D. Locatelli, A. Tottoli, D. M. Raimondo, "Model-based thermal fault detection in Li-ion batteries using
  a set-based approach," IFAC-PapersOnLine 55(6), pp. 329–334, 2022. doi:10.1016/j.ifacol.2022.07.150 [abstract only]
- P. Rosa, C. Silvestre, J. S. Shamma, M. Athans, "Fault detection and isolation of LTV systems using set-valued
  observers," Proc. 49th IEEE CDC, pp. 768–773, 2010. doi:10.1109/CDC.2010.5717634 [metadata only]
- D. Silvestre, P. Rosa, J. P. Hespanha, C. Silvestre, "Set-based fault detection and isolation for detectable linear
  parameter-varying systems," IJRNC 27(18), 2017. doi:10.1002/rnc.3814 [metadata only; CHECK volume/issue]
