"""
CLI for the MCP tool render_script_draft: enrich a plan with exact API data and
render the deterministic draft script.

Usage:
    python enrich_plan.py plan.json [--draft out.py] [--summary]
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "autosar-plan" / "scripts"))
from af_mcp import dump, srv  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--draft", default="")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    dump(srv.render_script_draft(a.plan, draft_path=a.draft, summary=a.summary))
