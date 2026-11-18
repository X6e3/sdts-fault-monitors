"""v3 freeze 1: the validation lock, frozen tables, Theorem-3 bases after pruning, and the scoring rules.
Never generates validation data (440000-440999): the lock test only checks that generation is refused."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for sub in ("experiments/v3", "experiments/machine", "experiments/generators", "experiments/oracle", "env"):
    sys.path.insert(0, str(ROOT / sub))
import dev_scenarios as S  # noqa: E402
import score_validation as SV  # noqa: E402
import template_state as V  # noqa: E402

T = V.T
MANIFEST = ROOT / "experiments" / "v3" / "frozen" / "MANIFEST.json"


class ValidationLock(unittest.TestCase):
    def test_validation_seeds_are_refused_without_unlock(self):
        self.assertFalse(S._VALIDATION_UNLOCKED)
        for seed in (440000, 440099, 440999):
            with self.assertRaises(ValueError):
                S.ambient(seed, "rw")
            with self.assertRaises(ValueError):
                S.onset(seed)

    def test_other_ranges_are_refused_always(self):
        for seed in (400000, 410000, 420000, 429999, 431000, 441000):
            with self.assertRaises(ValueError):
                S.noise(seed, "uniform")

    def test_approval_line_is_exact(self):
        import run_validation as RV
        self.assertIsNone(RV.APPROVAL.search("Status: PROPOSED (not approved)"))
        self.assertIsNone(RV.APPROVAL.search("Status: APPROVED"))
        self.assertIsNotNone(RV.APPROVAL.search("x\nStatus: APPROVED by Can Koç on 2026-11-19\ny"))


class FrozenTables(unittest.TestCase):
    def test_roundtrip_is_bit_exact_and_hash_checked(self):
        tp = V.Template(V.directions("box+diff"), invariant=True)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.json")
            V.write_frozen(tp, {"name": "t"}, p)
            sha = hashlib.sha256(Path(p).read_bytes()).hexdigest()
            t2 = V.load_frozen(p, sha)
            with self.assertRaises(ValueError):
                V.load_frozen(p, "0" * 64)
        for a, b in zip(tp.pred + tp.supp_as, t2.pred + t2.supp_as):
            for x, y in zip(a, b):
                self.assertTrue(np.array_equal(x, y))
        for name in ("D", "cap_inv", "rho_pad", "h0"):
            self.assertTrue(np.array_equal(getattr(tp, name), getattr(t2, name)))
        r = S.run(430090, next(c for c in T.CELLS if c.name == "drift_0.005"), "E1", "ramp")
        self.assertEqual(V.first_inconsistent(tp, r["y"], r["P"]), V.first_inconsistent(t2, r["y"], r["P"]))

    def test_pruning_with_no_usage_keeps_the_theorem3_bases(self):
        tp = V.Template(V.directions("inv", N=4), invariant=True)
        zero = [np.zeros(len(g[0]), dtype=int) for g in tp.pred + tp.supp_as]
        self.assertEqual(V.dominance_bases_present(V.pruned(tp, zero)), [])

    def test_manifest_files_match_when_frozen(self):
        if not MANIFEST.exists():
            self.skipTest("no manifest yet")
        m = json.loads(MANIFEST.read_text())
        for rel, h in m["files"].items():
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), h, rel)
        for name, c in m["candidates"].items():
            tp = V.load_frozen(ROOT / c["file"], c["sha256"])
            self.assertEqual(V.dominance_bases_present(tp), [], name)


def row(seed, cell, t_star, v2, cand, status="certified", noise="uniform", ambient="rw"):
    return {"seed": seed, "cell": cell, "arm": "E0", "ambient": ambient, "noise": noise, "t_f": 300,
            "oracle": {"t_star": t_star, "status": status}, "v2": v2, "candidates": {"x": cand}}


MAN = {"candidates": {"x": {"target_paired_lag_reduction": 0.10}}}


class Scoring(unittest.TestCase):
    def test_paired_and_censored_lag(self):
        rows = [row(1, "drift_0.001", 1000, 1100, 1050), row(2, "drift_0.001", 1000, 1200, 1100),
                row(3, "drift_0.001", 3000, None, 3100), row(4, "healthy", None, None, None)]
        s = SV.score(rows, MAN)
        c = s["candidates"]["x"]
        self.assertEqual((c["L_paired"], c["L_paired_v2"], c["paired_set"]), (150, 300, 2))
        self.assertAlmostEqual(c["D_paired"], 0.5)
        self.assertEqual((c["L_censored"], c["L_censored_v2"]), (250, 300 + 600))   # v2 miss: N - t* = 600
        self.assertEqual(c["verdict"], "PASS")

    def test_fail_on_soundness_dominance_misses_and_target(self):
        base = [row(1, "drift_0.001", 1000, 1100, 1000)]
        self.assertEqual(SV.score(base + [row(2, "healthy", None, None, 5)], MAN)["candidates"]["x"]["verdict"], "FAIL")
        self.assertEqual(SV.score(base + [row(2, "jump_0.2", None, None, 7)], MAN)["candidates"]["x"]["verdict"], "FAIL")
        self.assertEqual(SV.score(base + [row(2, "jump_0.5", 500, 500, 499)], MAN)["candidates"]["x"]["verdict"], "FAIL")
        self.assertEqual(SV.score(base + [row(2, "jump_0.5", 500, 510, 520)], MAN)["candidates"]["x"]["verdict"], "FAIL")
        self.assertEqual(SV.score(base + [row(2, "jump_0.5", 500, None, None), row(3, "jump_0.5", 500, 600, None)],
                                  MAN)["candidates"]["x"]["verdict"], "FAIL")
        slow = [row(1, "drift_0.001", 1000, 1100, 1095)]
        self.assertEqual(SV.score(slow, MAN)["candidates"]["x"]["verdict"], "FAIL")      # D = 0.05 < 0.10

    def test_healthy_edge_noise_counts_as_admissible(self):
        rows = [row(1, "drift_0.001", 1000, 1100, 1000), row(1, "healthy", None, None, 9, noise="edge", status="x")]
        c = SV.score(rows, MAN)["candidates"]["x"]
        self.assertEqual(len(c["soundness_violations"]), 1)

    def test_inconclusive_when_too_many_uncertified_or_incomplete(self):
        rows = [row(i, "drift_0.001", 1000, 1100, 1000) for i in range(99)] + \
               [row(99, "drift_0.001", 1000, 1100, 1000, status="undetermined"),
                row(100, "drift_0.001", 1000, 1100, 1000, status="undetermined")]
        self.assertEqual(SV.score(rows, MAN)["candidates"]["x"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(SV.score(rows[:99], MAN, expected_runs=100)["candidates"]["x"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(SV.score(rows[:100], MAN)["candidates"]["x"]["verdict"], "PASS")      # 1 of 100: allowed


if __name__ == "__main__":
    unittest.main()
