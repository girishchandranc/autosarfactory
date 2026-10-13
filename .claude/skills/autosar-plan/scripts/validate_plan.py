"""
CLI for the MCP tool validate_plan: check a plan against the live API data.

Usage:
    python validate_plan.py plan.json            # report only
    python validate_plan.py plan.json --fix      # apply corrections in place
    python validate_plan.py plan.json --fix --out fixed.json

Exit code 0 when no errors remain, 1 otherwise.
"""

import argparse
import sys

from af_mcp import dump, srv

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    report = srv.validate_plan(a.plan, fix=a.fix, out=a.out)
    report.pop("plan", None)  # already written to disk
    dump(report)
    sys.exit(0 if report["valid"] else 1)
