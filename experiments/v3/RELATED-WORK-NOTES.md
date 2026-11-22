# SDTS v3: related work (checked against full texts, 2026-11-19)

**Status:** this replaces the first pass, which was read from abstracts. Each claim about a paper carries a label:
- **VERIFIED:** the full text was read; the page or section is given.
- **ABSTRACT:** the official abstract only.
- **UNVERIFIED:** the metadata only (the DOI resolves to these authors, title and venue), or a summary in another paper.

All DOIs were checked against Crossref or OpenAlex on 2026-11-19. "Not found" means not found in the papers read
and the targeted searches of this pass, not that it does not exist.

## 1. What SDTS adds

1. **The yardstick: detection-delay loss against the exact full-history oracle, as a function of memory**
   (W = 64…256, K = 32…64), with a pre-registered validation. **Not found.** The closest prior work:
   - Scott, Raimondo, Marseglia and Braatz (2016) compare bounded-complexity estimators with the exact set, but on
     state-estimation volume and radius (section 5, pp. 131–132, Figs. 3–5; VERIFIED). Their fault-detection study
     sweeps the complexity n_c against detection time (section 6, Fig. 7) and leaves the exact observer out: "We did
     not compare the exact observer Poly because it was found in Section 5 to have much higher complexity" (p. 133).
   - Casini, Garulli and Vicino (2024) plot the log-volume of bounded-memory estimators against the memory depth
     (q_p, q_o), relative to the smallest box around the exact feasible set (section 6, Fig. 5, p. 10; VERIFIED). This
     is state estimation, not detection.
   - Sznaier, Yilmaz and Blanchini (2011) keep the last r measurements. Their filter is optimal within that r-memory
     scenario, and they do not compare it with the exact set (sections III–IV; VERIFIED).
2. **The smoothing fold, and the diagnosis of the loss.** The base of the moving window is updated with the
   measurements up to the fold time, for fault detection. On DEV, a filtering-only base never recovers 430027.
   **Not found** for set-membership fault detection. The neighbours:
   - **Quadratic MHE** has both arrival-cost updates. The filtering form uses the data before the window; the
     smoothing form also uses the data inside it. Rao, Rawlings and Lee (2001) and Tenny and Rawlings (2002) are
     recapped in Haseltine and Rawlings (2005): section 5 and appendix 10.1–10.2 (VERIFIED, report version). Haseltine
     and Rawlings warn that a linearised smoothing prior can bias multimodal nonlinear posteriors (section 6.2). In the
     linear set-membership case the smoothed set is convex, and an outer template bound of it stays sound.
   - **Set-membership smoothing exists for state estimation:**
     - Garulli, Vicino and Zappa (1999): UNVERIFIED, cited by Li et al.;
     - Liu, Shen and Deller (2017), forward–backward ellipsoids: ABSTRACT;
     - Meslem and Ramdani (2018), forward–backward intervals: ABSTRACT;
     - Li, Cong, Zhou and Dong (2026), optimal set-membership smoothing with constrained zonotopes: VERIFIED. It is
       batch smoothing over [0, T], with no complexity reduction, no moving window and no detection.
   - Morrell and Stirling (1988, 1991) smooth convex sets of Gaussian distributions, not unknown-but-bounded sets
     (ABSTRACT).
   - The other parts of the diagnosis are from our own runs: the template geometry at cut events, and the long-memory
     TA cuts.
3. **The exact compressed window.** The ambient increments stay explicit, so each segment is exact with 3 rows.
   Convexity removes the ac and as boxes between nodes. A measurement is kept only if it is not redundant on arrival.
   The result is numerically more accurate than the dense LP (the C0 finding). Its parts are standard tools:
   - condensing, i.e. eliminating the states (for example Jerez, Kerrigan and Constantinides 2011, cited in EIQP);
   - exact affine maps and intersections of constrained zonotopes (Scott et al. 2016, Proposition 1; VERIFIED).

   The combination and the exactness argument are ours.
4. **Every fold and every alarm certified, with the coefficient rounding enclosed, and audited in exact rational
   arithmetic.** In the papers read on set-membership estimation and detection, the solvers are all uncertified
   floating-point ones (linprog, CPLEX, YALMIP, MPT, IPOPT). Certifying every step of an online monitor was
   **not found**.
   - The method is that of Neumaier and Shcherbina (2004) and Jansson (2004).
   - Safe bounds have been applied before in exact rational MIP (Cook, Koch, Steffy and Wolter 2011/2013; VERIFIED)
     and in static program analysis with template polyhedra (Wang et al. 2021; VERIFIED).
