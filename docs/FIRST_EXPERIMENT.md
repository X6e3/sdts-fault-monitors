# Experiment 001 — History-Derived State Without Detector Semantics

Status: specification draft; implementation intentionally absent.

## Claim
C1 — History-derived distinction.

## Hypothesis
There exist admissible histories \(H_A,H_B\) ending at the same instantaneous physical observation but producing distinct temporal states.

## Required construction

Create paired trajectories with

\[
x_t^{(A)} = x_t^{(B)}
\]

and controlled differences in the pre-terminal history.

Initial history families:

1. slow monotonic approach vs fast transient-and-return;
2. sustained plateau vs recent crossing;
3. equal endpoint and equal local slope, different older trajectory;
4. time-reversed prehistories where physically admissible.

## Primary output

No class label and no detector score.

Record:

- full candidate state \(S_t\);
- exact/epsilon state collision;
- coordinate-wise separation;
- state-byte count;
- deterministic replay hash.

## Controls

- current-only representation;
- one-pole EWMA as a trivial history-bearing control;
- a small fixed-window representation if the budget permits.

These controls test whether the candidate preserves a different or richer distinction; they are not detector baselines.

## Success condition

C1 succeeds if at least one predeclared admissible paired-history family creates reproducible state separation while the declared instantaneous observable set is matched.

C1 success does not establish future relevance. That is Experiment 002/Phase 4.
