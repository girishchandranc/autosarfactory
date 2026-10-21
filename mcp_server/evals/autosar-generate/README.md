# autosar-generate prompt evals

Evals for the `autosar-generate` MCP prompt. How to run them is in [../README.md](../README.md).

- `evals.json`: three eval prompts, one per generation mode, and their expectations.
- `files/`: pre-approved plans with `__OUTDIR__` placeholders.
  - `plan_system_sr.plan.json`: mode `system_new`.
  - `plan_ecuc_defref.plan.json`: mode `ecuc_defref_postprocess`, expects 5 DEFINITION-REFs.
  - `plan_ecuc_withdefs.plan.json` with `defs.arxml`: mode `ecuc_with_defs`, expects 3 DEFINITION-REFs and an unchanged `defs.arxml`.
- `grade_run.py`: grades one run.

  ```bash
  python mcp_server/evals/autosar-generate/grade_run.py --eval-id 2 --outputs <run>/outputs --out <run>/grading.json
  ```