5. **The ambient-box finding:** detection of slow drifts leans on the assumed range of TA. It is structurally like the
   parameter box Θ in Ingimundarson et al. (2005), where a fault inside Θ cannot be detected when the rate bound λ is
   infinite (sections II and V-B; VERIFIED).

## 2. Prior art to cite, not to claim

| SDTS ingredient | prior work | label, and what it does |
|---|---|---|
| The information state as a set; detection = no consistent explanation | Witsenhausen 1968; Schweppe 1968; Bertsekas and Rhodes 1971; Puig 2010 (review of set-membership fault diagnosis) | Schweppe and Puig: ABSTRACT. The others: UNVERIFIED. |
| No false alarm within the assumed bounds | Ingimundarson et al. 2005 (Def. 2, p. 994); Scott et al. 2016 (Eq. (34)); Puig 2010 | VERIFIED. SDTS adds the numerical certificate. |
| **A moving window with an outer-bounded initial set, for fault detection** | **Kesavan and Lee 2001** | Summarised in Ingimundarson et al. (2005, section I, p. 993; VERIFIED there, UNVERIFIED in the primary text): "a moving horizon strategy where an outer bound of the initial state was propagated" with recursive optimal bounding parallelotopes (ROBP), forward only. The first pass attributed this phrase to Ingimundarson et al.; it describes Kesavan and Lee. |
| Parallelotope consistency tests | Ingimundarson, Bravo, Puig, Alamo 2005; zonotopes in Ingimundarson et al. 2009 | 2005: VERIFIED. A recursive single-step parallelotope, with no window. They remark that an LP over only the last M points does not use all the data (section IV-A, p. 996). 2009: UNVERIFIED. |
| Set-valued estimates from a fixed number of recent measurements | Brunner, Müller, Allgöwer (CDC 2016; TAC 2018); Köhler, Müller, Allgöwer (2021) | For output-feedback MPC, not detection. Brunner: ABSTRACT. Köhler: VERIFIED (section III-C), with a forward scalar bound on the initial error. |
| Set-membership and moving-horizon estimation combined | Segovia, Puig, Duviella (ISA Trans. 2022) | VERIFIED. A two-stage distributed state estimator: forward zonotope filtering tightens the box constraints of a quadratic MHE. It is not moving-horizon set-membership fault detection. |
| Bounded memory; the exact set's complexity cannot be bounded a priori | Sznaier, Yilmaz, Blanchini 2011; Blanchini and Sznaier 2012; Casini, Garulli, Vicino 2024 | Sznaier et al. and Casini et al.: VERIFIED. Blanchini and Sznaier: UNVERIFIED. |
| The arrival cost: filtering against smoothing | Rao, Rawlings, Lee 2001; Rao, Rawlings, Mayne 2003; Haseltine and Rawlings 2005 | Haseltine and Rawlings: VERIFIED. Rao, Rawlings, Mayne: ABSTRACT. Rao, Rawlings, Lee: UNVERIFIED. See 1.2. |
| Fixed-direction polytopes (cyl16p) | Sankaranarayanan, Dang, Ivančić 2008 (template polyhedra); Le Guernic and Girard 2010 (support functions) | UNVERIFIED. |
| An exact set representation with complexity reduction | Scott et al. 2016; Raghuraman and Koeln 2022 | Scott et al.: VERIFIED. A constrained zonotope is exactly a convex polytope (Theorem 1). Linear maps, Minkowski sums and intersections are exact and grow linearly. Raghuraman and Koeln: UNVERIFIED. |
| Interval observers as the other main family | Pourasghar, Puig, Ocampo-Martínez 2019; Tang et al. 2019; Althoff and Rath 2021 | Pourasghar: ABSTRACT. Tang et al.: as implemented in CORA (VERIFIED there). |
| A certified LP bound from approximate duals over boxed variables | Neumaier and Shcherbina 2004; Jansson 2004; Guilbeau, Hossain, Karhbet, Kearfott, Sanusi, Zhao 2017 (the review) | Neumaier and Shcherbina, and the review: VERIFIED. Jansson: partial (only a PostScript copy of the 2002 report was read, not the printed Theorem 6.1). The review corrects two printed sign errors in Neumaier and Shcherbina: the multiplier is λ ≈ y − z, not z − y (above Eq. (8), p. 7); and in the rounding scheme (Eq. (11), lines 3 and 5) the residual is Aᵀλ − c, not Aᵀλ + c. Our bound is derived directly from weak duality with every variable boxed, and audited in exact arithmetic (5,676 + 84 bounds, no violation), so it does not depend on the printed formulas. |
| Exact rational LP | Cook, Koch, Steffy, Wolter (IPCO 2011; MPC 2013) | VERIFIED. QSopt_ex and safe floating-point bounds inside SCIP. |
| An LP or QP on an MCU with a certified worst-case time | DAQP (Arnström, Bemporad, Axehill); its STM32F405 demonstration (Wikner, Arnström, Axehill 2026); EIQP (Wu, Xiao, Braatz 2025) | **Correction:** DAQP solves LPs directly, with proximal-point iterations (documentation, VERIFIED; Arnström, Bemporad, Axehill 2022, ABSTRACT). The first pass said it needs a quadratic regularisation; that was wrong. DAQP is dense. The STM32F405 demonstration is a strictly convex QP with 60 variables and input boxes only (VERIFIED). EIQP supports LPs with a data-independent iteration count, but it uses a dense LU of size about n + 1 (VERIFIED). Neither fits the 409-row, 643-variable sparse LP of F in about 200 KB as it is. |

