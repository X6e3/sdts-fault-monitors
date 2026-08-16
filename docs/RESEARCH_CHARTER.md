# Research Charter — Software-Defined Temporal Sensing

## 1. Central question

Can a physical sensor stream be transformed, using only causal software state, into a new temporal observable whose value reflects the effect of history at the present time?

Let the physical measurement be \(x_t\). A software-defined temporal sensor maintains

\[
S_t = F(S_{t-1}, x_t; \theta)
\]

under bounded memory and deterministic execution.

The objective is not to replay \(x_{0:t}\). The objective is to compress history into a state whose distinctions are relevant to present or future system behavior.

## 2. Terminology

### Physical measurement
The instantaneous sensor observation \(x_t\).

### History-derived temporal state
A bounded causal state \(S_t\) that can differ for histories that share the same instantaneous observation.

### Virtual temporal sensor
An implementation that exposes \(S_t\) as a software-defined observable with an explicit state contract.

### Software-Defined Temporal Sensing (SDTS)
The broader research concept: deriving measurable, bounded temporal observables from physical sensor history in software.

### DMREDA
A candidate temporal-state construction inside SDTS. DMREDA is not synonymous with the paradigm.

## 3. Core claim ladder

### C0 — Bounded causal state
There exists a fixed-size deterministic recurrence

\[
S_t = F(S_{t-1},x_t)
\]

with no dependence on future samples.

### C1 — History-derived distinction
There exist two admissible histories \(H_A,H_B\) such that

\[
x_t^{(A)} = x_t^{(B)}
\]

but

\[
S_t^{(A)} \ne S_t^{(B)}.
\]

This establishes history sensitivity, not usefulness.

### C2 — Non-redundancy
The relevant distinction in \(S_t\) cannot be reconstructed from the declared instantaneous observable set alone, and proposed state reductions are rejected by exact collision witnesses where possible.

### C3 — Behavioral necessity
For at least one state distinction, merging two states that appear equivalent under a reduced representation causes divergent behavior under a common admissible continuation.

### C4 — Future relevance
The temporal state contributes predictive information about a predeclared future variable beyond the instantaneous physical observation:

\[
I(Y_{t+1:t+H};S_t\mid x_t) > 0.
\]

Operationally, this should be demonstrated primarily with predeclared proper scoring rules or nested predictive models rather than relying only on difficult mutual-information estimators.

### C5 — Robust temporal sensing
C1–C4 remain valid under declared perturbations such as unseen trajectories, process-parameter shifts, sensor noise, quantization, timing variation, and sampling-rate changes within a stated operating envelope.

## 4. Explicit non-claims

Until separately demonstrated, the project does not claim:

- superior fault-detection accuracy;
- superiority to EWMA, LSSM, Kalman filters, observers, or other estimators as general methods;
- unique optimality of a DMREDA recurrence geometry;
- reconstruction of the complete past;
- identification of a physical latent state merely because history is represented;
- time-scale invariance;
- arbitrary semantic-memory decoding;
- causal discovery from observational predictive information alone.

## 5. Downstream separation

The core research object is \(S_t\). Downstream functions are separate:

\[
S_t \to \text{detector}
\]

\[
S_t \to \text{control policy}
\]

\[
S_t \to \text{prognostics}
\]

\[
(S_t,Q_t) \to Q_{t+1}
\]

Performance of a downstream consumer must not be silently promoted into a claim about the temporal representation itself.
