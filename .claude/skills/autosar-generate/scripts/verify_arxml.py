"""
CLI for the MCP tool verify_arxml: confirm a generated arxml exists, loads, and
contains every shortName the plan creates.

Usage:
    python verify_arxml.py out.arxml [--plan plan.json]
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "autosar-plan" / "scripts"))
from af_mcp import dump, srv  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("arxml")
    ap.add_argument("--plan")
    a = ap.parse_args()
    report = srv.verify_arxml(a.arxml, a.plan)
    dump(report)
    sys.exit(0 if report["ok"] else 1)