**For the MCU (our inference, not from the literature):** the certified bound holds for any multiplier vector,
because every variable is boxed. A solver stopped at an iteration cap therefore gives a looser fold, or an alarm left
uncertified and so not raised. Neither is unsound; the cost is detection delay. A custom sparse dual simplex with a
cap therefore keeps the soundness guarantee. Its worst-case time would still have to be shown.

## Sources

DOIs checked against Crossref or OpenAlex on 2026-11-19.

**Read in full (VERIFIED):**
- M. Althoff, "Guaranteed State Estimation in CORA 2021," ARCH21, EPiC Series in Computing 80, pp. 161–175, 2021. doi:10.29007/7m2k
- M. Casini, A. Garulli, A. Vicino, "Set membership state estimation for discrete-time linear systems with binary sensor measurements," Automatica 159, 111396, 2024. doi:10.1016/j.automatica.2023.111396
- M. Casini, A. Garulli, A. Vicino, "Adaptive Threshold Selection for Set Membership State Estimation With Quantized Measurements," IEEE TAC 70(9), pp. 5736–5749, 2025. doi:10.1109/TAC.2025.3545704
- W. Cook, T. Koch, D. E. Steffy, K. Wolter, "A hybrid branch-and-bound approach for exact rational mixed-integer programming," Math. Prog. Comp. 5(3), pp. 305–344, 2013. doi:10.1007/s12532-013-0055-6 (IPCO 2011 version: doi:10.1007/978-3-642-20807-2_9)
- J. T. Guilbeau, Md. I. Hossain, S. D. Karhbet, R. B. Kearfott, T. S. Sanusi, L. Zhao, "A review of computation of mathematically rigorous bounds on optima of linear programs," J. Global Optim. 68(3), pp. 677–683, 2017. doi:10.1007/s10898-016-0489-2
- E. L. Haseltine, J. B. Rawlings, "Critical evaluation of extended Kalman filtering and moving-horizon estimation," Ind. Eng. Chem. Res. 44(8), pp. 2451–2460, 2005. doi:10.1021/ie034308l (TWMCC report 2002-03 read)
- A. Ingimundarson, J. M. Bravo, V. Puig, T. Alamo, "Robust Fault Diagnosis using Parallelotope-based Set-membership Consistency Tests," CDC-ECC 2005, pp. 993–998. doi:10.1109/CDC.2005.1582287
- C. Jansson, "Rigorous Lower and Upper Bounds in Linear Programming," SIAM J. Optim. 14(3), pp. 914–935, 2004. doi:10.1137/S1052623402416839 (2002 report, partly read)
- J. Köhler, M. A. Müller, F. Allgöwer, "Robust output feedback model predictive control using online estimation bounds," arXiv:2105.03427, 2021
- Y. Li, Y. Cong, X. Zhou, J. Dong, "Optimal Set-Membership Smoothing," IEEE TAC 71(5), pp. 3327–3334, 2026. doi:10.1109/TAC.2025.3632158
- A. Neumaier, O. Shcherbina, "Safe bounds in linear and mixed-integer linear programming," Math. Prog. 99(2), pp. 283–296, 2004. doi:10.1007/s10107-003-0433-3
- J. K. Scott, D. M. Raimondo, G. R. Marseglia, R. D. Braatz, "Constrained zonotopes: A new tool for set-based estimation and fault detection," Automatica 69, pp. 126–136, 2016. doi:10.1016/j.automatica.2016.02.036
- P. Segovia, V. Puig, E. Duviella, "Set-membership-based distributed moving horizon estimation of large-scale systems," ISA Trans. 128B, pp. 402–413, 2022. doi:10.1016/j.isatra.2021.10.036
- M. Sznaier, B. Yilmaz, F. Blanchini, "Bounded Complexity ℓ∞ Filters for Switched Systems," ACC 2011, pp. 2006–2011. doi:10.1109/ACC.2011.5991274
- T. Wang, L. Chen, T. Chen, G. Fan, J. Wang, "Making Rigorous Linear Programming Practical for Program Analysis," CP 2021, LIPIcs 210, 57. doi:10.4230/LIPIcs.CP.2021.57
- J. Wikner, D. Arnström, D. Axehill, "On Real-Time Feasibility of High-Rate MPC using an Active-Set Method on Nano-Quadcopters," arXiv:2603.09342, 2026
- L. Wu, W. Xiao, R. D. Braatz, "EIQP: Execution-time-certified and Infeasibility-detecting QP Solver," arXiv:2502.07738, 2025
- DAQP documentation: https://darnstrom.github.io/daqp/ (accessed 2026-11-19)

