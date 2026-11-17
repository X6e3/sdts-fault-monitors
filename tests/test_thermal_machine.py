"""Contract checks for section 4's online interval recursion."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "machine"))
from thermal_machine import T, ThermalMachine


class Machine(unittest.TestCase):
    def test_absolute_offset_needs_a_wide_enough_radius(self):
        machine = ThermalMachine()
        machine.observe(50.0, T.P0)
        lo, hi = machine.offset_outer
        self.assertLessEqual(lo, -2.3)
        self.assertGreaterEqual(hi, 2.3)
        self.assertEqual(machine.verdict(1), "AYIRT EDİLEMEZ")
        self.assertEqual(machine.verdict(3), "TUTARLI")

    def test_inconsistent_prefix_is_absorbing(self):
        machine = ThermalMachine()
        self.assertFalse(machine.observe(50.0, T.P0))
        self.assertTrue(machine.observe(52.0, T.P0))
        self.assertTrue(machine.observe(50.0, T.P0))
        self.assertEqual(machine.verdict(3), "TUTARSIZ")
        self.assertIsNone(machine.offset_outer)

    def test_without_box_a_constant_shift_is_consistent(self):
        machine = ThermalMachine(box=False)
        for _ in range(8):
            self.assertFalse(machine.observe(150.0, T.P0))
        self.assertEqual(machine.verdict(3), "AYIRT EDİLEMEZ")

    def test_command_updates_the_state_for_the_next_measurement(self):
        run = T.run(410197, T.CELLS[0], "E1")
        machine = ThermalMachine()
        for y, command in zip(run["y"], run["P"], strict=True):
            self.assertFalse(machine.observe(y, command))
