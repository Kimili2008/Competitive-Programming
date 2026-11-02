"""Experimental incremental Masyu constraint solver."""
from __future__ import annotations

from collections import deque
import math
import random
import sys
import time

from p4 import validate_masyu, score_masyu


PORTS = (0, 10, 5, 3, 9, 6, 12)
CHARS = ".-|LJF7"
# A white pearl chooses a straight orientation and one neighboring turn.
# Either choice is valid when both neighbors turn. This encodes its OR rule
# with binary constraints, so ordinary arc consistency propagates it early.
STATES = (
    tuple((p, -1) for p in PORTS),
    ((10, 1), (10, 3), (5, 0), (5, 2)),
    ((3, -1), (9, -1), (6, -1), (12, -1)),
)
FULL = (127, 15, 15)
COUNTS = tuple(x.bit_count() for x in range(128))
VALUES = tuple(tuple(i for i in range(7) if m & (1 << i)) for m in range(128))
ON = [[0] * 4 for _ in range(3)]
FORCED = [[0] * 128 for _ in range(3)]
POSSIBLE = [[0] * 128 for _ in range(3)]
REV = [[[[0] * 128 for _ in range(4)] for _ in range(3)] for _ in range(3)]
for kind, states in enumerate(STATES):
    for d in range(4):
        ON[kind][d] = sum(1 << s for s, (p, _) in enumerate(states) if p & (1 << d))
    for domain in range(1, FULL[kind] + 1):
        forced, possible = 15, 0
        for s in VALUES[domain]:
            forced &= states[s][0]
            possible |= states[s][0]
        FORCED[kind][domain] = forced
        POSSIBLE[kind][domain] = possible
for a in range(3):
    for b in range(3):
        for d in range(4):
            reverse = (d + 2) % 4
            supports = []
            for q, require_q in STATES[b]:
                compatible = 0
                for i, (p, require_p) in enumerate(STATES[a]):
                    connected = bool(p & (1 << d))
                    if connected != bool(q & (1 << reverse)):
                        continue
                    if connected and ((a == 2 and q not in (5, 10)) or
                                      (b == 2 and p not in (5, 10))):
                        continue
                    if require_p == d and q in (0, 5, 10):
                        continue
                    if require_q == reverse and p in (0, 5, 10):
                        continue
                    compatible |= 1 << i
                supports.append(compatible)
            table = REV[a][b][d]
            for domain in range(1, FULL[b] + 1):
                low = domain & -domain
                table[domain] = table[domain ^ low] | supports[low.bit_length() - 1]


class SearchTimeout(Exception):
    pass


