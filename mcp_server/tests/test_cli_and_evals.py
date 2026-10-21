"""Tests for the offline CLI and the prompt-eval harness (setup_runs / graders)."""

import json
import os
import subprocess
import sys

from conftest import MCP_SERVER_DIR, REPO_ROOT

EVALS = MCP_SERVER_DIR / "evals"


def _cli(*args):
    env = {**os.environ, "PYTHONPATH": str(MCP_SERVER_DIR)}
    return subprocess.run([sys.executable, "-m", "autosarfactory_mcp.cli", *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, env=env, timeout=300)


# --- offline CLI ---------------------------------------------------------------

def test_cli_lists_all_tools_and_prompts():
    proc = _cli("list")
    assert proc.returncode == 0, proc.stderr
    listing = json.loads(proc.stdout)
    for tool in ("find_creation_chain", "validate_plan", "render_script_draft",
                 "check_generated_script", "verify_arxml", "gather_modelling_context"):
        assert tool in listing["tools"]
    assert set(listing["prompts"]) == {"autosar-plan", "autosar-generate"}


def test_cli_calls_tool_with_json_kwargs():
    proc = _cli("get_ecuc_param_literals", '{"param_path": "/AUTOSAR/EcucDefs/Os/OsTask/OsTaskSchedule"}')
    assert proc.returncode == 0, proc.stderr
    assert sorted(json.loads(proc.stdout)["literals"]) == ["FULL", "NON"]


def test_cli_renders_prompt():
    proc = _cli("prompt", "autosar-plan", '{"request": "Model a CAN network"}')
    assert proc.returncode == 0 and "Model a CAN network" in proc.stdout
    assert "autosarfactory_mcp.cli" in proc.stdout, "prompt must tell offline agents how to reach the tools"


def test_cli_unknown_tool_fails_cleanly():
    proc = _cli("no_such_tool")
    assert proc.returncode == 2 and "Unknown tool" in proc.stderr


# --- eval harness ------------------------------------------------------------------

def test_eval_specs_are_consistent():
    for suite in ("autosar-plan", "autosar-generate"):
        spec = json.loads((EVALS / suite / "evals.json").read_text(encoding="utf-8"))
        assert spec["skill_name"] == suite
        ids = [e["id"] for e in spec["evals"]]
        assert len(ids) == len(set(ids))
        for e in spec["evals"]:
            assert e["prompt"] and e["expectations"]
            for f in e.get("files", []):
                assert (EVALS / suite / f).is_file(), f"missing fixture {f}"


def test_setup_runs_builds_tasks(tmp_path):
    proc = subprocess.run([sys.executable, str(EVALS / "setup_runs.py"), str(tmp_path)],
                          capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, timeout=300)
    assert proc.returncode == 0, proc.stderr
    runs = sorted(tmp_path.glob("*/iteration-1/eval-*/*/run-1"))
    assert len(runs) == 12
    for run in runs:
        task = (run / "task.md").read_text(encoding="utf-8")
        assert "__OUTDIR__" not in task and "unattended" in task
        if run.parent.name == "with_skill":
            assert "autosarfactory_mcp.cli" in task
        else:
            assert "Do NOT use the autosarfactory MCP tools" in task
    plan = next(tmp_path.glob("autosar-generate/iteration-1/eval-2-*/with_skill/run-1/outputs/*.plan.json"))
    assert "__OUTDIR__" not in plan.read_text(encoding="utf-8")


def test_generate_grader_passes_a_correct_run(srv, tmp_path):
    """Render + run the fixture plan the way a perfect agent would; the grader must give 100%."""
    subprocess.run([sys.executable, str(EVALS / "setup_runs.py"), str(tmp_path), "--suite", "autosar-generate"],
                   check=True, capture_output=True, cwd=REPO_ROOT, timeout=300)
    for eval_id in (1, 2, 3):
        out = next(tmp_path.glob(f"autosar-generate/iteration-1/eval-{eval_id}-*/with_skill/run-1/outputs"))
        plan_path = next(out.glob("*.plan.json"))
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        srv.render_script_draft(str(plan_path), draft_path=plan["output"]["script"], summary=True)
        assert subprocess.run([sys.executable, plan["output"]["script"]], capture_output=True,
                              timeout=300).returncode == 0
        proc = subprocess.run([sys.executable, str(EVALS / "autosar-generate" / "grade_run.py"),
                               "--eval-id", str(eval_id), "--outputs", str(out)],
                              capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, timeout=300)
        grading = json.loads(proc.stdout)
        failed = [e["text"] for e in grading["expectations"] if not e["passed"]]
        assert not failed, f"eval {eval_id}: {failed}"


def test_plan_grader_rejects_empty_run(tmp_path):
    proc = subprocess.run([sys.executable, str(EVALS / "autosar-plan" / "grade_run.py"),
                           "--eval-id", "1", "--outputs", str(tmp_path)],
                          capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, timeout=300)
    grading = json.loads(proc.stdout)
    assert proc.returncode == 1 and grading["summary"]["passed"] == 0


def test_mcp_config_formats(tmp_path):
    """Each agent gets a config in its own schema that launches the real server over stdio."""
    sys.path.insert(0, str(EVALS))
    from run_agent_evals import write_mcp_config
    copilot = json.loads(write_mcp_config(tmp_path / "c.json", "copilot").read_text())["mcpServers"]["autosarfactory"]
    assert copilot["type"] == "local" and copilot["tools"] == ["*"]
    claude = json.loads(write_mcp_config(tmp_path / "a.json", "claude").read_text())["mcpServers"]["autosarfactory"]
    assert claude["type"] == "stdio"
    for cfg in (copilot, claude):
        assert cfg["args"] == ["-m", "autosarfactory_mcp.server"]
        assert str(MCP_SERVER_DIR) in cfg["env"]["PYTHONPATH"] and str(REPO_ROOT) in cfg["env"]["PYTHONPATH"]


def test_setup_runs_server_mode(tmp_path):
    proc = subprocess.run([sys.executable, str(EVALS / "setup_runs.py"), str(tmp_path),
                           "--suite", "autosar-plan", "--mcp-access", "server"],
                          capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, timeout=300)
    assert proc.returncode == 0, proc.stderr
    task = next(tmp_path.glob("autosar-plan/iteration-1/eval-1-*/with_skill/run-1/task.md")).read_text(encoding="utf-8")
    assert "MCP server is connected to this session" in task
