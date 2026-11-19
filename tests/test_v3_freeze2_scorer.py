"""v3 freeze 2 scorer (DIAG-3 amendment 9, criterion S1): run identity, integrity and verdict precedence.
Uses the DEV rehearsal at bc2a051 (results/v3/freeze2/rehearsal-dev-430096-bc2a051) and edits copies of it. Never
generates data."""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("experiments/v3", "env"):
    sys.path.insert(0, str(ROOT / sub))
import score_validation_v2 as SV2  # noqa: E402

REH = ROOT / "results" / "v3" / "freeze2" / "rehearsal-dev-430096-bc2a051"
MANIFEST = json.loads((ROOT / "experiments" / "v3" / "frozen" / "MANIFEST-V2.json").read_text())


def load():
    meta = json.loads((REH / "meta.json").read_text())
    text = (REH / "rows.jsonl").read_text()
    return meta, [json.loads(l) for l in text.splitlines() if l.strip()], hashlib.sha256(text.encode()).hexdigest()


def verdict(meta, rows, rows_sha, manifest_sha=None):
    manifest = copy.deepcopy(MANIFEST)
    lo, hi = manifest["validation_block"] if meta.get("mode") == "validation" else meta["seeds"]
    _, exp = SV2.identity(rows, manifest, lo, hi)
    problems = SV2.integrity(meta, manifest, manifest_sha or meta["manifest_sha256"], rows_sha)
    return SV2.score(rows, manifest, expected=exp, problems=problems)


class Scorer(unittest.TestCase):
    def setUp(self):
        self.meta, self.rows, self.sha = load()
        self.old = json.loads((REH / "scores.json").read_text())

    def test_rehearsal_reproduced(self):
        s = verdict(self.meta, self.rows, self.sha)
        self.assertEqual(s["F"]["verdict"], "PASS")
        self.assertEqual(s["integrity_problems"], [])
        for k in ("D_paired", "misses", "equal_to_oracle", "evictions", "max_rows", "unproved_primal_alarms"):
            self.assertEqual(s["F"][k], self.old["F"][k], k)
        self.assertEqual(s["detection_events"], self.old["detection_events"])

    def test_missing_row(self):
        self.assertEqual(verdict(self.meta, self.rows[1:], self.sha)["F"]["verdict"], "INCONCLUSIVE")

    def test_duplicate_row(self):
        self.assertEqual(verdict(self.meta, self.rows + [self.rows[0]], self.sha)["F"]["verdict"], "INCONCLUSIVE")

    def test_extra_key(self):
        extra = dict(self.rows[0], seed=430098)
        self.assertEqual(verdict(self.meta, self.rows + [extra], self.sha)["F"]["verdict"], "INCONCLUSIVE")

    def test_rows_sha_mismatch(self):
        s = verdict(self.meta, self.rows, "0" * 64)
        self.assertEqual(s["F"]["verdict"], "INCONCLUSIVE")
        self.assertTrue(any("rows sha256" in p for p in s["integrity_problems"]))

    def test_env_mismatch(self):
        meta = copy.deepcopy(self.meta)
        meta["env"]["scipy"] = "1.17.0"
        s = verdict(meta, self.rows, self.sha)
        self.assertEqual(s["F"]["verdict"], "INCONCLUSIVE")
        self.assertTrue(any("scipy" in p for p in s["integrity_problems"]))

    def test_manifest_mismatch(self):
        self.assertEqual(verdict(self.meta, self.rows, self.sha, manifest_sha="f" * 64)["F"]["verdict"],
                         "INCONCLUSIVE")

    def test_soundness_violation_with_a_missing_row_is_a_fail(self):
        rows = copy.deepcopy(self.rows[1:])
        h = next(r for r in rows if r["cell"] == "healthy")
        h["F"]["detect"] = 1000
        h["F"]["alarm_certificate"] = {"certified": True, "certified_margin_mC": -1.0}
        s = verdict(self.meta, rows, self.sha)
        self.assertFalse(s["complete"])
        self.assertEqual(s["F"]["verdict"], "FAIL")

    def test_uncertified_alarm_is_a_fail(self):
        rows = copy.deepcopy(self.rows)
        r = next(r for r in rows if r["F"]["detect"] is not None)
        r["F"]["alarm_certificate"] = {"certified": False, "reason": "constructed"}
        self.assertEqual(verdict(self.meta, rows, self.sha)["F"]["verdict"], "FAIL")

    def test_validation_mode_needs_block_and_approval(self):
        meta = dict(self.meta, mode="validation")
        s = verdict(meta, self.rows, self.sha)
        self.assertEqual(s["F"]["verdict"], "INCONCLUSIVE")
        self.assertTrue(any("validation block" in p for p in s["integrity_problems"]))
        self.assertTrue(any("approval" in p for p in s["integrity_problems"]))


if __name__ == "__main__":
    unittest.main()