**Abstract only (ABSTRACT):**
- D. Arnström, A. Bemporad, D. Axehill, "A Linear Programming Method Based on Proximal-Point Iterations With Applications to Multi-Parametric Programming," IEEE L-CSS 6, pp. 2066–2071, 2022. doi:10.1109/LCSYS.2021.3138218
- D. Arnström, A. Bemporad, D. Axehill, "A Dual Active-Set Solver for Embedded Quadratic Programming Using Recursive LDLᵀ Updates," IEEE TAC 67(8), pp. 4362–4369, 2022. doi:10.1109/TAC.2022.3176430
- D. Arnström, D. Broman, D. Axehill, "Exact Worst-Case Execution-Time Analysis for Implicit Model Predictive Control," IEEE TAC 69(10), pp. 7190–7196, 2024. doi:10.1109/TAC.2024.3395521
- F. D. Brunner, M. A. Müller, F. Allgöwer, "Enhancing output feedback MPC for linear discrete-time systems with set-valued moving horizon estimation," CDC 2016, pp. 2733–2738. doi:10.1109/CDC.2016.7798675
- F. D. Brunner, M. A. Müller, F. Allgöwer, "Enhancing Output-Feedback MPC With Set-Valued Moving Horizon Estimation," IEEE TAC 63(9), pp. 2976–2986, 2018. doi:10.1109/TAC.2018.2791899
- J. Liu, Q. Shen, J. R. Deller, "A set-membership smoother for state estimation in disturbances of unknown distribution," CCC 2017, pp. 5038–5042. doi:10.23919/CHICC.2017.8028152
- N. Meslem, N. Ramdani, "Forward-Backward Set-Membership State Estimator Based on Interval Analysis," ACC 2018, pp. 5161–5166. doi:10.23919/ACC.2018.8431250
- D. R. Morrell, W. C. Stirling, "Set-valued filtering and smoothing," Asilomar 1988, pp. 236–240, doi:10.1109/ACSSC.1988.753990; IEEE Trans. SMC 21(1), pp. 184–193, 1991, doi:10.1109/21.101148
- P. F. Odgaard, J. Stoustrup, M. Kinnaert, "Fault-Tolerant Control of Wind Turbines: A Benchmark Model," IEEE TCST 21(4), pp. 1168–1182, 2013. doi:10.1109/TCST.2013.2259235
- M. Pourasghar, V. Puig, C. Ocampo-Martínez, "Interval observer versus set-membership approaches for fault detection in uncertain systems using zonotopes," IJRNC 29(10), pp. 2819–2843, 2019. doi:10.1002/rnc.4523
- V. Puig, "Fault diagnosis and fault tolerant control using set-membership approaches: Application to real case studies," IJAMCS 20(4), pp. 619–635, 2010. doi:10.2478/v10006-010-0046-y
- C. V. Rao, J. B. Rawlings, D. Q. Mayne, "Constrained state estimation for nonlinear discrete-time systems: stability and moving horizon approximations," IEEE TAC 48(2), pp. 246–258, 2003. doi:10.1109/TAC.2002.808470
- F. C. Schweppe, "Recursive state estimation: Unknown but bounded errors and system inputs," IEEE TAC 13(1), pp. 22–28, 1968. doi:10.1109/TAC.1968.1098790

