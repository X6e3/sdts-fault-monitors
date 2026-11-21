# Paper plan (2026-11-21)

Source: `preprint/main.tex` and `preprint/refs.bib` (v0.2, 2026-11-21), built with Tectonic 0.17.0 on the Mac
(`tectonic -X compile main.tex`; installed with Homebrew on 2026-11-21, chosen over TeX Live because the Mac had 7 GB
free). The source is standard LaTeX and also builds with pdflatex and BibTeX. `DRAFT.md` is v0.1, kept as it was; new
text goes into `main.tex` only.

## Form

- First target: a full-length preprint (no page limit), then a journal or conference version cut from it. Decided
  2026-11-21 (preprint first). arXiv category to choose (eess.SY is the likely one); a first submission there may
  need an endorsement.
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
| 5 Window tier, certificates, fallback | draft | — (full proof in Appendix A, 2026-11-22) |
| 6 Protocol | draft | — |
| 7.1–7.6 Results | draft | — |
| 7.7 Baselines | placeholder | block run on 440400–440599 (configurations frozen 2026-11-21, `9438dffa`) |
| 7.8 Ambient box | draft | — |
| 7.5 Process isolation | draft | — |
| 8 What went wrong | draft | — |
| 9 Related work | draft | primary texts below |
| 10 Limitations | draft | — |
| 11 Reproducibility | draft | public URL |
| Appendix A (proof of Proposition 3) | draft (2026-11-22) | — |
| Figures | four drafted (2026-11-21) | baselines on Figure 2 after the block run |

## Figures (drafted 2026-11-21)

In `preprint/fig_*.tex` (pgfplots and TikZ, compiled with the paper). Data from `figures/make_data.py`, which writes
`preprint/figdata/` (the `.dat` files and `figures.json`) from the records and from DEV runs it regenerates. Colours:
slots 1 to 3 of the dataviz reference palette, validated; IM, TS and WM keep one colour, dash pattern and marker each
in every figure.

1. The window between two folds (schematic), section 5.2.
2. D_paired against the numbers kept, development and validation, section 7.1. Baselines go here after the block
   run.
3. Run 430010: the upper edge of each monitor's band near t*, and the running median width of the a_s-range,
   section 7.1.
4. Validation 3: the lag per fault cell, IM against WM, section 7.4.

## Before submission

- Read the primary texts marked UNVERIFIED or ABSTRACT that the draft leans on: Kesavan and Lee 2001, Saccani et al.
  2022, Rosa et al. 2010, Alamo et al. 2005, Combastel 2015, Sankaranarayanan et al. 2008.
- Every number in DRAFT.md against its `src` comment; every [CHECK] and [PENDING] resolved.
- The AI-use statement: written 2026-11-22 (general form, no tool list; the author's choice). A journal that asks
  for tool names gets a provider-level line at submission.
- An outside reading of the whole draft.
- The post-freeze code fixes of FREEZE-V3.md §5 before the code is released.
