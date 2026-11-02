import math
import unittest

from p4 import score_masyu, solve_masyu, validate_masyu


SAMPLE = [
    "......",
    ".W....",
    "....B.",
    "......",
    ".B....",
    "....W.",
]


class MasyuTests(unittest.TestCase):
    def test_sample_finds_shortest_known_length(self):
        answer = solve_masyu(SAMPLE, time_limit=2)
        self.assertIsNotNone(answer)
        self.assertEqual(validate_masyu(SAMPLE, answer), (True, "valid"))
        self.assertEqual(sum(ch != "." for row in answer for ch in row), 18)
        self.assertEqual(score_masyu(SAMPLE, answer, 18, 0.5), 100.0)

    def test_rejects_missing_pearl_and_multiple_loops(self):
        puzzle = ["BW...B"] + ["......"] * 5
        loop = ["F----7"] + ["|....|"] * 4 + ["L----J"]
        self.assertTrue(validate_masyu(puzzle, loop)[0])
        missing = loop.copy()
        missing[0] = ".F---7"
        self.assertFalse(validate_masyu(puzzle, missing)[0])

        two_loops = ["F-7F-7", "|.||.|", "L-JL-J"]
        empty = ["......"] * 3
        self.assertEqual(validate_masyu(empty, two_loops), (False, "multiple loops"))

    def test_rejects_wrong_pearl_shapes(self):
        loop = ["F----7"] + ["|....|"] * 4 + ["L----J"]
        white_in_middle = ["..W..."] + ["......"] * 5
        black_on_straight = [".B...."] + ["......"] * 5
        self.assertIn("white pearl", validate_masyu(white_in_middle, loop)[1])
        self.assertIn("black pearl", validate_masyu(black_on_straight, loop)[1])

    def test_score_formula(self):
        puzzle = ["BW...B"] + ["......"] * 5
        loop = ["F----7"] + ["|....|"] * 4 + ["L----J"]
        expected = 100 * (18 / 20) ** 2 * (0.5 + 0.5 * math.exp(-1 / 5))
        self.assertAlmostEqual(score_masyu(puzzle, loop, 18, 2.0), expected)

    def test_timeout_scores_zero(self):
        puzzle = ["BW...B"] + ["......"] * 5
        loop = ["F----7"] + ["|....|"] * 4 + ["L----J"]
        self.assertGreater(score_masyu(puzzle, loop, 20, 9.99), 0)
        self.assertEqual(score_masyu(puzzle, loop, 20, 10.0), 0)
        self.assertEqual(score_masyu(puzzle, loop, 20, 12.0), 0)

    def test_interior_pearls_on_large_grid(self):
        size, a, b = 50, 15, 35
        grid = [["."] * size for _ in range(size)]
        for r, c in ((a, a), (a, b), (b, a), (b, b)):
            grid[r][c] = "B"
        grid[a][a + 1] = "W"
        puzzle = ["".join(row) for row in grid]
        answer = solve_masyu(puzzle, time_limit=2)
        self.assertIsNotNone(answer)
        self.assertTrue(validate_masyu(puzzle, answer)[0])
        self.assertEqual(sum(ch != "." for row in answer for ch in row), 80)


if __name__ == "__main__":
    unittest.main()
