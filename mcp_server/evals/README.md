# Evals for the autosar-plan / autosar-generate MCP prompts

End-to-end, AI-in-the-loop evals for the server's two workflow prompts, in the
[skill-creator](https://github.com/anthropics/skills) eval format. The
deterministic per-tool tests live in [`../tests/`](../tests/) instead.

| Suite | Evals | What each eval checks |
|---|---|---|
| [`autosar-plan/`](autosar-plan/) | system SR model, ECUC Os config, modify an existing arxml | a valid plan JSON with the right request type, elements, links, ECUC definitions/values, connectivity status, and no modelling code |
| [`autosar-generate/`](autosar-generate/) | system model, ECUC without definitions, ECUC with definitions | the script passes `check_generated_script`, runs, and the arxml loads with every planned element and the exact DEFINITION-REFs; the definition arxml is left untouched |

Each suite has `evals.json` (prompts and expectations), `files/` (fixtures) and
`grade_run.py` (a programmatic grader that writes skill-creator `grading.json`).

## Running a benchmark

From the repo root:

```bash
# 1. Build the workspace: one run directory per eval x configuration, fixtures copied in,
#    and a ready-to-run task.md in each
python mcp_server/evals/setup_runs.py <workspace> --iteration 1

# 2. Run every <workspace>/<suite>/iteration-1/eval-*/*/run-1/task.md with an agent
#    (cwd = repo root), one agent per task, and record its tokens and duration in
#    timing.json next to task.md: {"total_tokens": N, "duration_ms": N, "total_duration_seconds": N}

# 3. Grade
python mcp_server/evals/grade_all.py <workspace>/autosar-plan/iteration-1
python mcp_server/evals/grade_all.py <workspace>/autosar-generate/iteration-1
```

Then aggregate and review with skill-creator's `scripts/aggregate_benchmark.py` and
`eval-viewer/generate_review.py`.

## In GitHub Actions

Two workflows check the evals:

- **Every push and PR** ([`autosarfactory_testing.yml`](../../.github/workflows/autosarfactory_testing.yml)):
  `pytest mcp_server/tests` runs the deterministic layer. This covers the tool tests, the
  `evals.json` and fixture consistency checks, and a known-good run that the graders must
  score at 100%. No credentials are needed and it costs nothing.
- **Agent evals that gate merges** ([`mcp_prompt_evals.yml`](../../.github/workflows/mcp_prompt_evals.yml)):
  a real coding agent works through every eval with the actual MCP server attached, then
  the results are graded. The job posts a results table as its summary, uploads the full
  workspace as an artifact, and fails below the pass-rate threshold.
  - **Agent:** GitHub Copilot CLI by default. Claude Code is available for manual runs.
  - **When it runs:** automatically on pull requests to `main` and in the merge queue
    (`merge_group`), and manually from the Actions tab, where you can pick the agent,
    suite, model, threshold and whether to run the baseline.
  - **When it spends credits:** only when the change touches `mcp_server/`, the library
    (`autosarfactory/autosarfactory.py`), `requirements.txt` or the workflow file. Any
    other change makes the job pass immediately. That is why it can be a required check:
    a path filter on the workflow itself would leave a required check waiting forever.
  - **Pull requests from forks** get no secrets, so they skip it. If you use a merge
    queue, the queue still runs it before merging.

### Setup

1. Create a **fine-grained personal access token** with the **"Copilot Requests"**
   permission, from an account that has a Copilot subscription. Classic `ghp_` tokens and
   the built-in Actions `GITHUB_TOKEN` are not accepted.
2. Add it as the repository secret **`COPILOT_GITHUB_TOKEN`** (Settings → Secrets and
   variables → Actions). Add `ANTHROPIC_API_KEY` only if you want manual runs with
   Claude Code.
3. Optionally add repository variables: `EVAL_MODEL` (the model for automatic runs) and
   `EVAL_MIN_PASS_RATE` (default `0.9`).
4. To block merges on the result, add **`MCP prompt evals`** as a required status check
   in your branch protection rule or ruleset for `main`.

Each eval run uses Copilot AI credits (or premium requests on the legacy plan). A full
run is 6 agent sessions with the baseline off, and pushing again to the same PR cancels
the run in progress.

The same runner works locally with either CLI:

```bash
python mcp_server/evals/run_agent_evals.py /tmp/evals --agent copilot --min-pass-rate 0.9
python mcp_server/evals/run_agent_evals.py /tmp/evals --agent claude --model sonnet
```

Cost caps: `--max-ai-credits` for Copilot, and `--max-budget-usd` for Claude (2 USD per
run by default).

## Configurations

- `with_skill`: `task.md` is the MCP prompt (`autosar-plan` / `autosar-generate`)
  rendered with the eval prompt. `run_agent_evals.py` attaches the real autosarfactory
  MCP server to the agent over stdio, so these runs exercise the actual MCP tools.
  With `--no-mcp-server`, or with `setup_runs.py --mcp-access cli` for runs you start
  yourself, the agent uses the offline CLI (`python -m autosarfactory_mcp.cli`) instead.
- `without_skill`: the baseline. It gets the same eval prompt, no workflow prompt,
  and must not use the MCP tools; it works only from the library source (it may
  read `plan_schema.md`).

The prompts are interactive (they ask for approval). Eval agents can't answer
questions, so every task ends with an "unattended run" clause and the graders
check what was produced, not the dialogue.
