# Paper plan (2026-11-21)

Working draft: `DRAFT.md` (Markdown with plain-text math). Converted to LaTeX once the content is stable; no TeX
installation exists yet on either machine.

## Form

- First target: a full-length preprint (no page limit), then a journal or conference version cut from it.
- Candidate venues (RELATED-WORK-NOTES.md §3): Automatica, IEEE TCST, IJRNC; IFAC SAFEPROCESS, CDC, ACC.
- Sole author.

## Status by section

| section | status | waits for |
|---|---|---|
| Abstract | draft | baselines sentence |
| 1 Introduction | draft | baselines contribution |
| 2 Problem | draft | — |
| 3 Information state, IM, Lemma 1, Proposition 4 | draft | — |
| 4 Template tier, Theorems 2–3 | draft | — |
| 5 Window tier, certificates, fallback | draft | decide: full proof in an appendix? |
| 6 Protocol | draft | — |
| 7.1–7.6 Results | draft | — |
| 7.7 Baselines | placeholder | DEV tuning (Arch), freeze of configs, block run on 440400–440599 |
| 7.8 Ambient box | draft | — |
| 7.5 Process isolation | placeholder | ISOLATION-PLAN.md run (Arch) |
| 8 What went wrong | draft | — |
| 9 Related work | draft | primary texts below |
| 10 Limitations | draft | — |
| 11 Reproducibility | draft | public URL |
| Figures | none yet | see below |

## Figures to make

1. The memory-loss curve: D_paired against state size (IM, inv4p, TS, W = 64…256), development and validation
   points marked apart; baselines added when they exist.
2. One run (430010 drift 0.0005 ramp): z, the as-ranges of IM, TS and WM, t*.
3. The window's anatomy: base at τ, nodes, kept measurements, fold at τ + 16 (diagram).
4. Per-cell lag, IM against WM (validation 3).

## Before submission

- Read the primary texts marked UNVERIFIED or ABSTRACT that the draft leans on: Kesavan and Lee 2001, Saccani et al.
  2022, Rosa et al. 2010, Alamo et al. 2005, Combastel 2015, Sankaranarayanan et al. 2008.
- Every number in DRAFT.md against its `src` comment; every [CHECK] and [PENDING] resolved.
- The AI-use statement (author's decision; Elsevier and Wiley require one).
- An outside reading of the whole draft.
- The post-freeze code fixes of FREEZE-V3.md §5 before the code is released.
