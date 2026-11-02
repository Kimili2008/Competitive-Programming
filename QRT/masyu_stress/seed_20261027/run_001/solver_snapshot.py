"""Masyu validator, scorer, and dependency-free search solver.

Input on stdin: R, followed by R rows containing '.', 'W', and 'B'.
Output on stdout: R rows containing '.', '-', '|', 'L', 'J', 'F', and '7'.
"""

from __future__ import annotations

import math
import sys
import time
from collections import deque


N, E, S, W = (1 << i for i in range(4))
DR = (-1, 0, 1, 0)
DC = (0, 1, 0, -1)
CHARS = ".-|LJF7"
PORTS = (0, E | W, N | S, N | E, N | W, S | E, S | W)
BITS = tuple(1 << i for i in range(7))
ALL = (1 << 7) - 1
STRAIGHT = BITS[1] | BITS[2]
TURN = ALL & ~(BITS[0] | STRAIGHT)
CHAR_TO_TILE = {ch: i for i, ch in enumerate(CHARS)}
SUPPORT = [[0] * 7 for _ in range(4)]
for direction in range(4):
    for tile in range(7):
        for other in range(7):
            a = bool(PORTS[tile] & (1 << direction))
            b = bool(PORTS[other] & (1 << ((direction + 2) % 4)))
            if a == b:
                SUPPORT[direction][tile] |= BITS[other]


def validate_masyu(puzzle: list[str], solution: list[str]) -> tuple[bool, str]:
    """Check dimensions, all local rules, and the single-loop rule."""
    rows = len(puzzle)
    if not rows or len(solution) != rows:
        return False, "wrong number of rows"
    cols = len(puzzle[0])
    if not cols or any(len(row) != cols for row in puzzle):
        return False, "puzzle is not rectangular"
    if any(len(row) != cols for row in solution):
        return False, "wrong solution dimensions"
    if any(ch not in ".WB" for row in puzzle for ch in row):
        return False, "invalid puzzle character"
    if any(ch not in CHAR_TO_TILE for row in solution for ch in row):
        return False, "invalid solution character"

    used = []
    for r in range(rows):
        for c in range(cols):
            tile = CHAR_TO_TILE[solution[r][c]]
            mask = PORTS[tile]
            if tile:
                used.append((r, c))
            elif puzzle[r][c] != ".":
                return False, f"pearl at ({r}, {c}) is missing"
            for d in range(4):
                nr, nc = r + DR[d], c + DC[d]
                outgoing = bool(mask & (1 << d))
                if not (0 <= nr < rows and 0 <= nc < cols):
                    if outgoing:
                        return False, f"line leaves the grid at ({r}, {c})"
                else:
                    neighbor = PORTS[CHAR_TO_TILE[solution[nr][nc]]]
                    incoming = bool(neighbor & (1 << ((d + 2) % 4)))
                    if outgoing != incoming:
                        return False, f"unmatched line at ({r}, {c})"

    if not used:
        return False, "empty loop"
    for r in range(rows):
        for c in range(cols):
            pearl = puzzle[r][c]
            if pearl == ".":
                continue
            mask = PORTS[CHAR_TO_TILE[solution[r][c]]]
            adjacent = [
                CHAR_TO_TILE[solution[r + DR[d]][c + DC[d]]]
                for d in range(4)
                if mask & (1 << d)
            ]
            if pearl == "W":
                if mask not in (E | W, N | S):
                    return False, f"white pearl turns at ({r}, {c})"
                if all(t in (1, 2) for t in adjacent):
                    return False, f"white pearl has no adjacent turn at ({r}, {c})"
            elif pearl == "B":
                if mask in (E | W, N | S):
                    return False, f"black pearl is straight at ({r}, {c})"
                if any(t not in (1, 2) for t in adjacent):
                    return False, f"black pearl lacks adjacent straights at ({r}, {c})"

    stack = [used[0]]
    seen = {used[0]}
    while stack:
        r, c = stack.pop()
        mask = PORTS[CHAR_TO_TILE[solution[r][c]]]
        for d in range(4):
            if mask & (1 << d):
                nxt = (r + DR[d], c + DC[d])
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
    if len(seen) != len(used):
        return False, "multiple loops"
    return True, "valid"


