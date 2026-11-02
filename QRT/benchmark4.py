"""Run the standalone solver with a 10-second limit and report local scores.

Example: python3 benchmark4.py sample4.txt --reference-length 18
Timing includes interpreter startup; judge hardware and timing may differ.
"""

import argparse
import math
from pathlib import Path
import subprocess
import sys
import time

from p4 import score_masyu, validate_masyu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--reference-length", type=int, default=None)
    parser.add_argument("--s", type=float, default=1.0)
    args = parser.parse_args()
    if args.reference_length is not None and args.reference_length <= 0:
        parser.error("--reference-length must be positive")
    if not math.isfinite(args.s) or args.s <= 0:
        parser.error("--s must be finite and positive")

    text = args.input.read_text()
    lines = text.splitlines()
    try:
        rows = int(lines[0])
        puzzle = [row.strip() for row in lines[1:]]
        if len(puzzle) != rows or not puzzle or not puzzle[0]:
            raise ValueError
        if any(len(row) != len(puzzle[0]) for row in puzzle):
            raise ValueError
        if any(ch not in ".WB" for row in puzzle for ch in row):
            raise ValueError
    except (IndexError, ValueError):
        parser.error("input must contain R followed by exactly R rectangular puzzle rows")

    start = time.perf_counter()
    try:
        process = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("p4.py"))],
            input=text, text=True, capture_output=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        print("Valid: no (10-second timeout)\nScore: 0")
        return 1
    seconds = time.perf_counter() - start
    print(f"Time: {seconds:.4f} s (includes process startup)")
    if process.returncode:
        print("Valid: no (solver exited with an error)\nScore: 0")
        print(process.stderr.strip(), file=sys.stderr)
        return 1

    answer = process.stdout.splitlines()
    valid, reason = validate_masyu(puzzle, answer)
    print(f"Valid: {valid} ({reason})")
    if not valid:
        print("Score: 0")
        return 1

    length = sum(ch != "." for row in answer for ch in row)
    speed = 0.5 + 0.5 * math.exp(-max(0, seconds - 1) / 5)
    print(f"Length: {length}\nSpeed: {speed:.6f}")
    if seconds >= 10:
        print("Score: 0 (time limit)")
        return 1
    if args.reference_length is None:
        print("Quality and score: unknown (provide --reference-length)")
    else:
        quality = min(1, args.s * args.reference_length / length) ** 2
        score = score_masyu(puzzle, answer, args.reference_length, seconds, args.s)
        print(f"Quality: {quality:.6f}\nScore: {score:.4f}")
    print("Solution:\n" + "\n".join(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