class Engine:
    def __init__(self, puzzle, deadline, max_length=None, seed=0, mode=0, probe_budget=0.1):
        self.puzzle = puzzle
        self.rows, self.cols = len(puzzle), len(puzzle[0])
        self.n = self.rows * self.cols
        self.deadline, self.max_length = deadline, max_length
        self.kinds = [0 if ch == "." else 1 if ch == "W" else 2 for row in puzzle for ch in row]
        self.domains = [FULL[k] for k in self.kinds]
        self.reasons = [0] * self.n
        self.root_reason = [0] * self.n
        self.conflict = 0
        self.jumps = 0
        self.pearls = [i for i, k in enumerate(self.kinds) if k]
        self.pearl_total = len(self.pearls)
        self.mandatory = self.pearl_total
        self.trail = []
        self.edge_trail = []
        self.parent = list(range(self.n))
        self.sizes = [1] * self.n
        self.pearl_count = [int(k != 0) for k in self.kinds]
        self.ends = [(i, i) for i in range(self.n)]
        self.graph = [0] * self.n
        self.complete = -1
        self.adj = []
        for i in range(self.n):
            r, c = divmod(i, self.cols)
            self.adj.append((i - self.cols if r else -1,
                             i + 1 if c + 1 < self.cols else -1,
                             i + self.cols if r + 1 < self.rows else -1,
                             i - 1 if c else -1))
        self.buckets = [0] * 32
        self.slots = [0] * self.n
        for i in range(self.n):
            slot = self.bucket(i, self.domains[i])
            self.slots[i] = slot
            self.buckets[slot] |= 1 << i
        self.weight = [sum(self.kinds[j] != 0 for j in ns if j >= 0) for ns in self.adj]
        self.rng = random.Random(seed)
        self.seed = seed
        self.mode = mode
        self.probe_budget = probe_budget
        self.nodes = self.revisions = self.failures = self.max_depth = 0
        self.queue = deque()
        self.queued = set()

    def bucket(self, i, domain):
        count = (bool(domain & 3) + bool(domain & 12)) if self.kinds[i] == 1 else COUNTS[domain]
        if count <= 1:
            return 0
        frontier = any(j >= 0 and FORCED[self.kinds[j]][self.domains[j]] == POSSIBLE[self.kinds[j]][self.domains[j]]
                       and FORCED[self.kinds[j]][self.domains[j]] & (1 << ((d + 2) % 4))
                       for d, j in enumerate(self.adj[i]))
        if not frontier and not self.kinds[i]:
            return 0
        return count * 2 + (not self.kinds[i]) + (0 if frontier else 16)

    def refresh(self, i):
        new = self.bucket(i, self.domains[i])
        old = self.slots[i]
        if new != old:
            self.buckets[old] &= ~(1 << i)
            self.buckets[new] |= 1 << i
            self.slots[i] = new

    def change(self, i, new, reason=0):
        old = self.domains[i]
        if new == old:
            return True
        if not new:
            self.weight[i] += 2
            self.conflict = self.reasons[i] | reason
            return False
        self.trail.append((i, old, self.reasons[i]))
        self.reasons[i] |= reason
        if self.kinds[i] == 0 and old & 1 and not new & 1:
            self.mandatory += 1
        self.domains[i] = new
        self.refresh(i)
        for j in self.adj[i]:
            if j >= 0:
                self.refresh(j)
        if i not in self.queued:
            self.queued.add(i)
            self.queue.append(i)
        return True

    def find(self, i):
        while self.parent[i] != i:
            i = self.parent[i]
        return i

    def connect(self, i, j, d):
        if self.graph[i] & (1 << d):
            return True
        if COUNTS[self.graph[i]] == 2 or COUNTS[self.graph[j]] == 2:
            self.conflict = self.root_reason[self.find(i)] | self.root_reason[self.find(j)] | self.reasons[i]
            return False
        a, b = self.find(i), self.find(j)
        if a == b:
            if self.pearl_count[a] != self.pearl_total:
                self.conflict = self.root_reason[a] | self.reasons[i]
                return False
            self.edge_trail.append((i, j, d, -1, -1, 0, 0, (0, 0), 0))
            self.graph[i] |= 1 << d
            self.graph[j] |= 1 << ((d + 2) % 4)
            self.complete = i
            return True
        ei = self.ends[a][1] if self.ends[a][0] == i else self.ends[a][0]
        ej = self.ends[b][1] if self.ends[b][0] == j else self.ends[b][0]
        if self.sizes[a] < self.sizes[b]:
            a, b = b, a
        self.edge_trail.append((i, j, d, a, b, self.sizes[a], self.pearl_count[a], self.ends[a], self.root_reason[a]))
        self.parent[b] = a
        self.sizes[a] += self.sizes[b]
        self.pearl_count[a] += self.pearl_count[b]
        self.root_reason[a] |= self.root_reason[b] | self.reasons[i]
        self.ends[a] = (ei, ej)
        self.graph[i] |= 1 << d
        self.graph[j] |= 1 << ((d + 2) % 4)
        if self.pearl_count[a] < self.pearl_total and ej in self.adj[ei]:
            direction = self.adj[ei].index(ej)
            if not self.graph[ei] & (1 << direction) and not self.change(ei, self.domains[ei] & ~ON[self.kinds[ei]][direction], self.root_reason[a]):
                return False
        return True

    def undo(self, checkpoint):
        dm, em, complete = checkpoint
        while len(self.edge_trail) > em:
            i, j, d, a, b, size, pearls, ends, reason = self.edge_trail.pop()
            self.graph[i] &= ~(1 << d)
            self.graph[j] &= ~(1 << ((d + 2) % 4))
            if a >= 0:
                self.parent[b] = b
                self.sizes[a] = size
                self.pearl_count[a] = pearls
                self.ends[a] = ends
                self.root_reason[a] = reason
        while len(self.trail) > dm:
            i, old, reason = self.trail.pop()
            now = self.domains[i]
            if self.kinds[i] == 0 and old & 1 and not now & 1:
                self.mandatory -= 1
            self.domains[i] = old
            self.reasons[i] = reason
            self.refresh(i)
            for j in self.adj[i]:
                if j >= 0:
                    self.refresh(j)
        self.complete = complete
        self.queue.clear()
        self.queued.clear()

    def propagate(self):
        while self.queue:
            self.revisions += 1
            if self.revisions % 512 == 0 and time.monotonic() >= self.deadline:
                raise SearchTimeout
            i = self.queue.popleft()
            self.queued.remove(i)
            kind = self.kinds[i]
            forced = FORCED[kind][self.domains[i]]
            for d, j in enumerate(self.adj[i]):
                if j < 0:
                    continue
                if forced & (1 << d) and not self.connect(i, j, d):
                    return False
                new = self.domains[j] & REV[self.kinds[j]][kind][(d + 2) % 4][self.domains[i]]
                if not self.change(j, new, self.reasons[i]):
                    return False
            if self.max_length is not None and self.mandatory > self.max_length:
                self.conflict = self.all_reasons()
                return False
        return True

    def all_reasons(self):
        result = 0
        for reason in self.reasons:
            result |= reason
        return result

    def connected(self):
        # Every vertex of one simple cycle belongs to a single biconnected
        # block. Bridges and articulation points cannot join two required
        # regions of a loop. This is stronger than plain reachability.
        domains, kinds, adj = self.domains, self.kinds, self.adj
        required = [bool(k or not domains[i] & 1) for i, k in enumerate(kinds)]
        total = sum(required)
        discovery = [0] * self.n
        low = [0] * self.n
        edges = []
        clock = 0
        allowed = None

        def visit(i, parent):
            nonlocal clock, allowed
            clock += 1
            discovery[i] = low[i] = clock
            possible = POSSIBLE[kinds[i]][domains[i]]
            for d, j in enumerate(adj[i]):
                if not possible & (1 << d) or j == parent:
                    continue
                if not discovery[j]:
                    edges.append((i, j))
                    visit(j, i)
                    low[i] = min(low[i], low[j])
                    if low[j] >= discovery[i]:
                        component = set()
                        while True:
                            a, b = edges.pop()
                            component.add(a)
                            component.add(b)
                            if a == i and b == j:
                                break
                        if len(component) >= 4 and sum(required[v] for v in component) == total:
                            allowed = component
                elif discovery[j] < discovery[i]:
                    edges.append((i, j))
                    low[i] = min(low[i], discovery[j])

        visit(self.pearls[0], -1)
        if allowed is None:
            self.conflict = self.all_reasons()
            return False
        reason = self.all_reasons()
        for i in range(self.n):
            if i not in allowed and not self.change(i, domains[i] & 1 if kinds[i] == 0 else 0, reason):
                return False
        return self.propagate()

    def choose(self):
        if self.mode == 1:
            for slots in ((4, 20), (6, 22), (8, 24)):
                candidates = self.buckets[slots[0]] | self.buckets[slots[1]]
                if candidates:
                    return (candidates & -candidates).bit_length() - 1
        elif self.mode == 2:
            for slots in ((4, 5, 20), (6, 7, 22), (8, 9, 24)):
                candidates = 0
                for slot in slots:
                    candidates |= self.buckets[slot]
                if candidates:
                    return candidates.bit_length() - 1
        for bucket in range(4, 32):
            candidates = self.buckets[bucket]
            if candidates:
                return (candidates & -candidates).bit_length() - 1
        return -1

    def options(self, i):
        if self.kinds[i] == 1:
            return [self.domains[i] & mask for mask in (3, 12) if self.domains[i] & mask]
        options = [1 << s for s in VALUES[self.domains[i]]]
        options.sort(key=lambda mask: STATES[self.kinds[i]][mask.bit_length() - 1][0] not in (5, 10))
        return options

    def probe(self, until):
        # Failed-literal probing plus deductions shared by both alternatives.
        # Store only changed cells, then roll back; no whole-grid copies.
        while time.monotonic() < until:
            changed = False
            candidate_bits = 0
            for bucket in (4, 5, 6, 7, 8, 20, 22, 24):
                candidate_bits |= self.buckets[bucket]
            candidates = []
            while candidate_bits:
                low = candidate_bits & -candidate_bits
                candidates.append(low.bit_length() - 1)
                candidate_bits ^= low
            for i in candidates:
                if time.monotonic() >= until:
                    return True
                options = self.options(i)
                if not 2 <= len(options) <= 4:
                    continue
                checkpoint = len(self.trail), len(self.edge_trail), self.complete
                outcomes = []
                for mask in options:
                    if self.change(i, mask) and self.propagate():
                        touched = {entry[0] for entry in self.trail[checkpoint[0]:]}
                        outcomes.append({j: self.domains[j] for j in touched})
                    self.undo(checkpoint)
                if not outcomes:
                    return False
                common = set(outcomes[0])
                for outcome in outcomes[1:]:
                    common.intersection_update(outcome)
                for j in common:
                    merged = 0
                    for outcome in outcomes:
                        merged |= outcome[j]
                    if merged != self.domains[j]:
                        changed = True
                        if not self.change(j, self.domains[j] & merged):
                            return False
                if not self.propagate():
                    return False
                if self.complete >= 0:
                    return True
            if not changed:
                return True
        return True

    def output(self):
        root = self.find(self.complete)
        chars = [CHARS[PORTS.index(self.graph[i])] if self.find(i) == root else "."
                 for i in range(self.n)]
        return ["".join(chars[r * self.cols:(r + 1) * self.cols]) for r in range(self.rows)]

    def dfs(self, depth=0):
        self.nodes += 1
        self.max_depth = max(self.max_depth, depth)
        if self.nodes % 32 == 0 and time.monotonic() >= self.deadline:
            raise SearchTimeout
        if self.complete >= 0:
            return self.output()
        if self.nodes % 32 == 0 and not self.connected():
            self.failures += 1
            return None
        i = self.choose()
        if i < 0:
            self.conflict = self.all_reasons()
            return None
        checkpoint = len(self.trail), len(self.edge_trail), self.complete
        options = self.options(i)
        if self.seed:
            self.rng.shuffle(options)
        decision = 1 << depth
        combined = self.reasons[i]
        for mask in options:
            if self.change(i, mask, decision) and self.propagate():
                answer = self.dfs(depth + 1)
                if answer is not None:
                    return answer
            failed = self.conflict
            self.undo(checkpoint)
            if not failed & decision:
                self.jumps += 1
                return None
            combined |= failed & ~decision
        self.weight[i] += 1
        self.failures += 1
        self.conflict = combined
        return None

    def solve(self):
        for i, neighbors in enumerate(self.adj):
            domain = self.domains[i]
            for d, j in enumerate(neighbors):
                if j < 0:
                    domain &= ~ON[self.kinds[i]][d]
            if not self.change(i, domain):
                return None
            if i not in self.queued:
                self.queue.append(i)
                self.queued.add(i)
        if self.propagate() and self.probe(min(self.deadline, time.monotonic() + self.probe_budget)):
            return self.dfs()
        return None