def score_masyu(
    puzzle: list[str], solution: list[str], reference_length: int, seconds: float,
    s: float = 1.0,
) -> float:
    """Compute the published score when the hidden reference length is known."""
    valid, _ = validate_masyu(puzzle, solution)
    if not valid:
        return 0.0
    if (reference_length <= 0 or not math.isfinite(reference_length)
            or seconds < 0 or not math.isfinite(seconds)
            or s <= 0 or not math.isfinite(s)):
        raise ValueError("reference_length, seconds, or s is invalid")
    if seconds >= 10.0:
        return 0.0
    length = sum(ch != "." for row in solution for ch in row)
    quality = min(1.0, s * reference_length / length) ** 2
    speed = 0.5 + 0.5 * math.exp(-max(0.0, seconds - 1.0) / 5.0)
    return 100.0 * quality * speed


class SearchTimeout(Exception):
    pass


class MasyuSolver:
    def __init__(self, puzzle: list[str], deadline: float, max_length: int | None = None):
        self.puzzle = puzzle
        self.rows = len(puzzle)
        self.cols = len(puzzle[0])
        self.size = self.rows * self.cols
        self.deadline = deadline
        self.max_length = max_length
        self.pearl_ids = [
            r * self.cols + c
            for r in range(self.rows) for c in range(self.cols)
            if puzzle[r][c] != "."
        ]
        self.pearl_set = set(self.pearl_ids)
        self.neighbors = []
        self.affected = []
        for i in range(self.size):
            r, c = divmod(i, self.cols)
            ns = []
            for d in range(4):
                nr, nc = r + DR[d], c + DC[d]
                ns.append(nr * self.cols + nc if 0 <= nr < self.rows and 0 <= nc < self.cols else -1)
            self.neighbors.append(ns)
            self.affected.append([i] + [j for j in ns if j >= 0])
        self.nodes = 0

    def _pearl_options(self, i: int, domains: list[int], options: int) -> int:
        pearl = self.puzzle[i // self.cols][i % self.cols]
        if pearl == ".":
            return options
        valid = 0
        for tile in range(1, 7):
            bit = BITS[tile]
            if not options & bit:
                continue
            directions = [d for d in range(4) if PORTS[tile] & (1 << d)]
            a, b = (self.neighbors[i][d] for d in directions)
            if a < 0 or b < 0:
                continue
            if pearl == "B":
                need_a = BITS[2] if directions[0] in (0, 2) else BITS[1]
                need_b = BITS[2] if directions[1] in (0, 2) else BITS[1]
                if domains[a] & need_a and domains[b] & need_b:
                    valid |= bit
            elif pearl == "W":
                if domains[a] & TURN or domains[b] & TURN:
                    valid |= bit
        return valid

    def _propagate(self, domains: list[int], changed: list[int]) -> bool:
        queue = deque()
        queued = bytearray(self.size)
        steps = 0
        for i in changed:
            for j in self.affected[i]:
                if not queued[j]:
                    queued[j] = 1
                    queue.append(j)
        while queue:
            steps += 1
            if steps % 256 == 0 and time.monotonic() >= self.deadline:
                raise SearchTimeout
            i = queue.popleft()
            queued[i] = 0
            old = domains[i]
            new = 0
            for tile in range(7):
                bit = BITS[tile]
                if not old & bit:
                    continue
                for d, neighbor in enumerate(self.neighbors[i]):
                    if neighbor < 0:
                        if PORTS[tile] & (1 << d):
                            break
                    elif not SUPPORT[d][tile] & domains[neighbor]:
                        break
                else:
                    new |= bit
            new = self._pearl_options(i, domains, new)
            if not new:
                return False
            if new != old:
                domains[i] = new
                for j in self.affected[i]:
                    if not queued[j]:
                        queued[j] = 1
                        queue.append(j)

            # A fixed black pearl forces the two neighboring straight pieces.
            pearl = self.puzzle[i // self.cols][i % self.cols]
            if pearl == "B" and new.bit_count() == 1:
                tile = new.bit_length() - 1
                for d in range(4):
                    if PORTS[tile] & (1 << d):
                        j = self.neighbors[i][d]
                        need = BITS[2] if d in (0, 2) else BITS[1]
                        reduced = domains[j] & need
                        if not reduced:
                            return False
                        if reduced != domains[j]:
                            domains[j] = reduced
                            for k in self.affected[j]:
                                if not queued[k]:
                                    queued[k] = 1
                                    queue.append(k)

            # A fixed white pearl needs a turn on at least one side.
            if pearl == "W" and new.bit_count() == 1:
                tile = new.bit_length() - 1
                directions = [d for d in range(4) if PORTS[tile] & (1 << d)]
                a, b = (self.neighbors[i][d] for d in directions)
                for j, other in ((a, b), (b, a)):
                    if not domains[other] & TURN:
                        reduced = domains[j] & TURN
                        if not reduced:
                            return False
                        if reduced != domains[j]:
                            domains[j] = reduced
                            for k in self.affected[j]:
                                if not queued[k]:
                                    queued[k] = 1
                                    queue.append(k)
        return True

    def _closed_loop(self, domains: list[int]) -> list[str] | bool | None:
        """Return a complete answer, False for a premature loop, or None."""
        seen = set()
        for start, domain in enumerate(domains):
            if domain.bit_count() != 1 or domain == BITS[0] or start in seen:
                continue
            component = set()
            stack = [start]
            closed = True
            while stack:
                i = stack.pop()
                if i in component:
                    continue
                component.add(i)
                tile = domains[i].bit_length() - 1
                for d in range(4):
                    if PORTS[tile] & (1 << d):
                        j = self.neighbors[i][d]
                        if domains[j].bit_count() != 1:
                            closed = False
                        elif j not in component:
                            stack.append(j)
            seen.update(component)
            if closed:
                if self.pearl_set.issubset(component):
                    chars = ["."] * self.size
                    for i in component:
                        chars[i] = CHARS[domains[i].bit_length() - 1]
                    return ["".join(chars[r * self.cols:(r + 1) * self.cols]) for r in range(self.rows)]
                return False
        return None

    def _choose(self, domains: list[int]) -> int:
        best = -1
        best_key = (10, 10, 10)
        for i, domain in enumerate(domains):
            count = domain.bit_count()
            if count <= 1:
                continue
            forced_neighbor = any(
                domains[j].bit_count() == 1 and domains[j] != BITS[0]
                and bool(PORTS[domains[j].bit_length() - 1] & (1 << ((d + 2) % 4)))
                for d, j in enumerate(self.neighbors[i]) if j >= 0
            )
            if not forced_neighbor and i not in self.pearl_set:
                continue
            key = (0 if forced_neighbor else 1, count, 0 if i in self.pearl_set else 1)
            if key < best_key:
                best_key, best = key, i
        return best

    def _search(self, domains: list[int]) -> list[str] | None:
        self.nodes += 1
        if self.nodes % 64 == 0 and time.monotonic() >= self.deadline:
            raise SearchTimeout
        if self.max_length is not None:
            forced_length = sum(
                domain.bit_count() == 1 and domain != BITS[0]
                for domain in domains
            )
            if forced_length > self.max_length:
                return None
        cycle = self._closed_loop(domains)
        if cycle is False:
            return None
        if cycle is not None:
            return cycle
        i = self._choose(domains)
        if i < 0:
            return None
        options = [t for t in range(7) if domains[i] & BITS[t]]
        # Search a connected continuation first; empty cells are tried last.
        options.sort(key=lambda t: (t == 0, t not in (1, 2)))
        for tile in options:
            trial = domains.copy()
            trial[i] = BITS[tile]
            if self._propagate(trial, [i]):
                answer = self._search(trial)
                if answer is not None:
                    return answer
        return None

    def solve(self) -> list[str] | None:
        domains = [ALL] * self.size
        for i in range(self.size):
            pearl = self.puzzle[i // self.cols][i % self.cols]
            if pearl == "W":
                domains[i] = STRAIGHT
            elif pearl == "B":
                domains[i] = TURN
        if not self._propagate(domains, list(range(self.size))):
            return None
        return self._search(domains)


def solve_masyu(puzzle: list[str], time_limit: float = 9.0) -> list[str] | None:
    """Find one loop; return None if this bounded search does not find one."""
    if not puzzle or not puzzle[0] or any(len(row) != len(puzzle[0]) for row in puzzle):
        raise ValueError("puzzle must be a nonempty rectangle")
    start_time = time.monotonic()
    rows, cols = len(puzzle), len(puzzle[0])
    pearls = [(r, c) for r in range(rows) for c in range(cols) if puzzle[r][c] != "."]
    if not pearls:
        return None
    top = min(r for r, _ in pearls)
    bottom = max(r for r, _ in pearls)
    left = min(c for _, c in pearls)
    right = max(c for _, c in pearls)

    # Search small boxes first. A tight box both favors shorter loops and
    # avoids spending time assigning irrelevant cells far from all pearls.
    boxes = []
    for margin in (0, 1, 2, 4, 8, 16, 32, 64):
        box = (
            max(0, top - margin), min(rows, bottom + margin + 1),
            max(0, left - margin), min(cols, right + margin + 1),
        )
        if box not in boxes:
            boxes.append(box)
        if box == (0, rows, 0, cols):
            break

    overall_deadline = start_time + time_limit
    for index, (r0, r1, c0, c1) in enumerate(boxes):
        remaining = overall_deadline - time.monotonic()
        if remaining <= 0:
            break
        attempt_deadline = time.monotonic() + remaining / (len(boxes) - index)
        subpuzzle = [row[c0:c1] for row in puzzle[r0:r1]]
        solver = MasyuSolver(subpuzzle, attempt_deadline)
        try:
            result = solver.solve()
        except SearchTimeout:
            continue
        if result is None:
            continue
        full = ["." * cols for _ in range(rows)]
        for r, row in enumerate(result, r0):
            full[r] = "." * c0 + row + "." * (cols - c1)
        valid, reason = validate_masyu(puzzle, full)
        if not valid:
            raise AssertionError(f"internal solver error: {reason}")
        best = full
        best_length = sum(ch != "." for row in best for ch in row)
        # The first second has no speed penalty. Use its remainder to improve
        # the loop, while keeping the first valid result as a fallback.
        improve_deadline = min(overall_deadline, start_time + 0.95)
        while time.monotonic() < improve_deadline and best_length > len(pearls):
            improver = MasyuSolver(subpuzzle, improve_deadline, best_length - 1)
            try:
                better = improver.solve()
            except SearchTimeout:
                break
            if better is None:
                break
            for r, row in enumerate(better, r0):
                best[r] = "." * c0 + row + "." * (cols - c1)
            best_length = sum(ch != "." for row in best for ch in row)
        return best
    return None


def main() -> None:
    sys.setrecursionlimit(10000)
    rows = int(sys.stdin.readline())
    puzzle = [sys.stdin.readline().strip() for _ in range(rows)]
    result = solve_masyu(puzzle)
    if result is None:
        # The contest requires a valid grid; this signals that the search did
        # not find one within its time budget, rather than printing a fake loop.
        raise RuntimeError("No Masyu loop found within the search time budget")
    sys.stdout.write("\n".join(result) + "\n")


if __name__ == "__main__":
    main()
