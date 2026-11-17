"""Regression tests for process isolation and independent LP certificates."""
import json
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "oracle"))
import thermal_oracle as O


class Isolation(unittest.TestCase):
    def test_signal_is_logged_and_next_method_solves(self):
        popen = O.subprocess.Popen
        crashing_script = (
            "import os, resource, signal, sys; "
            "resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); "
            "print('before signal', flush=True); "
            "print('worker stderr', file=sys.stderr, flush=True); "
            "os.kill(os.getpid(), signal.SIGSEGV)"
        )
        with tempfile.TemporaryDirectory() as out:
            def launch(command, **kwargs):
                worker = [sys.executable, "-c", crashing_script] if launch.first else command
                launch.first = False
                return popen(worker, **kwargs)

            launch.first = True
            with patch.object(O.subprocess, "Popen", side_effect=launch):
                verdict, lower, upper = O.verdict([25.0] * 8, attempt_dir=out)
            self.assertEqual(verdict, "consistent")
            self.assertLessEqual(lower, upper)
            failed, = Path(out).glob("*-highs-ds-*")
            recovered, = Path(out).glob("*-highs-ipm-*")
            fail = json.loads((failed / "attempt.json").read_text())
            recover = json.loads((recovered / "attempt.json").read_text())
            self.assertEqual(fail["exit_code"], -signal.SIGSEGV)
            self.assertEqual(fail["signal"], "SIGSEGV")
            self.assertIsNone(fail["solver_status"])
            self.assertIn("before signal", (failed / "stdout.txt").read_text())
            self.assertIn("worker stderr", (failed / "stderr.txt").read_text())
            self.assertEqual(recover["exit_code"], 0)
            self.assertEqual(recover["solver_status"], 0)

    def test_no_solver_evidence_is_undetermined(self):
        with patch.object(O, "_attempt", return_value=None):
            self.assertEqual(O.verdict([25.0]), ("undetermined", 0.0, float("inf")))


class Certificates(unittest.TestCase):
    def test_constant_measurement_offset_enclosure(self):
        # With z=25 and a fixed ambient in [23, 27], the exact interval is ±2.3 °C.
        with tempfile.TemporaryDirectory() as out:
            inner, outer = O.offset_enclosure([25.0] * 8, attempt_dir=out)
        self.assertLessEqual(outer[0], -2.3)
        self.assertGreaterEqual(outer[1], 2.3)
        self.assertAlmostEqual(inner[0], -2.3, places=7)
        self.assertAlmostEqual(inner[1], 2.3, places=7)

    def test_two_degree_jump_has_dual_lower_bound(self):
        with tempfile.TemporaryDirectory() as out:
            verdict, lower, upper = O.verdict([25.0, 27.0], attempt_dir=out)
        self.assertEqual(verdict, "inconsistent")
        self.assertLessEqual(lower, 1.0)
        self.assertGreaterEqual(upper, 1.0)

    def test_adjacent_rate_certificate_after_both_attempts_fail(self):
        with tempfile.TemporaryDirectory() as out, patch.object(O, "_attempt", return_value=None):
            verdict, lower, upper = O.verdict([25.0, 27.0], attempt_dir=out)
            certificate, = Path(out).glob("certificate-*.json")
            self.assertEqual(json.loads(certificate.read_text())["sample"], 1)
            without_rate = O.verdict([25.0, 27.0], rate=False, attempt_dir=out)[0]
        self.assertEqual(verdict, "inconsistent")
        self.assertGreater(lower, O.T.DELTA)
        self.assertLessEqual(lower, 1.0)
        self.assertEqual(upper, 2.0)
        self.assertEqual(without_rate, "undetermined")

    def test_free_command_with_the_true_command_fixed_is_the_known_command_lp(self):
        """The (d) LP on y with P pinned to the applied command has the same optimum as the z LP."""
        from scipy.optimize import linprog
        run, m = O.T.run(410003, O.T.CELLS[0], "E1"), 300
        opt = {"method": "highs-ds", "options": {"presolve": False}}
        c, Aub, bub, Aeq, beq, bounds, _ = O._build_free_command(run["y"], m, True, True, p_bounds=run["P"])
        free = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, **opt)
        c, Aub, bub, Aeq, beq, bounds, _ = O._build(run["z"], m, True, True, "margin", 0.0)
        known = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, **opt)
        self.assertEqual((free.status, known.status), (0, 0))
        self.assertAlmostEqual(free.fun, known.fun, places=7)

    def test_free_command_is_a_relaxation_and_explains_a_healthy_run(self):
        run, m = O.T.run(410003, O.T.CELLS[0], "E1"), 600
        with tempfile.TemporaryDirectory() as out:
            v_free, lo_free, up_free = O.verdict_free_command(run["y"], m, attempt_dir=out)
            v_known, lo_known, up_known = O.verdict(run["z"], m, attempt_dir=out)
        self.assertEqual((v_free, v_known), ("consistent", "consistent"))
        self.assertLessEqual(lo_free, up_known)
        self.assertLessEqual(lo_free, up_free)

    def test_free_command_still_rejects_a_step_the_plant_can_not_make(self):
        """100 samples at 50 °C pin the state near a steady state. Tc moves at most about P_HI/CC = 1.4 °C per
        sample, so Ts can not follow a 10 °C step with any command, and the dual certificate must show it."""
        y = [50.0] * 100 + [60.0] * 20
        with tempfile.TemporaryDirectory() as out:
            verdict, lower, upper = O.verdict_free_command(y, attempt_dir=out)
        self.assertEqual(verdict, "inconsistent")
        self.assertGreater(lower, 1.5)
        self.assertLessEqual(lower, upper)

    def test_certified_prefix_pair_supersedes_an_unknown_probe(self):
        decisions = {8: "inconsistent", 4: "undetermined", 2: "consistent", 3: "inconsistent"}

        def verdict(z, m, *args, **kwargs):
            return decisions[m], 0.0, float("inf")

        with patch.object(O, "verdict", side_effect=verdict):
            self.assertEqual(O.first_inconsistent([25.0] * 8), (2, "certified"))
            decisions[3] = "undetermined"
            self.assertEqual(O.first_inconsistent([25.0] * 8), (2, "undetermined"))
