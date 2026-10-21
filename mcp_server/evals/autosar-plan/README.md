# autosar-plan prompt evals

Evals for the `autosar-plan` MCP prompt. How to run them is in [../README.md](../README.md).

- `evals.json`: three eval prompts (system SR model, ECUC Os configuration, modifying an existing arxml) and their expectations.
- `files/model.arxml`: the existing model used by the modify eval (`/Interfaces/SrIf_Speed`, `/Swcs/SpeedReceiver`).
- `grade_run.py`: grades one run.

  ```bash
  python mcp_server/evals/autosar-plan/grade_run.py --eval-id 1 --outputs <run>/outputs --out <run>/grading.json
  ```
