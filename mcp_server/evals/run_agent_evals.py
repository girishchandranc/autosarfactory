"""
Run the autosar-plan / autosar-generate prompt evals end to end with a headless coding
agent (GitHub Copilot CLI or Claude Code), grade them, and fail when the pass rate is
below a threshold. Built for CI (.github/workflows/mcp_prompt_evals.yml) but runs locally
the same way.

Usage (from the repo root):
    python mcp_server/evals/run_agent_evals.py <workspace> --agent copilot|claude \
        [--suite all|autosar-plan|autosar-generate] [--configs with_skill[,without_skill]] \
        [--model <id>] [--min-pass-rate 0.9] [--parallel 3]

Agents and their auth:
    copilot  `copilot` CLI (npm @github/copilot); COPILOT_GITHUB_TOKEN = fine-grained PAT with
             the "Copilot Requests" permission. Cost cap: --max-ai-credits.
    claude   `claude` CLI (npm @anthropic-ai/claude-code); ANTHROPIC_API_KEY.
             Cost cap: --max-budget-usd.

with_skill runs get the real autosarfactory MCP server attached over stdio, so the eval
exercises the actual MCP tools and prompts; without_skill (baseline) runs never do.

Per run it stores transcript.* (the agent's output) and timing.json next to task.md, then
grades every run. Writes <workspace>/summary.md (also appended to $GITHUB_STEP_SUMMARY when
set) and exits 1 when a graded with_skill configuration falls below --min-pass-rate, or
when an agent run fails outright.
"""

import argparse
import concurrent.futures
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
MCP_SERVER_DIR = HERE.parent
REPO_ROOT = MCP_SERVER_DIR.parent
sys.path.insert(0, str(HERE))
from grade_all import grade_iteration  # noqa: E402
from setup_runs import build  # noqa: E402

SUITES = ("autosar-plan", "autosar-generate")
SECRET_VARS = ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "ANTHROPIC_API_KEY")


def _server_env() -> dict:
    # The MCP server needs its own package and the autosarfactory library on the path.
    return {"PYTHONPATH": os.pathsep.join([str(MCP_SERVER_DIR), str(REPO_ROOT)])}


def write_mcp_config(path: pathlib.Path, agent: str) -> pathlib.Path:
    """Write the agent-specific config that attaches the autosarfactory MCP server over stdio."""
    server = {"command": sys.executable, "args": ["-m", "autosarfactory_mcp.server"], "env": _server_env()}
    if agent == "copilot":
        server = {"type": "local", **server, "tools": ["*"]}
    else:
        server = {"type": "stdio", **server}
    path.write_text(json.dumps({"mcpServers": {"autosarfactory": server}}, indent=1), encoding="utf-8")
    return path


def _usage_tokens(usage) -> int:
    """Best-effort total from a usage object: sums every numeric *tokens* field it finds."""
    total = 0
    if isinstance(usage, dict):
        for k, v in usage.items():
            if isinstance(v, (int, float)) and "token" in k.lower() and "total" not in k.lower():
                total += int(v)
            elif isinstance(v, (dict, list)):
                total += _usage_tokens(v)
    elif isinstance(usage, list):
        total += sum(_usage_tokens(x) for x in usage)
    return total