def loop_path(answer):
    rows, cols = len(answer), len(answer[0])
    start = next((r, c) for r in range(rows) for c in range(cols) if answer[r][c] != ".")
    path, previous, current = [], None, start
    while True:
        path.append(current)
        r, c = current
        mask = PORTS[CHARS.index(answer[r][c])]
        for d, (dr, dc) in enumerate(((-1, 0), (0, 1), (1, 0), (0, -1))):
            other = (r + dr, c + dc)
            if mask & (1 << d) and other != previous:
                break
        previous, current = current, other
        if current == start:
            return path


def path_grid(path, rows, cols):
    grid = [["."] * cols for _ in range(rows)]
    bits = {(-1, 0): 1, (0, 1): 2, (1, 0): 4, (0, -1): 8}
    for i, (r, c) in enumerate(path):
        a, b = path[i - 1], path[(i + 1) % len(path)]
        mask = bits[(a[0] - r, a[1] - c)] | bits[(b[0] - r, b[1] - c)]
        grid[r][c] = CHARS[PORTS.index(mask)]
    return ["".join(row) for row in grid]


def shorten_once(puzzle, answer, deadline):
    """Remove pearl-free detours; every accepted replacement is validated."""
    rows, cols = len(puzzle), len(puzzle[0])
    path = loop_path(answer)
    n = len(path)
    index = {cell: i for i, cell in enumerate(path)}
    prefix = [0]
    for r, c in path:
        prefix.append(prefix[-1] + (puzzle[r][c] != "."))
    shortcuts = []
    for i, (r, c) in enumerate(path):
        for cell in ((r + 1, c), (r, c + 1)):
            if cell not in index:
                continue
            a, b = sorted((i, index[cell]))
            if b - a > 1 and prefix[b] == prefix[a + 1]:
                shortcuts.append((b - a - 1, a, b, False))
            if n - (b - a + 1) > 0 and prefix[-1] == prefix[b + 1] - prefix[a]:
                shortcuts.append((n - (b - a + 1), a, b, True))
    for _, a, b, keep in sorted(shortcuts, reverse=True)[:48]:
        if time.monotonic() >= deadline:
            return None
        candidate_path = path[a:b + 1] if keep else path[:a + 1] + path[b:]
        if len(candidate_path) < 4:
            continue
        candidate = path_grid(candidate_path, rows, cols)
        if validate_masyu(puzzle, candidate)[0]:
            return candidate

    # Keep two original steps next to each pearl. Changing the route between
    # these anchors preserves the pearl and its adjacent-cell geometry.
    pearls = [i for i, (r, c) in enumerate(path) if puzzle[r][c] != "."]
    gaps = [(pearls[(i + 1) % len(pearls)] + (n if i + 1 == len(pearls) else 0) - a, a)
            for i, a in enumerate(pearls)]
    for gap, pearl_index in sorted(gaps, reverse=True):
        if gap < 7 or time.monotonic() >= deadline:
            break
        a, span = (pearl_index + 2) % n, gap - 4
        rotated = path[a:] + path[:a]
        source, target = rotated[0], rotated[span]
        if abs(source[0] - target[0]) + abs(source[1] - target[1]) >= span:
            continue
        blocked = set(rotated[span + 1:])
        parent = {source: None}
        queue = deque([(source, 0)])
        while queue and target not in parent:
            if len(parent) % 64 == 0 and time.monotonic() >= deadline:
                return None
            (r, c), distance = queue.popleft()
            for other in ((r - 1, c), (r, c + 1), (r + 1, c), (r, c - 1)):
                rr, cc = other
                if (0 <= rr < rows and 0 <= cc < cols and other not in blocked
                        and other not in parent
                        and distance + 1 + abs(rr - target[0]) + abs(cc - target[1]) < span):
                    parent[other] = (r, c)
                    queue.append((other, distance + 1))
        if target in parent:
            route, current = [], target
            while current is not None:
                route.append(current)
                current = parent[current]
            candidate = path_grid(list(reversed(route)) + rotated[span + 1:], rows, cols)
            if validate_masyu(puzzle, candidate)[0]:
                return candidate
    return None


