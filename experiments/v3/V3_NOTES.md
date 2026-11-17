# SDTS v3 — the information state of the thermal problem under a resource budget

Branch `sdts-v3/template-state`. Labels:
- **MATH:** proved here.
- **DEV:** measured on v3 DEV seeds 430000–430099.
- **HYP:** not shown.
- **OPEN:** an open problem.

No v2 FINAL, CAL or TRAIN data was used to build or tune anything in v3. The seeds 440000–440999 are reserved
for an independent check of a frozen v3 and were never generated.

## 0. Question

How accurately can a bounded, deterministic, online state represent what the history of one sensor says about
its physical explanations? Two limits apply:
- the representation must never claim more than the history and the assumptions allow;
- the budget is MCU-class RAM, flash, cycles and precision.

The yardstick is v2's certified full-history oracle, under **identical decision semantics**: the first sample
at which no explanation with b = 0 and |noise| ≤ δ exists.

## 1. Setting

The setting is that of v2: known plant, known command (S known, so z = y − S), unknown ambient TA, and the
assumptions:
- (a) |v| ≤ δ;
- (b) |ΔTA| ≤ ρ_A;
- (c) TA ∈ [23, 27];
- (e) start at the P0 steady state.

Temperatures are shifted by −25 °C. The physical state is s = (ac, as, TA):
- ac and as are the ambient responses of the core and surface nodes;
- s_{k+1} = M s_k + e3·w_k, with |w_k| ≤ ρ_A;
- M = [[A11, A12, 0], [A21, A22, B2], [0, 0, 1]];
- the eigenvalues of M are 0.984 (slow), 0.716 (fast) and 1 (the ambient integrator).

## 2. The exact information state is three-dimensional (MATH)

**Theorem 1.** Define the information state recursively:

    X_0     = {t·(1,1,1) : t ∈ [LO, HI]} ∩ {s : |z_0 − s_2| ≤ δ},
    X_{k+1} = (M X_k ⊕ {0}×{0}×[−ρ_A, ρ_A]) ∩ {LO ≤ s_3 ≤ HI} ∩ {|z_{k+1} − s_2| ≤ δ}.

X_k is the set of physical states at k that some admissible past explains, z[0..k] is consistent iff
X_k ≠ ∅, and the oracle's t* = min{k : X_k = ∅}.

*Proof.* An admissible past is a sequence TA[0..k] with (b) and (c). Together with (e), it fixes s_0..s_k by
s_{j+1} = M s_j + e3 (TA[j+1] − TA[j]). Every constraint of the LP at time j — the noise bound (a), the box
(c) and the rate (b) between j and j+1 — involves s_j, or s_j and s_{j+1}. Induction on k: s_{k+1} is
explained by an admissible past iff s_{k+1} = M s_k + e3 w for some explained s_k and some |w| ≤ ρ_A, and
s_{k+1} meets (c) and the measurement at k+1. The oracle's LP is the same feasibility problem with the
intermediate states written out. ∎

**Consequences.**
- History beyond X_k carries no information about any future consistency decision. "More history" is never
  needed in principle; what can be needed is a *finer description* of a convex polytope in R^3.
- X_k is a compact convex polytope: linear images, Minkowski sums with a segment and intersections with
  halfspaces preserve that.
- Its number of facets is not bounded a priori (**OPEN**: whether it stays bounded for this plant).

## 3. What the v2 machine keeps and discards (MATH)

v2 keeps an interval I_k ⊇ π_2(X_k) (the projection on as):

    I_{k+1} = (I_k ⊕ [−ρ_A, ρ_A]) ∩ slab ∩ box.

It uses the lemma |as[k+1] − as[k]| ≤ ρ_A: the TA→as response is nonnegative with unit sum, and (e) gives
Δas[1] = 0.

What it discards is the rest of s: the error state e = (ac − TA, as − TA). In particular, the as-velocity
v·s_k = as[k+1] − as[k], with v = M^T e2 − e2, is itself a state with dynamics. A surface that has been rising
at the full rate cannot fall at the full rate one sample later, because the core lags. The interval allows
±ρ_A at every step independently.

