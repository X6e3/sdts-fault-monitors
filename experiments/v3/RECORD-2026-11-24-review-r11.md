# Review r11: public-readiness audit of the repository (2026-11-24)

Package `public-716fbd28` (full-history clone of the pushed branch, 253 commits, the archive's zip files and nested
bundle included), read-only. Seven findings. The reviewer's fresh-clone checks passed: environment lock,
`experiments/j713/reproduce_step3.py` (reproduced), 66 of 66 unit tests, `widebox_vertices.py`, `s_gap_witness.py`
(byte for byte), `independent_score.py --freeze 3`, and REPRODUCE.md section 1 (`scores.json` byte for byte). No
secrets, no unreleased J713 sensor values, OBD record limited to ECT, rpm and speed.

The history is not rewritten: the paper cites approval commits by hash and the bundle of c87301bc is time-stamped.

| # | finding | class | outcome |
|---|---|---|---|
| 1 | Root commit c2babba2 has the author's personal e-mail address | history | Left; the author decides before the repository is made public. |
| 2 | Elsevier template files (LPPL) not excepted in README and NOTICE | tip | Fixed: both name the files and their licence. |
| 3 | A private-network address and ssh user in `results/v3/fb/hfb-459e6813/v3-fb-459e6813-mac.sh` (not pinned by a hash; a record names the file) | tip | Fixed: the host is now `$ARCH_HOST`, with a comment saying it was replaced before publication. The deleted HANDOFF.md keeps another such address in the history. |
| 4 | Tool names left at the tip | tip | Fixed where nothing pins the file: `check_evidence.py` (variable `sol` renamed `ref`), the run folder in DIAG-1-PLAN.md. Left by design where a recorded sha256, a DONE.txt, an OpenTimestamps proof or the archive's SHA256SUMS pins the file (diag1_review.py, results/v3/diag1/codex-T2*, results/v3/diag3/indep-*, results/v3/mcu/N1-430010, the archive), and in folder names that records cite. |
| 5 | Informal approval quotes, tool names and HANDOFF.md in the history | history | Left (no secret, no private life). |
| 6 | A Turkish quote in `results/v3/iso/iso-35f479c5-arch/run.sh`; two quotes in the stamped J713 addenda | tip | run.sh: replaced by an English note. The addenda are covered by OpenTimestamps proofs and stay unchanged. |
| 7 | experiments/j713/README.md lacked the pilot files; README's figure numbers are the preprint's | tip | Fixed: a pilot row; "Figure N of the preprint". |