**Metadata only (UNVERIFIED content):**
- T. Alamo, J. M. Bravo, E. F. Camacho, "Guaranteed state estimation by zonotopes," Automatica 41(6), pp. 1035–1043, 2005. doi:10.1016/j.automatica.2004.12.008
- M. Althoff, J. J. Rath, "Comparison of guaranteed state estimators for linear time-invariant systems," Automatica 130, 109662, 2021. doi:10.1016/j.automatica.2021.109662
- D. P. Bertsekas, I. B. Rhodes, "Recursive state estimation for a set-membership description of uncertainty," IEEE TAC 16(2), pp. 117–128, 1971. doi:10.1109/TAC.1971.1099674
- F. Blanchini, M. Sznaier, "A Convex Optimization Approach to Synthesizing Bounded Complexity ℓ∞ Filters," IEEE TAC 57(1), pp. 216–221, 2012. doi:10.1109/TAC.2011.2162893
- L. Chisci, A. Garulli, G. Zappa, "Recursive state bounding by parallelotopes," Automatica 32(7), pp. 1049–1055, 1996. doi:10.1016/0005-1098(96)00048-9
- C. Combastel, "Zonotopes and Kalman observers: Gain optimality under distinct uncertainty paradigms and robust convergence," Automatica 55, pp. 265–273, 2015. doi:10.1016/j.automatica.2015.03.008
- A. Garulli, A. Vicino, G. Zappa, "Optimal induced-norm and set membership state smoothing and filtering for linear systems with bounded disturbances," Automatica 35(5), pp. 767–776, 1999. doi:10.1016/S0005-1098(98)00212-X
- A. Ingimundarson, J. M. Bravo, V. Puig, T. Alamo, P. Guerra, "Robust fault detection using zonotope-based set-membership consistency test," IJACSP 23(4), pp. 311–330, 2009. doi:10.1002/acs.1038
- P. Kesavan, J. H. Lee, "A set based approach to detection and isolation of faults in multivariable systems," Comput. Chem. Eng. 25(7–8), pp. 925–940, 2001. doi:10.1016/S0098-1354(00)00315-X
- C. Le Guernic, A. Girard, "Reachability analysis of linear systems using support functions," Nonlinear Anal. Hybrid Syst. 4(2), pp. 250–262, 2010. doi:10.1016/j.nahs.2009.03.002
- V. Raghuraman, J. P. Koeln, "Set operations and order reductions for constrained zonotopes," Automatica 139, 110204, 2022. doi:10.1016/j.automatica.2022.110204
- C. V. Rao, J. B. Rawlings, J. H. Lee, "Constrained linear state estimation—a moving horizon approach," Automatica 37(10), pp. 1619–1628, 2001. doi:10.1016/S0005-1098(01)00115-7
- S. Sankaranarayanan, T. Dang, F. Ivančić, "Symbolic Model Checking of Hybrid Systems Using Template Polyhedra," TACAS 2008, LNCS 4963, pp. 188–202. doi:10.1007/978-3-540-78800-3_14
- S. M. Tabatabaeipour, P. F. Odgaard, T. Bak, J. Stoustrup, "Fault Detection of Wind Turbines with Uncertain Parameters: A Set-Membership Approach," Energies 5(7), pp. 2424–2448, 2012. doi:10.3390/en5072424
- W. Tang, Z. Wang, Y. Wang, T. Raïssi, Y. Shen, "Interval Estimation Methods for Discrete-Time Linear Time-Invariant Systems," IEEE TAC 64(11), pp. 4717–4724, 2019. doi:10.1109/TAC.2019.2902673
- H. S. Witsenhausen, "Sets of possible states of linear systems given perturbed observations," IEEE TAC 13(5), pp. 556–558, 1968. doi:10.1109/TAC.1968.1098995
