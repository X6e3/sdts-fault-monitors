# v3 independent validation — draft (not frozen, not run)

**Purpose:** check a frozen v3 candidate on data that played no part in building it.

## Data

- Seeds 440000–440999 (`dev_scenarios.VALIDATION`). They are not generated before the candidate and these rules
  are frozen in a dated commit.
- The DEV seeds (430000–430099) and every v2 range (TRAIN, CAL, FINAL) are excluded.

## To freeze before generating any validation data

1. **The candidate:**
   - template family and size;
   - pruning: none, or a table built on DEV only;
   - arithmetic: float32 or float64;
   - the C build and its table hash.
2. **The cells and scenario laws:**
   - the v2 cells;
   - ambient laws `rw` and `ramp`;
   - noise laws `uniform` and `edge`;
   - arms E0 and E1;
   - optionally new laws written before seeing data.
3. **The comparison:**
   - the v2 oracle (certified t*);
   - the v2 machine;
   - the candidate.

   Decision for all three: the first sample with no explanation at b = 0 and |noise| ≤ δ.

## Claims and how each is scored

| | claim | kind | fails if |
|---|---|---|---|
| V1 | candidate never flags a healthy run, at the noise edge included | MATH (Theorem 2) | any healthy run flagged → implementation bug, stop |
| V2 | candidate never earlier than the oracle's certified t* | MATH (Theorem 2) | any earlier → bug, stop |
| V3 | candidate never later than the v2 machine | MATH (Theorem 3; needs ±e2, ±v̂ and their bases kept) | any later → bug or a violated condition, stop |
| V4 | share of oracle-inconsistent runs where the candidate equals t*, and lag quantiles | empirical, reported | — |
| V5 | resources: state numbers, table entries, MAC per sample, flash bytes, measured cycles on a Cortex-M (if hardware is available) | reported | — |

V4 is reported, not predicted. A threshold may be added only if it is written before validation data exists.

## What validation can not show

- Anything about sensor correctness beyond the constant-offset class (Theorem 4).
- Anything under plant-parameter mismatch: out of scope; a separate protocol.
