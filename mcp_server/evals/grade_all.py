"""
Grade every run of an eval workspace iteration with the suite's programmatic grader.

Usage (from the repo root):
    python mcp_server/evals/grade_all.py <workspace>/<suite>/iteration-N

Writes grading.json next to each run's outputs/ and prints a pass-rate table per
configuration. Suite (autosar-plan / autosar-generate) is taken from the path.
"""

import collections
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def grade_iteration(it: pathlib.Path) -> tuple[list, dict]:
    """Grade all runs under one iteration dir. Returns (rows, totals{config: [passed, total]})."""
    it = it.resolve()
    suite = next((p for p in ("autosar-generate", "autosar-plan") if p in str(it)), None)
    if suite is None:
        raise ValueError(f"cannot tell the suite (autosar-plan / autosar-generate) from path {it}")
    grader = HERE / suite / "grade_run.py"
    totals = collections.defaultdict(lambda: [0, 0])
    rows = []
    for run in sorted(it.glob("eval-*/*/run-*")):
        eval_id = int(re.match(r"eval-(\d+)", run.parent.parent.name).group(1))
        cfg = run.parent.name
        (run / "grading.json").unlink(missing_ok=True)
        proc = subprocess.run([sys.executable, str(grader), "--eval-id", str(eval_id),
                               "--outputs", str(run / "outputs"), "--out", str(run / "grading.json")],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not (run / "grading.json").exists():
            print(f"grader failed for {run}:\n{proc.stderr}", file=sys.stderr)
            rows.append((run.parent.parent.name, cfg, "error", ["grader crashed"]))
            continue
        g = json.loads((run / "grading.json").read_text(encoding="utf-8"))
        s = g["summary"]
        totals[cfg][0] += s["passed"]
        totals[cfg][1] += s["total"]
        fails = [e["text"] for e in g["expectations"] if not e["passed"]]
        rows.append((run.parent.parent.name, cfg, f"{s['passed']}/{s['total']}", fails))
    return rows, dict(totals)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    try:
        rows, totals = grade_iteration(pathlib.Path(sys.argv[1]))
    except ValueError as e:
        sys.exit(str(e))
    for name, cfg, score, fails in rows:
        print(f"{name:32} {cfg:14} {score:6} " + ("; ".join(fails) if fails else "all pass"))
    for cfg, (p, t) in sorted(totals.items()):
        print(f"TOTAL {cfg:14} {p}/{t} = {p / t:.0%}" if t else f"TOTAL {cfg} no runs")


if __name__ == "__main__":
    main()