class Agent:
    name = ""
    binary = ""

    def __init__(self, args):
        self.a = args
        self.path = shutil.which(self.binary)
        if not self.path:
            sys.exit(f"the `{self.binary}` CLI is not on PATH ({self.install_hint})")

    def run(self, run: pathlib.Path, mcp_config) -> dict:
        task_file = run / "task.md"
        cmd, stdin, outfile = self.command(run, task_file, mcp_config)
        env = {**os.environ, **_server_env()}
        start = time.time()
        try:
            proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, input=stdin, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=self.a.timeout)
            out, err, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as e:
            out = e.stdout if isinstance(e.stdout, str) else ""
            err, code = f"timed out after {self.a.timeout}s", -1
        elapsed_ms = int((time.time() - start) * 1000)
        (run / outfile).write_text(out or "", encoding="utf-8")
        if err:
            (run / "stderr.txt").write_text(err[-20000:], encoding="utf-8")
        info = self.parse(run, out, elapsed_ms)
        (run / "timing.json").write_text(json.dumps({
            "total_tokens": info["tokens"], "duration_ms": info["duration_ms"],
            "total_duration_seconds": round(info["duration_ms"] / 1000, 1),
            "cost": info.get("cost"),
        }, indent=1), encoding="utf-8")
        ok = code == 0 and not info.get("is_error")
        return {"run": run, "ok": ok, "cost": info.get("cost_num", 0.0),
                "error": None if ok else (err.strip()[-500:] or info.get("error") or f"exit {code}")}


