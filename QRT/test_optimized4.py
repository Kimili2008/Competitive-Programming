"""Independent tiny-board oracle and incremental-state regression checks."""
import copy
import random
import time
import unittest

from p4 import Engine, path_grid, solve_masyu, validate_masyu


def enumerate_cycles(rows, cols):
    neighbors = []
    for i in range(rows * cols):
        r, c = divmod(i, cols)
        neighbors.append([rr * cols + cc for rr, cc in
                          ((r - 1, c), (r, c + 1), (r + 1, c), (r, c - 1))
                          if 0 <= rr < rows and 0 <= cc < cols])
    cycles = []
    for start in range(rows * cols):
        path = [start]
        used = {start}

        def visit(i):
            for j in neighbors[i]:
                if j == start and len(path) >= 4:
                    if path[1] < path[-1]:
                        cycles.append(path_grid([divmod(v, cols) for v in path], rows, cols))
                elif j > start and j not in used:
                    used.add(j)
                    path.append(j)
                    visit(j)
                    path.pop()
                    used.remove(j)
        visit(start)
    return cycles


class OptimizedTests(unittest.TestCase):
    def test_against_exhaustive_tiny_board_oracle(self):
        # Exhaustively enumerate loops, then check mixed satisfiable and
        # unsatisfiable pearl layouts. This can expose unsafe pruning.
        cycles = enumerate_cycles(3, 4)
        rng = random.Random(711)
        puzzles = []
        for _ in range(40):
            cells = ["."] * 12
            for i in rng.sample(range(12), rng.randrange(2, 8)):
                cells[i] = rng.choice("WB")
            puzzles.append(["".join(cells[r * 4:(r + 1) * 4]) for r in range(3)])
        for cycle in rng.sample(cycles, min(20, len(cycles))):
            eligible = []
            for r in range(3):
                for c in range(4):
                    for pearl in "WB":
                        grid = [["."] * 4 for _ in range(3)]
                        grid[r][c] = pearl
                        if validate_masyu(["".join(row) for row in grid], cycle)[0]:
                            eligible.append((r, c, pearl))
            if len(eligible) >= 2:
                grid = [["."] * 4 for _ in range(3)]
                for r, c, pearl in rng.sample(eligible, min(4, len(eligible))):
                    grid[r][c] = pearl
                puzzles.append(["".join(row) for row in grid])
        for puzzle in puzzles:
            with self.subTest(puzzle=puzzle):
                feasible = any(validate_masyu(puzzle, cycle)[0] for cycle in cycles)
                answer = solve_masyu(puzzle, time_limit=0.5)
                self.assertEqual(answer is not None, feasible)
                if answer is not None:
                    self.assertTrue(validate_masyu(puzzle, answer)[0])

    def test_rollback_restores_all_incremental_state(self):
        class RootOnly(Engine):
            def dfs(self, depth=0):
                return None

        puzzle = ["......", ".W....", "....B.", "......", ".B....", "....W."]
        engine = RootOnly(puzzle, time.monotonic() + 2, probe_budget=0)
        engine.solve()
        attributes = ("domains", "reasons", "root_reason", "parent", "sizes",
                      "pearl_count", "ends", "graph", "complete", "buckets", "slots", "mandatory")
        original = {key: copy.deepcopy(getattr(engine, key)) for key in attributes}
        variable = engine.choose()
        self.assertGreaterEqual(variable, 0)
        for option in engine.options(variable):
            checkpoint = len(engine.trail), len(engine.edge_trail), engine.complete
            engine.change(variable, option, 1)
            engine.propagate()
            engine.undo(checkpoint)
            for key in attributes:
                self.assertEqual(getattr(engine, key), original[key], key)

    def test_sparse_large_case_and_local_shortening(self):
        from pathlib import Path
        source = Path(__file__).parent / "masyu_stress/seed_20261027/cases/snake_06_sparse.in"
        puzzle = source.read_text().splitlines()[1:]
        stats = {}
        answer = solve_masyu(puzzle, time_limit=2, stats=stats)
        self.assertIsNotNone(answer)
        self.assertTrue(validate_masyu(puzzle, answer)[0])
        self.assertLess(stats["length"], stats["first_length"])


if __name__ == "__main__":
    unittest.main()
