"""
Build an eval workspace for the autosar-plan / autosar-generate MCP prompts.

Usage (from the repo root):
    python mcp_server/evals/setup_runs.py <workspace> [--suite autosar-plan|autosar-generate|all]
        [--iteration 1] [--mcp-access cli|server]

For every eval and configuration it creates
    <workspace>/<suite>/iteration-N/eval-<id>-<name>/<config>/run-1/
        outputs/            fixtures copied in, __OUTDIR__ substituted
        eval_metadata.json  prompt + assertions (skill-creator viewer format)
        task.md             the complete instruction to hand to the agent under test

Configurations:
    with_skill     task = the MCP prompt (autosar-plan / autosar-generate) rendered with the
                   eval prompt, so the agent follows the workflow and calls the MCP tools.
                   --mcp-access server: the real MCP server is connected to the agent
                   (run_agent_evals.py does this); cli: the agent uses the offline CLI.
    without_skill  baseline: same eval prompt, no workflow prompt, told not to use the
                   autosarfactory MCP tools/prompts - only the library source.

Run each task.md with an agent (cwd = repo root), then grade with grade_all.py.
"""

import argparse
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
MCP_SERVER_DIR = HERE.parent
REPO_ROOT = MCP_SERVER_DIR.parent
sys.path.insert(0, str(MCP_SERVER_DIR))
from autosarfactory_mcp.cli import load_server  # noqa: E402

UNATTENDED = ("\n\nThis is an unattended eval run: interactive approval is unavailable. Wherever the "
              "workflow says to ask the user or get approval, proceed with sensible defaults, record "
              "them as assumptions, and treat scope, plan and execution as approved. Save every artifact "
              "under the outputs directory: {outdir}")

MCP_ACCESS = {
    "cli": ("\n\nThe autosarfactory MCP tools are available offline: from the repo root "
            "({repo}) run `PYTHONPATH=./mcp_server python -m autosarfactory_mcp.cli <tool> '<json kwargs>'`. "
            "Use the tools exactly as the workflow above names them."),
    "server": ("\n\nThe autosarfactory MCP server is connected to this session: call its tools "
               "directly (they are named as in the workflow above). Use the offline CLI fallback only "
               "if the server's tools are unavailable."),
}

BASELINE = ("You are executing an unattended baseline eval. Do NOT use the autosarfactory MCP tools, "
            "the autosarfactory_mcp package, its prompts or its CLI. Work only from the autosarfactory "
            "library source (autosarfactory/autosarfactory.py in {repo}).{schema}\n\nTask:\n{prompt}")


def build(workspace: pathlib.Path, suite: str, iteration: int, mcp_access: str = "cli") -> list:
    srv = load_server()
    sdir = HERE / suite
    spec = json.loads((sdir / "evals.json").read_text(encoding="utf-8"))
    render = {"autosar-plan": lambda p: srv.autosar_plan_prompt(request=p),
              "autosar-generate": lambda p: srv.autosar_generate_prompt(plan=p)}[suite]
    made = []
    for ev in spec["evals"]:
        edir = workspace / suite / f"iteration-{iteration}" / f"eval-{ev['id']}-{ev['name']}"
        meta = {"eval_id": ev["id"], "eval_name": ev["name"], "prompt": ev["prompt"],
                "assertions": ev["expectations"]}
        edir.mkdir(parents=True, exist_ok=True)
        (edir / "eval_metadata.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        for cfg in ("with_skill", "without_skill"):
            run = edir / cfg / "run-1"
            out = run / "outputs"
            out.mkdir(parents=True, exist_ok=True)
            outdir = str(out.resolve()).replace("\\", "/")
            for f in ev.get("files", []):
                src = sdir / f
                dst = out / src.name
                if src.suffix == ".json":
                    dst.write_text(src.read_text(encoding="utf-8").replace("__OUTDIR__", outdir), encoding="utf-8")
                else:
                    shutil.copy(src, dst)
            prompt = ev["prompt"].replace("__OUTDIR__", outdir)
            if cfg == "with_skill":
                task = render(prompt) + MCP_ACCESS[mcp_access].format(repo=REPO_ROOT) + UNATTENDED.format(outdir=outdir)
            else:
                schema = (" Plans use the JSON format documented in "
                          "mcp_server/autosarfactory_mcp/workflow/prompts/plan_schema.md - you may read that file.")
                task = BASELINE.format(repo=REPO_ROOT, schema=schema, prompt=prompt) + UNATTENDED.format(outdir=outdir)
            (run / "eval_metadata.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
            (run / "task.md").write_text(task, encoding="utf-8")
            made.append(str(run))
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--suite", default="all", choices=["all", "autosar-plan", "autosar-generate"])
    ap.add_argument("--iteration", type=int, default=1)
    ap.add_argument("--mcp-access", default="cli", choices=["cli", "server"])
    a = ap.parse_args()
    suites = ["autosar-plan", "autosar-generate"] if a.suite == "all" else [a.suite]
    for s in suites:
        for run in build(pathlib.Path(a.workspace), s, a.iteration, a.mcp_access):
            print(run)


if __name__ == "__main__":
    main()
