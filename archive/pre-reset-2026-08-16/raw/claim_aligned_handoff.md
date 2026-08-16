# DMREDA Claim-Aligned Validation Handoff

- Branch: `research/dmreda-claim-aligned-validation`
- Final HEAD: `8264f2a831a1b4766f940abcfd67e220f7bae9a2`
- Worktree: `/Users/x6e3/Documents/Codex/2026-08-14/read-only-audit-do-not-modify-2/work/dmreda-claim-aligned-validation`
- Required artifact directory: `claim_aligned/`
- Artifact manifest: `claim_aligned/SHA256SUMS`
- Manifest SHA-256: `e0f7399f7cfc7e1386ad8e091b4791b33de4c3195947191b885297ef351a11d3`
- Authoritative experiment result: `claim_aligned/results/CLAIM_ALIGNED_RESULTS_V2.json`
- Result file SHA-256: `1a1303cf622f8721d714a2e90694a696cce1d4478eacaece7fec5cdf7917091a`
- Overall classification: `R3. RESEARCH-SUPPORTED STRUCTURAL REPRESENTATION / AUTHORITY ARCHITECTURE`
- FaultyTesting accessed: `false`
- Git worktree status after commit: clean

Primary reading order:

1. `claim_aligned/CLAIM_ALIGNED_TECHNICAL_REPORT.md`
2. `claim_aligned/CLAIM_MATRIX.md`
3. `claim_aligned/REPRESENTATION_EXPERIMENTS.md`
4. `claim_aligned/HISTORY_COLLISION_WITNESSES.md`
5. `claim_aligned/MINIMAL_STATE_REASSESSMENT.md`
6. `claim_aligned/LITERATURE_POSITIONING_V2.md`
7. `claim_aligned/PAPER_CANDIDATE.md`

Verification:

- historical/repository suite: 240 tests, `OK`;
- claim-aligned contract suite: 8 tests, `OK`;
- H exact Python/C parity replay: 1,039,792 rows, byte-identical report;
- current-claim manifest: all 28 entries `OK`;
- frozen-history manifest: all 19 entries `OK`;
- claim-aligned manifest: all 32 entries `OK`.