def solve_masyu(puzzle, time_limit=9.0, stats=None):
    if not puzzle or not puzzle[0] or any(len(row) != len(puzzle[0]) for row in puzzle):
        raise ValueError("puzzle must be a nonempty rectangle")
    if any(ch not in ".WB" for row in puzzle for ch in row):
        raise ValueError("invalid puzzle character")
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    start = time.monotonic()
    end = start + max(0, min(time_limit, 9.2))
    rows, cols = len(puzzle), len(puzzle[0])
    pearls = [(r, c) for r, row in enumerate(puzzle) for c, ch in enumerate(row) if ch != "."]
    if not pearls:
        return None
    top, bottom = min(r for r, c in pearls), max(r for r, c in pearls)
    left, right = min(c for r, c in pearls), max(c for r, c in pearls)
    lower_bound = max(4, 2 * (bottom - top + right - left), (len(pearls) + 1) // 2 * 2)
    boxes = []
    for margin in (0, 1, 2, 4, 8, 16, 64):
        box = (max(0, top - margin), min(rows, bottom + margin + 1),
               max(0, left - margin), min(cols, right + margin + 1))
        if box not in boxes:
            boxes.append(box)
    # Short initial attempts preserve fast cases; varied later attempts avoid
    # spending the whole budget on one unlucky branch order.
    schedule = [(0, 0, 0, 0.5)]
    schedule += [(i, 0, 0, 0.5) for i in range(1, len(boxes))]
    schedule += [(0, 1, 0, 1.2), (0, 2, 23, 1.2),
                 (len(boxes) - 1, 1, 17, 1.2), (0, 0, 41, 2.0),
                 (len(boxes) - 1, 2, 53, 9.0)]
    answer, unsat = None, set()
    totals = dict(nodes=0, revisions=0, failures=0, jumps=0, max_depth=0, attempts=0)

    def record(engine):
        totals["attempts"] += 1
        for name in ("nodes", "revisions", "failures", "jumps"):
            totals[name] += getattr(engine, name)
        totals["max_depth"] = max(totals["max_depth"], engine.max_depth)

    for box_index, mode, seed, budget in schedule:
        now = time.monotonic()
        if now >= end:
            break
        if box_index in unsat:
            continue
        r0, r1, c0, c1 = boxes[box_index]
        engine = Engine([row[c0:c1] for row in puzzle[r0:r1]], min(end, now + budget),
                        mode=mode, seed=seed, probe_budget=0.03)
        try:
            subanswer = engine.solve()
            if subanswer is None:
                unsat.add(box_index)
        except SearchTimeout:
            subanswer = None
        record(engine)
        if subanswer is not None:
            answer = ["." * cols for _ in range(rows)]
            for r, row in enumerate(subanswer, r0):
                answer[r] = "." * c0 + row + "." * (cols - c1)
            break

    if answer is not None:
        first_time = time.monotonic() - start
        length = sum(ch != "." for row in answer for ch in row)
        totals.update(first_solution_seconds=first_time, first_length=length)
        optimize_until = min(end, max(start + 0.85, time.monotonic() + 0.10))
        while length > lower_bound and time.monotonic() < optimize_until:
            before = time.monotonic()
            better = shorten_once(puzzle, answer, optimize_until)
            if better is None:
                break
            old_length = length
            answer = better
            length = sum(ch != "." for row in answer for ch in row)
            now = time.monotonic()
            # Extend only while recent shortening predicts enough quality gain
            # to compensate the next 0.15 seconds of speed penalty.
            rate = (old_length - length) / max(0.001, now - before)
            predicted = max(lower_bound, length - rate * 0.075)
            speed_now = 0.5 + 0.5 * math.exp(-max(0, now - start - 1) / 5)
            speed_later = 0.5 + 0.5 * math.exp(-max(0, now - start - 0.85) / 5)
            if speed_later / predicted ** 2 > 1.01 * speed_now / length ** 2:
                optimize_until = min(end, max(optimize_until, min(start + 2, now + 0.15)))
        # Small boards admit cheap exact tightening. Large boards use local
        # shortening so a valid solution is not delayed by another hard search.
        if rows * cols <= 144:
            while length > lower_bound and time.monotonic() < min(end, start + 0.85):
                engine = Engine(puzzle, min(end, start + 0.85), max_length=length - 2, probe_budget=0)
                try:
                    better = engine.solve()
                except SearchTimeout:
                    better = None
                record(engine)
                if better is None:
                    break
                answer = better
                length = sum(ch != "." for row in answer for ch in row)
        ok, reason = validate_masyu(puzzle, answer)
        if not ok:
            raise AssertionError(reason)
        totals["length"] = length
    totals["seconds"] = time.monotonic() - start
    if stats is not None:
        stats.update(totals)
    return answer


def main():
    n = int(sys.stdin.readline())
    puzzle = [sys.stdin.readline().strip() for _ in range(n)]
    result = solve_masyu(puzzle)
    if result is None:
        raise RuntimeError("No Masyu loop found within the search time budget")
    print("\n".join(result))


if __name__ == "__main__":
    main()