class CopilotAgent(Agent):
    name, binary = "copilot", "copilot"
    install_hint = "npm install -g @github/copilot"

    def command(self, run, task_file, mcp_config):
        # The task is long and multi-line: hand Copilot a short prompt pointing at the file
        # (argv limits on Windows; Copilot doesn't take the prompt from stdin).
        prompt = (f"Read the file {task_file.as_posix()} and carry out the instructions in it "
                  f"exactly. Work from the repository root {REPO_ROOT.as_posix()}.")
        cmd = [self.path, "-p", prompt, "--allow-all-tools", "--allow-all-paths", "--no-ask-user",
               "--no-auto-update", "--no-custom-instructions", "--disable-builtin-mcps",
               "--output-format", "json", "--log-level", "none",
               "--usage-output-file", str(run / "usage.json"),
               "--secret-env-vars", ",".join(SECRET_VARS)]
        if self.a.model:
            cmd += ["--model", self.a.model]
        if self.a.max_ai_credits:
            cmd += ["--max-ai-credits", str(self.a.max_ai_credits)]
        if mcp_config:
            cmd += ["--additional-mcp-config", f"@{mcp_config}"]
        return cmd, None, "transcript.jsonl"

    def parse(self, run, out, elapsed_ms):
        usage = {}
        try:
            usage = json.loads((run / "usage.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        credits = usage.get("aiCredits") or usage.get("ai_credits") or usage.get("premiumRequests")
        is_error = False
        for line in (out or "").splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict) and (ev.get("type") == "error" or ev.get("is_error")):
                is_error = True
        return {"tokens": _usage_tokens(usage), "duration_ms": elapsed_ms, "is_error": is_error,
                "cost": f"{credits} AI credits" if credits is not None else None,
                "cost_num": 0.0}


class ClaudeAgent(Agent):
    name, binary = "claude", "claude"
    install_hint = "npm install -g @anthropic-ai/claude-code"

    def command(self, run, task_file, mcp_config):
        # The task goes in on stdin: as an argv string it would hit Windows' 8 KB command-line
        # limit and lose everything after the first newline in npm's .cmd shim.
        cmd = [self.path, "-p", "--output-format", "json",
               "--max-budget-usd", str(self.a.max_budget_usd),
               # The CI runner is an ephemeral sandbox, so tool permission prompts are skipped.
               "--permission-mode", "bypassPermissions"]
        if self.a.model:
            cmd += ["--model", self.a.model]
        if mcp_config:
            cmd += ["--mcp-config", str(mcp_config), "--strict-mcp-config"]
        return cmd, task_file.read_text(encoding="utf-8"), "transcript.json"

    def parse(self, run, out, elapsed_ms):
        result = {}
        try:
            result = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
        except (ValueError, IndexError):
            pass
        cost = result.get("total_cost_usd")
        return {"tokens": _usage_tokens(result.get("usage") or {}),
                "duration_ms": result.get("duration_ms") or elapsed_ms,
                "is_error": result.get("is_error", False), "error": result.get("subtype"),
                "cost": f"${cost:.2f}" if isinstance(cost, (int, float)) else None,
                "cost_num": cost if isinstance(cost, (int, float)) else 0.0}


AGENTS = {"copilot": CopilotAgent, "claude": ClaudeAgent}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--agent", default="copilot", choices=sorted(AGENTS))
    ap.add_argument("--suite", default="all", choices=["all", *SUITES])
    ap.add_argument("--configs", default="with_skill",
                    help="comma list of with_skill,without_skill (baseline doubles the cost)")
    ap.add_argument("--model", default="")
    ap.add_argument("--min-pass-rate", type=float, default=0.9)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=1500, help="seconds per agent run")
    ap.add_argument("--no-mcp-server", action="store_true",
                    help="with_skill runs use the offline CLI instead of the attached MCP server")
    ap.add_argument("--max-budget-usd", type=float, default=2.0, help="claude: spend cap per run")
    ap.add_argument("--max-ai-credits", type=float, default=0, help="copilot: AI-credit cap per run (0 = none)")
    a = ap.parse_args()

    agent = AGENTS[a.agent](a)
    configs = [c.strip() for c in a.configs.split(",") if c.strip()]
    suites = list(SUITES) if a.suite == "all" else [a.suite]
    ws = pathlib.Path(a.workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    mcp_config = None if a.no_mcp_server else write_mcp_config(ws / f"mcp-config.{a.agent}.json", a.agent)
    access = "cli" if a.no_mcp_server else "server"

    runs = []
    for s in suites:
        for r in build(ws, s, iteration=1, mcp_access=access):
            r = pathlib.Path(r)
            if r.parent.name in configs:
                runs.append(r)
            else:
                shutil.rmtree(r.parent)  # configuration not requested - don't grade an empty run
    print(f"running {len(runs)} {a.agent} tasks ({', '.join(configs)}; MCP via {access}) "
          f"with parallel={a.parallel}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=a.parallel) as pool:
        futures = [pool.submit(agent.run, r, mcp_config if r.parent.name == "with_skill" else None)
                   for r in runs]
        statuses = []
        for f in concurrent.futures.as_completed(futures):
            st = f.result()
            statuses.append(st)
            rel = st["run"].relative_to(ws)
            print(f"  {'done ' if st['ok'] else 'FAIL '} {rel}" + ("" if st["ok"] else f"  ({st['error']})"), flush=True)

    cost = sum(s["cost"] for s in statuses)
    lines = ["# MCP prompt evals", "",
             f"Agent: `{a.agent}` · model: `{a.model or 'CLI default'}` · configs: {', '.join(configs)} · "
             f"MCP via {access} · threshold: {a.min_pass_rate:.0%}" + (f" · cost: ${cost:.2f}" if cost else ""), ""]
    failed = [s for s in statuses if not s["ok"]]
    below = []
    for s in suites:
        rows, totals = grade_iteration(ws / s / "iteration-1")
        lines += [f"## {s}", "", "| Eval | Config | Score | Failed checks |", "|---|---|---|---|"]
        for name, cfg, score, fails in rows:
            lines.append(f"| {name} | {cfg} | {score} | {'; '.join(fails) or '-'} |")
        lines.append("")
        for cfg, (p, t) in sorted(totals.items()):
            rate = p / t if t else 0.0
            mark = "PASS" if rate >= a.min_pass_rate else "FAIL"
            lines.append(f"- **{cfg}: {p}/{t} = {rate:.0%}** ({mark})")
            if cfg == "with_skill" and rate < a.min_pass_rate:
                below.append(f"{s}/{cfg} {rate:.0%}")
        lines.append("")
    if failed:
        lines += ["## Agent run failures", ""] + [f"- `{s['run'].relative_to(ws)}`: {s['error']}" for s in failed]

    summary = "\n".join(lines) + "\n"
    (ws / "summary.md").write_text(summary, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary)
    print(summary)

    if below or failed:
        print(f"FAILED: below threshold: {below or 'none'}; agent failures: {len(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
