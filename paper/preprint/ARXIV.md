# Preprint submission (metadata)

- **Title:** How much of the record does a sound fault monitor need? Bounded-memory set-membership detection of sensor
  faults, measured against the exact oracle
- **Authors:** Can Koç
- **Subject:** TechRxiv: Robotics and Control Systems. arXiv: eess.SY (Systems and Control), cross-list math.OC
- **License:** CC BY 4.0
- **Comments:** 30 pages, 4 figures, 7 tables. Code, frozen plans and records: https://github.com/X6e3/sdts-fault-monitors
- **Upload:** `sh make_arxiv.sh OUT` builds `OUT/sdts-arxiv.tar.gz` (main.tex, main.bbl, fig_*.tex, figdata/*.dat);
  refs.bib is left out because the .bbl is included. TeX comments stay in the upload; the `% src:` comments name
  the dated record in the repository behind each number.
- **Before upload:** a check that arXiv's pdfLaTeX build matches `OUT/main.pdf` (built here with Tectonic).

## Abstract for the submission form (plain text; arXiv allows at most 1,920 characters)

A set-membership fault detector alarms when no admissible explanation of the sensor record exists. For a linear plant with bounded noise and a bounded unknown input, the exact detector keeps a polytope of unbounded description, so an embedded detector keeps a bounded outer approximation and detects later. We measure that loss. On a two-node thermal plant with one sensor, a known heat input, an unknown ambient temperature and ten sensor fault classes, a certified LP over the full history gives each certified run's exact detection time, and bounded monitors are scored against it under the same assumptions: a difference is what a monitor loses. A template polyhedron with 42 supports needs no solver, is proved sound under explicit rounding conditions and, in exact arithmetic, never later than the interval monitor. Its frozen float64 builds meet those conditions only for noise at least 4.86e-13 °C inside the bound; a revised C state meets them in full; not yet validated on fresh seeds, its PC build raises the frozen builds' alarms on all 19,200 runs of two validation blocks. On an ESP32 the C builds match their PC builds bit for bit on 5.04 million samples. On 9,600 fresh, preregistered runs the template removed 38.7% of the interval monitor's paired lag. A window LP over 256 samples with a smoothing base update removed 99.5% of that lag on a second fresh block of 9,600 runs with no missed certified event; all 7,258 alarms carried weak-duality certificates. An earlier freeze of the window failed validation on one unsolved LP; we report it and its sound replacement. No memory budget can certify the error of a sensor drift that an admissible ambient path reproduces. Seven baselines in two comparisons fixed beforehand all lagged our monitors at their memory budgets; the nearest set-based one, a strengthened interval observer, removed 8.8% of the interval monitor's lag, the template 44.2%.
