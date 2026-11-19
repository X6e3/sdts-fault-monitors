# SDTS v3: related work, first pass (2026-11-19)

**Status:** working notes from a web search.
- Most entries were read from abstracts and indexes, not full texts.
- Every claim about a paper must be checked against the paper before it is cited.
- "Not found" means not found in this pass, not that it does not exist.

**Reading order:** what SDTS adds comes first (section 1). The known building blocks follow, with where SDTS stands on
each (section 2).

## 0. Corrections from the full-text pass (L1, partial, 2026-11-19; to be confirmed in its report)

The full-text pass was cut short; its report is pending. Its interim findings narrow section 1:

- **The window is not ours.** Kesavan and Lee (2001) already reduce the growing full-history LP to a fixed window with
  an outer-bounded initial set. Brunner, Müller and Allgöwer (CDC 2016, TAC 2018) also use set-valued estimates from a
  fixed number of recent measurements.
- **Set-membership smoothing exists:** Morrell and Stirling (1988), Liu, Shen and Deller (2017), Meslem and Ramdani
  (2018, forward–backward), and Li, Cong and Zhou (2024, optimal set-membership smoothing). What remains to be checked
  is whether any of them uses later measurements to update the base of a moving window for fault detection, as the
  smoothing fold does.
- **Comparing with the exact set is not ours either.** Scott et al. (2016) already compare bounded-complexity
  estimates with the exact set. The narrower candidate is the loss measured in **detection delay** against the
  full-history oracle, as a memory–loss curve, on fault-detection runs, with a pre-registered validation.
- **DAQP:** its current documentation supports pure LPs. The note below that it needs a regularisation is to be
  corrected once checked.
- **The safe-bounds review:** its authors and the two sign errors it corrects are confirmed in the pass. The details
  will be in the report.

**So the contribution, as it stands now:**
1. The memory–detection-loss curve against the exact oracle.
2. The diagnosis of where the loss comes from.
3. The exact compressed window, with every fold and alarm certified and audited.
4. The ambient-box finding.
5. The pre-registered validation.

The window, set-membership smoothing and the comparison with the exact set are prior art, to be cited, not claimed.

## 1. What SDTS adds (so far, from this pass)

Each item is backed by a measured, independently checked result in `diag/DIAG-3-RESULTS.md`. Whether it is new
is hedged: it comes from this first pass only.

1. **The yardstick.** Bounded-memory monitors are measured against the exact full-history information state (the oracle),
   with a size–loss curve (W = 64…256, K = 32…64) and a frozen, pre-registered validation. The literature states the
   growth problem and proposes bounded-complexity filters. A loss-against-the-exact-set curve on a fault-detection
   benchmark did not come up in this pass.
2. **The diagnosis of the loss:**
   - template geometry at cut events (DIAG-1 and 2);
   - long-memory TA cuts (430010);
   - smoothing against filtering for the base (DIAG-3: filtering never recovers 430027).

   The quadratic-MHE literature has filtering and smoothing arrival-cost updates. Whether the set-membership
   literature compares them like this is to be checked.
3. **The exact compressed window.**
   - The ambient increments stay explicit, so each segment zonotope is exact with 3 rows.
   - Convexity removes the ac and as boxes between nodes.
   - It is numerically more accurate than the dense LP (the C0 finding).
   - Individually, these are standard tools (condensing, zonotopes). Their combination and the exactness argument are
     ours.
4. **Every fold and every alarm certified, with the coefficient rounding enclosed,** and audited in exact rational
   arithmetic. The method is Neumaier and Shcherbina's; applying it to every step of an online monitor, with an audit,
   may be the less common part.
5. **The finding about the ambient box:** detection of slow drifts leans on the assumed range of TA.

## 2. The known building blocks, and where SDTS stands on them

