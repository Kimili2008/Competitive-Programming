"""Generate large, solvable Masyu cases and preserve every solver input/output.

Run: python3 stress4.py
Generate only: python3 stress4.py --generate-only
Repeat one case: python3 stress4.py --case random_01_sparse
The known solution is a witness, not a proven shortest solution.
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

from p4 import score_masyu, validate_masyu


ROOT = Path(__file__).resolve().parent
PORT_CHAR = {
    frozenset(((-1, 0), (1, 0))): "|",
    frozenset(((0, -1), (0, 1))): "-",
    frozenset(((-1, 0), (0, 1))): "L",
    frozenset(((-1, 0), (0, -1))): "J",
    frozenset(((1, 0), (0, 1))): "F",
    frozenset(((1, 0), (0, -1))): "7",
}


def rectangle(height, width):
    return ([(0, c) for c in range(width)]
            + [(r, width - 1) for r in range(1, height)]
            + [(height - 1, c) for c in range(width - 2, -1, -1)]
            + [(r, 0) for r in range(height - 2, 0, -1)])


def random_cycle(height, width, rng):
    """Replace an edge by a three-edge detour through two unused cells.

    Every operation preserves one simple cycle. Occasionally remove a
    three-edge detour to let subsequent growth take a different direction.
    """
    path = rectangle(height, width)
    occupied = set(path)
    target = int(height * width * 0.76)
    for _ in range(height * width * 100):
        if len(path) >= target:
            break
        i = rng.randrange(len(path))
        a, b = path[i], path[(i + 1) % len(path)]
        if rng.random() < 0.06 and i + 3 < len(path):
            end = path[i + 3]
            if abs(a[0] - end[0]) + abs(a[1] - end[1]) == 1:
                occupied.difference_update(path[i + 1:i + 3])
                del path[i + 1:i + 3]
                continue
        dr, dc = b[0] - a[0], b[1] - a[1]
        sign = rng.choice((-1, 1))
        shift = (-dc * sign, dr * sign)
        u = (a[0] + shift[0], a[1] + shift[1])
        v = (b[0] + shift[0], b[1] + shift[1])
        if all(0 <= r < height and 0 <= c < width and (r, c) not in occupied
               for r, c in (u, v)):
            path[i + 1:i + 1] = [u, v]
            occupied.update((u, v))
    return path


def snake_cycle(height, width):
    """Hamiltonian cycle on an even-height coarse rectangle."""
    assert height % 2 == 0
    path = [(0, c) for c in range(width)]
    for r in range(1, height):
        columns = range(width - 1, 0, -1) if r % 2 else range(1, width)
        path.extend((r, c) for c in columns)
    path.extend((r, 0) for r in range(height - 1, 0, -1))
    return path


def expand(path, scale, rows, cols, rng):
    max_r = max(r for r, _ in path) * scale
    max_c = max(c for _, c in path) * scale
    r0 = rng.randrange(rows - max_r)
    c0 = rng.randrange(cols - max_c)
    result = []
    for i, (r, c) in enumerate(path):
        nr, nc = path[(i + 1) % len(path)]
        dr, dc = nr - r, nc - c
        for step in range(scale):
            result.append((r0 + r * scale + dr * step, c0 + c * scale + dc * step))
    if rng.randrange(2):
        result = [(rows - 1 - r, c) for r, c in result]
    if rng.randrange(2):
        result = [(r, cols - 1 - c) for r, c in result]
    return result


def witness_and_candidates(path, rows, cols):
    # These structural checks are independent of the solver's validator.
    assert len(path) >= 4 and len(path) == len(set(path))
    turns = []
    witness = [["."] * cols for _ in range(rows)]
    for i, (r, c) in enumerate(path):
        assert 0 <= r < rows and 0 <= c < cols
        previous, following = path[i - 1], path[(i + 1) % len(path)]
        ports = frozenset((rr - r, cc - c) for rr, cc in (previous, following))
        assert len(ports) == 2 and all(abs(dr) + abs(dc) == 1 for dr, dc in ports)
        char = PORT_CHAR[ports]
        witness[r][c] = char
        turns.append(char not in "-|")
    candidates = []
    for i, (r, c) in enumerate(path):
        before, after = turns[i - 1], turns[(i + 1) % len(path)]
        if turns[i] and not before and not after:
            candidates.append((r, c, "B"))
        elif not turns[i] and (before or after):
            candidates.append((r, c, "W"))
    return ["".join(row) for row in witness], candidates


def build_suite(seed):
    specs = [
        ("random_01", 50, 50, 2, 101),
        ("random_02", 50, 50, 2, 202),
        ("random_03", 50, 50, 3, 303),
        ("random_04", 48, 50, 2, 404),
        ("tight_05", 50, 50, 1, 505),
        ("snake_06", 50, 40, 2, 606),
    ]
    cases = []
    for family, rows, cols, scale, offset in specs:
        rng = random.Random(seed + offset)
        h, w = (rows - 1) // scale + 1, (cols - 1) // scale + 1
        if family.startswith("snake"):
            h -= h % 2
            coarse = snake_cycle(h, w)
        else:
            coarse = random_cycle(h, w, rng)
        path = expand(coarse, scale, rows, cols, rng)
        witness, candidates = witness_and_candidates(path, rows, cols)
        assert len(candidates) >= 8
        rng.shuffle(candidates)
        for label, fraction in (("sparse", 0.08), ("medium", 0.30),
                                ("dense", 0.70), ("full", 1.0)):
            grid = [["."] * cols for _ in range(rows)]
            for r, c, color in candidates[:max(8, int(len(candidates) * fraction))]:
                grid[r][c] = color
            puzzle = ["".join(row) for row in grid]
            valid, reason = validate_masyu(puzzle, witness)
            assert valid, reason
            cases.append((f"{family}_{label}", puzzle, witness, False))

    # Two large controls with a proven minimum: any cycle visiting the four
    # rectangle corners needs at least 2 * (height span + width span) edges.
    for name, rows, cols, top, left, height, width in (
        ("control_boundary", 50, 50, 0, 0, 50, 50),
        ("control_interior", 50, 50, 10, 7, 30, 36),
    ):
        path = [(r + top, c + left) for r, c in rectangle(height, width)]
        witness, _ = witness_and_candidates(path, rows, cols)
        grid = [["."] * cols for _ in range(rows)]
        for r, c in ((top, left), (top + height - 1, left),
                     (top, left + width - 1), (top + height - 1, left + width - 1)):
            grid[r][c] = "B"
        grid[top][left + 1] = "W"
        puzzle = ["".join(row) for row in grid]
        assert validate_masyu(puzzle, witness)[0]
        cases.append((name, puzzle, witness, True))
    return cases


def generate(case_dir, seed):
    cases = build_suite(seed)
    case_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, puzzle, witness, proven in cases:
        text = str(len(puzzle)) + "\n" + "\n".join(puzzle) + "\n"
        solution_text = "\n".join(witness) + "\n"
        # Do not silently overwrite manually edited fixtures.
        for path, content in ((case_dir / f"{name}.in", text),
                              (case_dir / f"{name}.witness.out", solution_text)):
            if path.exists() and path.read_text() != content:
                raise ValueError(f"Existing fixture differs: {path}; use a new --root")
            path.write_text(content)
        manifest.append({
            "name": name, "rows": len(puzzle), "cols": len(puzzle[0]),
            "white": sum(row.count("W") for row in puzzle),
            "black": sum(row.count("B") for row in puzzle),
            "witness_length": sum(ch != "." for row in witness for ch in row),
            "reference_proven_optimal": proven,
            "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
        })
    (case_dir / "manifest.json").write_text(json.dumps({"seed": seed, "cases": manifest}, indent=2) + "\n")
    return manifest


def run_case(solver, input_text, puzzle):
    start = time.perf_counter()
    try:
        process = subprocess.run([sys.executable, str(solver)], input=input_text,
                                 text=True, capture_output=True, timeout=10, cwd=solver.parent)
        elapsed = time.perf_counter() - start
        output, stderr, code = process.stdout, process.stderr, process.returncode
        valid, reason = validate_masyu(puzzle, output.splitlines())
        if code:
            status = "no_solution" if "No Masyu loop found" in stderr else "error"
        elif elapsed >= 10:
            status = "timeout"
        else:
            status = "valid" if valid else "invalid"
        return status, elapsed, output, stderr, code, reason
    except subprocess.TimeoutExpired as error:
        def decode(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
        return ("timeout", time.perf_counter() - start, decode(error.stdout),
                decode(error.stderr), None, "hard 10-second limit")


def run_suite(case_dir, run_dir, solver, cases, quiet):
    run_dir.mkdir(parents=True, exist_ok=False)
    source = solver.read_bytes()
    (run_dir / "solver_snapshot.py").write_bytes(source)
    (run_dir / "run.json").write_text(json.dumps({
        "solver": str(solver), "solver_sha256": hashlib.sha256(source).hexdigest(),
        "python": sys.version, "hard_timeout_seconds": 10,
        "timing": "sequential processes; elapsed wall time includes startup",
        "selected_cases": [case["name"] for case in cases],
    }, indent=2) + "\n")
    results = []
    report_path = run_dir / "all_inputs_outputs.md"
    with report_path.open("w") as report:
        report.write("# Masyu stress run\n\nEvery input, actual stdout, stderr and known valid witness is preserved below.\n\n"
                     "Witness solutions are not proven shortest except for the two controls. "
                     "Witness-relative scores are optimistic comparison metrics, not official scores. "
                     "Empty actual output means the solver produced no answer; the witness is never substituted.\n")
        for number, case in enumerate(cases, 1):
            name = case["name"]
            text = (case_dir / f"{name}.in").read_text()
            witness = (case_dir / f"{name}.witness.out").read_text()
            puzzle = text.splitlines()[1:]
            print(f"[{number}/{len(cases)}] {name}: running...", flush=True)
            status, seconds, output, stderr, code, reason = run_case(solver, text, puzzle)
            for suffix, content in (("in", text), ("out", output),
                                    ("stderr.txt", stderr), ("witness.out", witness)):
                (run_dir / f"{name}.{suffix}").write_text(content)
            length = sum(ch != "." for row in output.splitlines() for ch in row) if status == "valid" else None
            proxy = score_masyu(puzzle, output.splitlines(), case["witness_length"], seconds) if status == "valid" else 0.0
            result = dict(case, status=status, seconds=round(seconds, 6), length=length,
                          witness_relative_score=round(proxy, 6), return_code=code,
                          validation=reason)
            results.append(result)
            (run_dir / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            summary = f"{status}; {seconds:.3f}s; length={length}; witness_length={case['witness_length']}"
            print(f"[{number}/{len(cases)}] {name}: {summary}", flush=True)
            section = (f"\n## {name}\n\n{summary}\n\n"
                       f"### Input\n\n```text\n{text}```\n\n"
                       f"### Actual output\n\n```text\n{output}```\n")
            if not output:
                section += "\nActual stdout is empty.\n"
            if stderr:
                section += f"\n### Stderr\n\n```text\n{stderr}```\n"
            section += f"\n### Known valid witness (not solver output)\n\n```text\n{witness}```\n"
            report.write(section)
            report.flush()
            if not quiet:
                print(section, flush=True)

    fields = list(results[0])
    with (run_dir / "results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    counts = Counter(row["status"] for row in results)
    summary = ["# Stress test results", "", f"Status counts: {dict(counts)}", "",
               "Hard generated cases have no proven shortest reference. Proxy scores use the stored witness length.", "",
               "| Case | Size | Pearls | Status | Seconds | Length | Witness |",
               "|---|---|---:|---|---:|---:|---:|"]
    for r in results:
        summary.append(f"| [{r['name']}]({r['name']}.in) | {r['rows']}x{r['cols']} | "
                       f"{r['white'] + r['black']} | {r['status']} | {r['seconds']:.3f} | "
                       f"{r['length'] if r['length'] is not None else '-'} | {r['witness_length']} |")
    summary.append("\n[Full inputs, actual outputs and witnesses](all_inputs_outputs.md)\n")
    (run_dir / "summary.md").write_text("\n".join(summary))
    print(f"\nStatus counts: {dict(counts)}\nFull input/output report: {report_path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--root", type=Path, default=ROOT / "masyu_stress")
    parser.add_argument("--solver", type=Path, default=ROOT / "p4.py")
    parser.add_argument("--case", action="append", dest="names")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Console summaries only; full I/O is always saved")
    args = parser.parse_args()
    base = args.root.resolve() / f"seed_{args.seed}"
    case_dir = base / "cases"
    cases = generate(case_dir, args.seed)
    print(f"Generated and validated {len(cases)} solvable cases: {case_dir}", flush=True)
    if args.generate_only:
        return
    if args.names:
        unknown = set(args.names) - {case["name"] for case in cases}
        if unknown:
            parser.error(f"unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case["name"] in args.names]
    index = 1
    while (base / f"run_{index:03d}").exists():
        index += 1
    run_suite(case_dir, base / f"run_{index:03d}", args.solver.resolve(), cases, args.quiet)


if __name__ == "__main__":
    main()
