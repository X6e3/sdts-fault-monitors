# Roadmap — DMREDA / Software-Defined Temporal Sensing

## Phase 0 — Reset and provenance

Goal: separate historical work from the new claim system.

- Preserve all pre-reset artifacts byte-for-byte.
- Generate SHA-256 manifest.
- Mark old detector-aligned R3/R4 ladders and Semantic Tournament interpretations as historical, not authoritative for the SDTS claim ladder.
- Begin a clean active tree with no imported legacy implementation.

Exit condition: archive is immutable and the new research charter is frozen.

## Phase 1 — Formal interface, no algorithm heroics

Define a minimal temporal sensor interface:

- `reset()`
- `step(x_t, dt) -> S_t`
- `snapshot()/restore()`
- `state_bytes()`
- deterministic update contract
- explicit current-observable set \(O_t\)

Define what counts as state, parameter, input, and downstream consumer.

Exit condition: two independent implementations could obey the same contract without knowing the intended detector/application.

## Phase 2 — C1: exact history-distinction experiment

Construct paired admissible histories satisfying a declared instantaneous collision, initially:

\[
x_t^{(A)}=x_t^{(B)}.
\]

Then progressively strengthen matching constraints, for example current residual/current finite-window energy if those variables exist in the candidate recurrence.

Measure:

- exact state equality/inequality;
- collision rate under each representation;
- which state coordinates carry the distinction;
- sensitivity to sign, ordering, duration, and time reversal.

No detector is attached.

Exit condition: reproducible exact witnesses show a nontrivial history-derived distinction, or C1 is rejected for the candidate.

## Phase 3 — C2/C3: state reduction and continuation witnesses

For each proposed state coordinate or reduction:

1. find states that collide under the reduced representation;
2. apply the same admissible future suffix;
3. test whether exact future state/output behavior diverges.

This produces a behavioral necessity map of the recurrence state.

Targets include:

- ring/order state;
- accumulated state;
- lag state;
- regime/control state;
- authority state, but only as a separate downstream automaton.

Exit condition: a documented sufficient state and a set of proven/rejected reductions.

## Phase 4 — C4: future relevance on a ground-truth dynamical system

This is the decisive SDTS experiment.

### Recommended first plant: two-node thermal system

Use a system with hidden thermal energy/core temperature and one exposed physical sensor. Different heating histories can produce the same measured surface temperature while leaving different internal thermal states and therefore different future trajectories.

The temporal sensor receives only the exposed sensor stream.

Construct matched pairs such that

\[
x_t^{(A)}\approx x_t^{(B)}
\]

while the hidden plant state differs.

Choose a predeclared future target such as:

\[
Y = x_{t+H}
\]

under a common future input schedule, or a declared hidden-state quantity used only as ground truth.

Compare held-out nested models:

\[
Y \leftarrow x_t
\]

versus

\[
Y \leftarrow (x_t,S_t).
\]

Primary claim requires a statistically stable out-of-sample predictive gain.

Exit condition: C4 supported or rejected on the frozen plant family.

## Phase 5 — Representation baselines under equal questions

Only after C4 protocol is frozen, compare representations such as:

- current-only;
- derivative/slope state;
- EWMA state;
- fixed FIR/ring summaries;
- general stable LSSM;
- DMREDA candidate.

The question is not “which detector wins?” It is:

- how much conditional future-relevant information is retained;
- at what state-byte cost;
- at what compute cost;
- with what robustness.

Produce a Pareto frontier rather than a single winner label.

## Phase 6 — C5 robustness

Stress the frozen recurrence and probe under:

- sensor noise;
- quantization;
- bias/drift;
- missing samples;
- variable \(dt\);
- sample-rate changes;
- unseen plant parameters;
- unseen heating/cooling profiles;
- time dilation/compression.

Declare the operating envelope where the claim remains valid.

## Phase 7 — Embedded realization

Only after the scientific state contract is stable:

- reference Python implementation;
- strict C implementation;
- fp32/fixed-point decision;
- no-heap bounded memory;
- transactional state update;
- checkpoint invariants;
- Python/C parity;
- target-MCU cycle/WCET and RAM/flash measurements.

These establish deployability, not C4 by themselves.

## Phase 8 — Physical bench

Build a minimal thermal bench:

- heater/power resistor;
- thermal mass;
- exposed sensor used by DMREDA;
- internal/reference sensor used only as ground truth;
- MCU-controlled reproducible power profiles;
- timestamped acquisition.

Generate different histories that converge to the same exposed temperature, then apply the same future power input. Test whether \(S_t\) distinguishes histories that produce measurably different future evolution.

This is the cleanest route from synthetic C4 evidence to a physical “virtual temporal sensor” demonstration.

## Phase 9 — Publication claim

Only if C4 survives held-out and physical validation:

> A bounded causal software state derived from a physical sensor history exposes future-relevant temporal information not contained in the instantaneous physical measurement alone.

DMREDA-specific superiority is a separate claim and requires separate evidence.