| SDTS ingredient | known as | where to start |
|---|---|---|
| The information state as a set; detection = no consistent explanation | set-membership (unknown-but-bounded) estimation; consistency-based fault detection | Schweppe 1968 (the origin, ellipsoids); the review of set-membership fault diagnosis in IJAMCS 2010 |
| No false alarm within the assumed bounds | the guarantee of set-membership fault detection | Puig and co-workers (zonotopes and parallelotopes, consistency tests) |
| A window of exact constraints plus an outer bound of the initial set | moving-horizon set-membership estimation; "a moving horizon strategy where an outer bound of the initial set is propagated" | Ingimundarson et al. (CDC-ECC 2005, parallelotopes); Segovia, Puig, Duviella (ISA Trans. 2022, set-membership MHE) |
| Bounded memory, keeping only the last r measurements | bounded-complexity set-membership filters; the observation that the exact consistency set's complexity cannot be bounded a priori | Sznaier, Yilmaz, Blanchini (ACC 2011) |
| The arrival cost, and filtering against smoothing updates of it | moving horizon estimation (quadratic arrival cost) | Rao, Rawlings and co-workers. Check whether their smoothing update has a set-membership counterpart. |
| Fixed-direction polytopes (cyl16p) | template polyhedra, support functions | Le Guernic and Girard (support functions, 2010); Sankaranarayanan et al. (template polyhedra) |
| An exact set representation with complexity reduction | constrained zonotopes | Scott, Raimondo, Marseglia, Braatz (Automatica 2016) |
| Interval observers as the other main family | interval-observer fault detection, and comparisons with set-membership | Pourasghar, Puig, Ocampo-Martínez (IJRNC 2019) |
| A certified LP bound from approximate duals over boxed variables | safe bounds in linear programming | Neumaier and Shcherbina (Math. Prog. 2004); Jansson (2004, rigorous LP bounds). A later review reports errors in the printed formulas. Ours is derived directly from weak duality with every variable boxed, and audited in exact arithmetic (5,676 + 84 bounds, no violation). Cite the full texts and the review when writing. |
| Exact rational LP | exact MIP and LP solving | Cook, Koch, Steffy, Wolter |
| An LP or QP on an MCU with a guaranteed worst-case time | WCET-certified active-set solvers | DAQP (Arnström, Axehill; exact WCET for active-set MPC; an STM32F405 Cortex-M4 demonstration in a 2026 preprint). DAQP is a dual active-set solver for strictly convex QPs, so a pure LP needs a small quadratic regularisation; any dual still gives a valid bound, but how tight it is must be checked. EIQP (Wu, Braatz; execution-time certified, LP included). |

## 3. What a reviewer will ask, and what answers it

- **"How does this compare with zonotopic set-membership fault detection, constrained zonotopes or interval
  observers?"** A baseline comparison on the same scenarios is needed. Proposal: implement one or two baselines and
  compare them in a separate pre-registered study on a fresh block (440400+), after freeze 2, so that freeze 2 is not
  delayed or changed.
- **"One plant, known parameters."** A second plant, and a model-mismatch study.
- **"Can it run on an MCU?"** The DAQP and EIQP line shows that a certified worst-case time for active-set solvers on a
  Cortex-M4 is possible. The LP size here (about 400 rows) is the open question.

## Sources (as found; to be checked)

- Schweppe 1968, IEEE TAC 13(1): https://scilit.net/publications/46d584c2a6122e70fda6d4f44324655c
- Set-membership FD and FTC review (IJAMCS 2010): https://eudml.org/doc/208012
- Zonotopic sensor FD (HAL): https://hal-centralesupelec.archives-ouvertes.fr/hal-01002477
- Ingimundarson et al., parallelotopes and consistency (CDC-ECC 2005): https://folk.ntnu.no/skoge/prost/proceedings/cdc-ecc05/pdffiles/papers/2056.pdf
- Set-membership distributed MHE (TU Delft repository): https://repository.tudelft.nl/record/uuid:8a248228-bacb-439a-9d3a-f7145b47e59b
- Sznaier, Yilmaz, Blanchini, bounded complexity filters (ACC 2011): https://skoge.folk.ntnu.no/prost/proceedings/acc11/data/papers/0730.pdf
- Constrained zonotopes (Scott et al.): https://portal.mardi4nfdi.de/wiki/Publication:286264
- Le Guernic and Girard, support functions: https://hal.archives-ouvertes.fr/hal-00765598
- Neumaier and Shcherbina, safe bounds: https://optimization-online.org/?p=9243 ; the review: https://www.reliable-computing.org/archive/preprints/safe-bounds-review-revision-2.pdf
- Exact MIP (Cook et al.): https://math.uwaterloo.ca/~bico/papers/exactmip_bb_short.pdf
- DAQP on an STM32F405 (2026 preprint): https://arxiv.org/abs/2603.09342 ; exact WCET for implicit MPC: https://deepai.org/publication/exact-worst-case-execution-time-analysis-for-implicit-model-predictive-control
- Köhler, Müller, Allgöwer, online estimation bounds (arXiv 2105.03427): https://arxiv.org/abs/2105.03427
