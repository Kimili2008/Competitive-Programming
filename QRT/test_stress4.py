import unittest

from p4 import validate_masyu
from stress4 import build_suite


class StressFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = build_suite(20261027)

    def test_large_solvable_cases(self):
        self.assertEqual(len(self.cases), 26)
        self.assertEqual(len({name for name, *_ in self.cases}), 26)
        for name, puzzle, witness, _ in self.cases:
            with self.subTest(case=name):
                self.assertTrue(40 <= len(puzzle) <= 50)
                self.assertTrue(40 <= len(puzzle[0]) <= 50)
                self.assertGreaterEqual(sum(ch in "WB" for row in puzzle for ch in row), 2)
                self.assertEqual(validate_masyu(puzzle, witness), (True, "valid"))

    def test_reproducible_seed(self):
        self.assertEqual(self.cases, build_suite(20261027))

    def test_controls_match_proven_length_bound(self):
        for name, puzzle, witness, proven in self.cases:
            if not proven:
                continue
            pearls = [(r, c) for r, row in enumerate(puzzle)
                      for c, ch in enumerate(row) if ch in "WB"]
            span_r = max(r for r, _ in pearls) - min(r for r, _ in pearls)
            span_c = max(c for _, c in pearls) - min(c for _, c in pearls)
            self.assertEqual(sum(ch != "." for row in witness for ch in row),
                             2 * (span_r + span_c), name)


if __name__ == "__main__":
    unittest.main()
