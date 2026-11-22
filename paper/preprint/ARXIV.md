# arXiv submission (metadata)

- **Title:** How much of the record does a sound fault monitor need? Bounded-memory set-membership detection of sensor
  faults, measured against the exact oracle
- **Authors:** Can Koç
- **Primary category:** eess.SY (Systems and Control); cross-list: math.OC
- **License:** CC BY 4.0
- **Comments:** 26 pages, 4 figures, 7 tables. Code, frozen plans and records: https://github.com/X6e3/sdts-fault-monitors
- **Upload:** `sh make_arxiv.sh OUT` builds `OUT/sdts-arxiv.tar.gz` (main.tex, main.bbl, fig_*.tex, figdata/*.dat);
  refs.bib is left out because the .bbl is included. TeX comments stay in the upload; the `% src:` comments name
  the dated record in the repository behind each number.
- **Before upload:** a check that arXiv's pdfLaTeX build matches `OUT/main.pdf` (built here with Tectonic).

## Abstract for the arXiv form (plain text, at most 1,920 characters)

A set-membership fault detector raises an alarm when no admissible explanation of the sensor record exists. For a linear plant with bounded noise and a bounded unknown input, the exact detector keeps a polytope whose description is not bounded in advance, so an embedded detector keeps a bounded outer approximation and detects later. We measure that loss directly. On a two-node thermal plant with one temperature sensor, a known heat input, an unknown ambient temperature and ten classes of sensor fault, a certified linear program over the full history gives the exact detection time of every run it certifies, and bounded monitors are scored against it under the same assumptions and decision rule. A template polyhedron with 42 supports needs no solver, is proved sound and never later than the interval monitor, and runs on an ESP32; on 9,600 fresh, preregistered runs it removed 38.7% of the interval monitor's paired detection lag. A window LP over 256 samples, whose base is updated by a smoothing rule and whose alarms carry weak-duality certificates, removed 99.5% of that lag on a second fresh block of 9,600 runs with no missed certified event, and all 7,258 alarms were certified. A previous freeze of the window failed its validation on a single unsolved LP; we report that failure and the sound fallback that replaced it. We show that no memory budget can certify the error of a sensor drift that an admissible ambient path reproduces. Five baselines given the same prior and tuned before the run all lagged our monitors at their memory budget; the best set-based one, a constrained zonotope storing 203 reals, had 1.8 times the interval monitor's lag.
