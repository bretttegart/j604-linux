"""Offline rejection checks for the physical-buffer restart discriminator."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("restart", Path(__file__).resolve().parents[2] / "scripts/run-c9-restart.py")
restart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restart)


class RelocationChecks(unittest.TestCase):
    def setUp(self):
        self.old = [(0x100040000, 32768), (0x100050000, 16384), (0x100058000, 16384)]
        self.new = [(address + 0x100000, size) for address, size in self.old]
        self.trace = {"events": [{"kind": "INIT_BEGIN"}] + [
            {"kind": "MAP", "result": 1, "a": address, "b": size, "c": address}
            for address, size in self.old]}

    def test_success_requires_actual_different_intervals(self):
        self.assertEqual(restart.buffer_ranges(self.trace), self.old)
        self.assertTrue(restart.relocation_findings(self.old, self.new)["pass"])

    def test_same_addresses_rejected(self):
        with self.assertRaises(ValueError):
            restart.relocation_findings(self.old, self.old)

    def test_changed_base_with_partial_overlap_rejected(self):
        new = copy.deepcopy(self.new)
        new[0] = (self.old[0][0] + 16384, 32768)
        with self.assertRaises(ValueError):
            restart.relocation_findings(self.old, new)

    def test_missing_or_failed_maps_rejected(self):
        with self.assertRaises(ValueError):
            restart.buffer_ranges({"events": self.trace["events"][:-1]})
        bad = copy.deepcopy(self.trace)
        bad["events"][1]["result"] = 0
        with self.assertRaises(ValueError):
            restart.buffer_ranges(bad)

    def test_only_latest_init_counts(self):
        trace = {"events": self.trace["events"] + [{"kind": "INIT_BEGIN"}] + [
            {"kind": "MAP", "result": 1, "a": address, "b": size, "c": address}
            for address, size in self.new]}
        self.assertEqual(restart.buffer_ranges(trace), self.new)

    def test_overlapping_or_nonphysical_maps_rejected(self):
        bad = copy.deepcopy(self.trace)
        bad["events"][2]["a"] = bad["events"][2]["c"] = self.old[0][0] + 16384
        with self.assertRaises(ValueError):
            restart.buffer_ranges(bad)
        bad = copy.deepcopy(self.trace)
        bad["events"][1]["c"] += 16384
        with self.assertRaises(ValueError):
            restart.buffer_ranges(bad)

    def test_partial_retention_or_wrong_buffer_rejected(self):
        holds = [{"kind": "HOLD_ARM", "result": 1}] + [
            {"kind": "HOLD", "result": 1, "a": address, "b": size} for address, size in self.old]
        self.assertEqual(restart.retained_findings({"events": holds}, self.old)["bytes"], 65536)
        with self.assertRaises(ValueError):
            restart.retained_findings({"events": holds[:-1]}, self.old)
        wrong = copy.deepcopy(holds)
        wrong[-1]["a"] += 16384
        with self.assertRaises(ValueError):
            restart.retained_findings({"events": wrong}, self.old)


if __name__ == "__main__":
    unittest.main()
