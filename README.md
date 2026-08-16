# DMREDA / Software-Defined Temporal Sensing

Research reset initiated 2026-08-16.

## Research objective

Investigate whether a physical sensor stream can be transformed in software into a bounded, causal, deterministic temporal state that exposes future-relevant information not present in the instantaneous measurement alone.

The core object is

\[
S_t = F(S_{t-1}, x_t; \theta),
\]

not a detector. Detection, control, prognostics, and authority logic are downstream consumers of \(S_t\).

## Project separation

- `src/`, `tests/`, `experiments/`: clean post-reset research line.
- `archive/pre-reset-2026-08-16/`: immutable historical artifacts. They are evidence/history, not authoritative validation for the new claim system.
- `docs/RESEARCH_CHARTER.md`: definitions, claims, and non-claims.
- `docs/ROADMAP.md`: staged validation plan and stop/go criteria.
- `docs/VALIDATION_RULES.md`: experiment discipline.

No legacy implementation is imported into the active tree until a new experiment specification explicitly requires it.