**Corollary.** v2 and the oracle use the same assumptions and the same decision, so every difference between
v2's first-inconsistent sample and t* is information discarded by the representation. It is not a difference
in decision rule.
- X_k ⊆ {s : s_2 ∈ I_k}, so v2 can only be later.
- On v2 FINAL this loss reached 1617 s (drift_0.002) and two missed detections (FINAL record). That is cited
  only as a statement about v2.

## 4. v3 candidate: template state with offline bases and reachable-set clamps

**Definitions.**
- Fixed unit directions D = {d_1..d_n}, with ±e1, ±e2, ±e3 ∈ D.
- State h ∈ R^n, representing P = {s : D s ≤ h}.
- Support: supp_P(g) = min{λ·h : λ ≥ 0, D^T λ = g}. This is LP duality and is exact for nonempty P.
- Its optimum lies at a basic solution, i.e. a triple of directions. M and D are fixed, so every feasible
  triple and its λ for the needed g (M^T d_i, and ±e2) is computed **offline**. At run time a support is a min
  over 3-term dot products: no LP, no allocation.

**Per sample:**
1. The as-range of P is [−supp(−e2), supp(e2)]. If it misses [z − δ, z + δ]: TUTARSIZ (absorbing).
2. Tighten h(±e2) with the measurement.
3. Predict h'_i = supp(M^T d_i) + ρ_A |d_i3|.
4. Clamp with the TA box and the reachable-set caps (section 5).

**Lemma 2 (reachable set, MATH).**
- The error e = (ac − TA, as − TA) obeys e_{k+1} = F e_k + g w_k, with F = M[:2,:2], g = (−1, −1) and e_0 = 0.
- So every reachable e lies in E_∞ = ⊕_j F^j g [−ρ_A, ρ_A].
- Its support is h_E(q) = ρ_A Σ_j |q·F^j g|, computed offline with a bounded tail.
- **DEV numbers:**
  - |ac − TA| ≤ 0.135;
  - |as − TA| ≤ 0.105;
  - |ac − as| ≤ 0.030;
  - in the as-velocity direction, h_E = ρ_A **exactly**. v2's lemma is one face of this set.

**Theorem 2 (soundness, MATH).** For any such D, any subset of each direction's bases and outward rounding,
P_k ⊇ X_k for all k. Hence v3-TUTARSIZ at k implies the oracle is inconsistent at k: never earlier than the
oracle and never on an admissible record.

*Proof.* Induction:
- P_0 ⊇ X_0, because h0 is the segment's support.
- Intersecting both sides with the slab keeps the inclusion.
- A min over fewer bases is ≥ the exact support. The exact support of M(P ∩ slab) ⊕ w-segment in d_i is
  supp(M^T d_i) + ρ_A |d_i3|. A polytope described by upper bounds on the supports of a superset is a superset.
- The clamps are valid for every reachable state (Lemma 2 and (c)).
- Rounding: every computed support is an upper bound. The pads bound the dot-product rounding, the table
  residual, and in C the rounding of λ to the stored precision. ∎

**Theorem 3 (dominance over v2, MATH).** If ±e2 and ±v̂ ∈ D (v̂ = v/|v|), the clamps are applied, and the
basis {e2, v̂, x} is kept (for any x completing a basis), then π_2(P_k ∩ slab_k) ⊆ I_k for all k. So v3 is
never later than v2.

*Proof.* Induction:
- supp_{P_{k+1}}(e2) ≤ supp_{P_k ∩ slab}(M^T e2) = supp(e2 + v) ≤ h(e2) + |v| h(v̂) ≤ max I_k + ρ_A, because the
  clamp gives |v| h(v̂) ≤ h_E(v) = ρ_A.
- The lower end is symmetric.
- Intersecting with the slab and the box gives ⊆ I_{k+1}.

e2 carries no w term. ∎

