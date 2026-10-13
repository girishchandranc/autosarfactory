"""
CLI for the MCP tool check_generated_script: static checks on a generated script.

Usage:
    python check_script.py script.py [--plan plan.json]

Exit code 0 when no errors.
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "autosar-plan" / "scripts"))
from af_mcp import dump, srv  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--plan")
    a = ap.parse_args()
    report = srv.check_generated_script(a.script, a.plan)
    dump(report)
    sys.exit(0 if report["ok"] else 1)
