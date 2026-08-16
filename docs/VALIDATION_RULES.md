# Validation Rules

## 1. Claim-first experiments

Every experiment must begin with:

1. exact claim identifier;
2. falsifiable hypothesis;
3. admissible data-generating process;
4. state/observable definitions;
5. primary metric;
6. acceptance and rejection criteria;
7. frozen seeds or sealed test data;
8. declared baselines and why each baseline is relevant.

No experiment may be interpreted as evidence for a claim it was not designed to test.

## 2. Baseline semantics

EWMA, derivative, FIR/ring projections, LSSM, Kalman-style filters, or learned recurrences may be used as representation baselines where appropriate. They are not automatically detector competitors.

Comparisons must state the question explicitly, e.g.:

- history-distinction retention;
- conditional future-prediction gain;
- state bytes;
- operations per sample;
- robustness to timing/noise;
- exact continuation-state sufficiency.

## 3. No detector leakage into core validation

False positives, ROC curves, alarm rates, confirmation logic, refractory logic, or fault-classification accuracy are downstream metrics unless the tested claim explicitly concerns a downstream detector.

They cannot establish SDTS C1–C4 by themselves.

## 4. Exact witnesses before classifiers

When a property can be established by a constructive collision witness or exact state transition, prefer that over a classifier score.

Example pattern:

\[
R(H_A)=R(H_B)
\]

under a proposed reduction, but for a common suffix \(u\),

\[
B(H_Au)\ne B(H_Bu).
\]

This rejects the reduction directly.

## 5. Future relevance

For C4, compare nested predictive models on held-out trajectories:

- baseline: \(Y \leftarrow x_t\) (plus any explicitly allowed current observables);
- temporal: \(Y \leftarrow x_t,S_t\).

Use proper scoring rules appropriate to \(Y\), such as negative log-likelihood, Brier score, CRPS, or MSE for a clearly defined regression target.

The primary result is the held-out conditional gain, not raw accuracy.

## 6. Independence and split discipline

Split at the trajectory/process-realization level, not at individual samples when samples share history.

No tuning on FINAL data. Any post-hoc diagnostic is labeled post-hoc and cannot upgrade the frozen claim.

## 7. Determinism and artifact integrity

Each frozen result package records:

- source commit;
- environment lock;
- configuration;
- seeds/data hashes;
- executable command;
- result hashes;
- clean-tree status.

Python/C parity is implementation verification, not scientific validation.

## 8. Failure is informative

A failed claim remains in the repository with its protocol and result. It is not rewritten into a different success claim after seeing the data.