**Theorem 4 (no budget can fix the drift certificate: an impossibility, MATH + DEV).**
- Let the record y come from a faulty sensor with additive error e(t). If some admissible ambient TA′
  reproduces y as a healthy record (h * (TA′ − TA) = e within the noise slack), then *every* method whose
  output is a function of (y, P) gives the faulty run an output it also gives a healthy run.
- In particular, no state of any size (the full history included) can bound the sensor error below sup|e| over
  such twins.
- A slow linear drift (rate ≤ ρ_A, with box room) is such an error.
- **DEV witness** (certified oracle, full history): 430056 and 430059, drift_0.001/E0. The oracle's *exact*
  constant-offset interval is [−0.70, 0.12] and [−0.48, 0.24]; inside ±1. The true end error is 3.17 and
  3.18 °C.
- So the "drift certificate" counterexample of v2 is a property of the *hypothesis class* (constant offsets),
  not of compression.
- What a budget *can* fix: on v2 FINAL 420004 the machine certified at R = 1 a run that the oracle found
  inconsistent. That one is compression loss.

## 5. Resources

- **RAM:** n reals (h) plus S in double (2 numbers) plus a flag.
- **Flash:** the basis tables: 3 indices plus 3 λ per entry, and per-direction pads.
- **Cycles per sample:** about 3 × entries MAC plus mins.
- **Precision:**
  - The template update is sound in float32, because the pads are computed for the stored precision.
  - The command part S must not be float32: its recursion error is unbounded over 3600 steps and is not
    covered by any pad. S is double; on a Cortex-M4 it is about 10 double operations per sample in software.

The measured tables are in section 6. They are counts from the generated tables, not timings on hardware
(**OPEN**: Cortex-M timing).

## 6. DEV results

Filled in by `RESULTS.md` after the DEV run.

## 7. Alternatives, and why templates were implemented first

| representation | state | update | what it loses here |
|---|---|---|---|
| exact polytope (V or H) | grows | hull or LP online | nothing; not MCU-bounded |
| v2 interval on as | 2 | closed form | the error state e (section 3) |
| ellipsoid (Schweppe / Fogel–Huang) | 9 | closed form | cannot express the box or the thin reachable slab; approximate strip intersection |
| zonotope, fixed order | 3 + 3q | exact linear map and Minkowski sum | the strip and box intersection, which happens every sample, is approximate |
| sliding-window LP | W samples | LP online | exact inside the window, but an LP per sample |
| **template + offline bases + clamps** | n | min of 3-term dot products | the linear map is replaced by its template hull |

None of these ingredients is new in itself:
- template polyhedra, from abstract interpretation;
- set-membership estimation;
- mRPI sets, from robust control;
- enumeration of LP bases, from parametric programming.

No novelty is claimed without a literature check. What is specific here:
- the combination as an LP-free MCU update for fixed dynamics;
- the clamps that make it dominate v2;
- the certified comparison against a full-history oracle under identical semantics.

## 8. Model-consistent is not sensor-correct

- **TUTARSIZ** proves the record violates the model and the assumptions. It does not say which fault.
- **Not TUTARSIZ** says only that some admissible explanation exists. Any fault in the indistinguishable set
  passes (Theorem 4).
- The state's bounds on (ac, as, TA) are conditional on the healthy hypothesis. They are not measurements of
  the plant.

## 9. Open problems

- Is the facet count of X_k bounded for this plant? How many directions does exact agreement need?
- Choice of D: is there a principled minimal set (orbits, invariants) that matches the oracle on a fault
  class?
  - DEV says the decisive lost information is the ambient lower bound (−TA directions, 0.02–0.06 °C looser than
    exact).
  - Faces orthogonal to TA help: cyl16 gives −38 % total lag.
  - Transported past-measurement normals do not help.
  - Near the detectability boundary, small looseness becomes thousands of seconds.
- Alternative explanations as extra dimensions: b (4-D) and drift (5-D). Theorem 4 says certification of the
  sensor error fails once drift is in the class. What remains certifiable?
- Uncertain plant parameters: X_k becomes non-convex (bilinear). Is there a sound bounded state?
- Validation on the reserved seeds 440000–440999 after freezing a v3 candidate; timing on a real Cortex-M.
