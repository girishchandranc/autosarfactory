---
name: autosar-generate
description: AUTOSAR Code Generator. Takes an approved /autosar-plan plan (JSON file path or the plan from the conversation) and produces a complete, executable autosarfactory Python script that writes the arxml, handling both workflows - system models (AF.new_file + AF.save) and ECUC configuration (definition loading or DEFINITION-REF post-processing + AF.save([file])). Syntax/API-checks the script and optionally runs it. Use after /autosar-plan or when the user invokes /autosar-generate.
argument-hint: [path/to/plan.json]
allowed-tools: Bash(python .claude/skills/autosar-plan/scripts/*), Bash(python .claude/skills/autosar-generate/scripts/*), Read, Write, Edit, AskUserQuestion
---

# /autosar-generate — AUTOSAR Code Generator

Turn an approved plan into a working autosarfactory script, check it, and (with
permission) run it.

Plan: `$ARGUMENTS`

```
P=.claude/skills/autosar-plan/scripts
G=.claude/skills/autosar-generate/scripts
```

This skill is the Claude Code CLI form of the MCP prompt `autosar-generate`; the logic
lives in `mcp_server/autosarfactory_mcp/workflow/` and is shared by both. The helpers run
from the repo root, print JSON, and call the MCP server's tools in-process, so they work
even when the MCP server is not connected.

---

## Step 1 — Load the plan

- `$ARGUMENTS` is a path → use it.
- Empty → use the most recent approved plan in this conversation; if it exists only
  as JSON in the chat, write it to `<dir of output.arxml>/<stem>.plan.json` first.
- No plan at all → stop and suggest `/autosar-plan <request>`.

Re-validate (read-only) before generating:

```bash
python $P/validate_plan.py <plan.json>
```

Errors → do not generate; show them and suggest re-running `/autosar-plan`.
If the plan was never approved by the user, show its step table and get approval first.

## Step 2 — Enrich via MCP and render the draft (no AI)

```bash
python $G/enrich_plan.py <plan.json> --draft <plan.output.script> --summary
```

Returns the **mode**, mode-specific **rules**, enum aliases with their literals,
per-class API (`new` / `references` / `attributes`), and for ECUC the definition
constraints. The draft script is rendered deterministically from the plan with
the correct boilerplate for the mode:

| mode | file workflow |
|---|---|
| `system_new` | `AF.new_file(OUTPUT_ARXML, defaultArPackage=…, overWrite=True)` → model → `AF.save()` |
| `system_modify` | `AF.read(INPUT_ARXMLS)` (check flag) → `AF.get_node()` (check None) → model → `AF.save()` |
| `ecuc_with_defs` | `AF.read(ECUC_DEFS)` → `AF.new_file(...)` → values + `set_definition(_def(path))` → `AF.save([OUTPUT_ARXML])` |
| `ecuc_defref_postprocess` | `AF.new_file(...)` → values + `_defref(obj, path, DEST)` → `AF.save([OUTPUT_ARXML])` → `_apply_definition_refs(OUTPUT_ARXML)` |

Why ECUC differs: `set_definition()` needs the definition object, which only
exists after the definition arxml is loaded. Without it, DEFINITION-REF elements
are patched into the saved file — and only *after* `AF.save()`, because save
rebuilds dirty nodes. ECUC must save with an explicit file list so the loaded
definition arxml is never rewritten.

## Step 3 — Generate the script (the AI step)

Read the draft and finish it into the final script at `output.script`. The draft
already encodes every plan step; your job is to make it complete and correct for
the user's request. Strict rules:

1. **Imports**: keep `from autosarfactory import autosarfactory as AF` with the
   `sys.path` fallback exactly as drafted. No other autosarfactory import style.
2. **Enum aliasing**: enums are aliased at module level (`ByteOrderEnum = AF.ByteOrderEnum`)
   and used as bare expressions `ByteOrderEnum.VALUE_…`. Never quote an enum.
   Literals only from `enum_aliases`.
3. **API names**: only methods listed under `classes` in the enrichment (or returned
   by `python $P/af_mcp.py …`). Never invent `new_`/`set_`/`add_` names.
4. **Save workflow**: follow the mode table above verbatim — do not mix modes.
5. **ECUC DEFINITION-REF**: `ecuc_with_defs` → `set_definition(_def(path))` on every
   value; `ecuc_defref_postprocess` → `_defref(obj, path, DEST)` on every value and
   `_apply_definition_refs()` after `AF.save([OUTPUT_ARXML])`. Paths/DEST come from the plan, never hand-built.
6. **Structure**: keep one `# --- Sx: description ---` section comment and one
   `_step("Sx", …)` progress print per plan step, in plan order; all modelling
   inside `main()`; `AF.reinit()` first.
7. **Fidelity**: implement nothing that is not in the plan. If the plan is missing
   something the request clearly needs, stop and tell the user (suggest adjusting
   the plan) instead of improvising.

## Step 4 — Syntax/API check (no AI)

```bash
python $G/check_script.py <script.py> --plan <plan.json>
```

Checks syntax, the import, quoted enums, enum literals, every `new_/set_/add_`
name against the API DB, the save/DEFINITION-REF ordering rules and per-step
sections. Fix all `errors` and re-run until `ok: true` (max 3 rounds, then show
the remaining errors to the user). Mention warnings in the summary.

## Step 5 — Approve execution, run, confirm

Show a short summary (script path, mode, output arxml, step count, check result) and
ask with AskUserQuestion: **Run now** / **Don't run**. For `system_modify`, warn that
the input arxml files will be rewritten in place.

If approved:

```bash
python <script.py>
python $G/verify_arxml.py <output.arxml> --plan <plan.json>
```

- Success → report the arxml path, size, element counts, DEFINITION-REF count (ECUC)
  and that every planned shortName is present.
- Failure → show the traceback, diagnose (usually a wrong parent/method or a missing
  definition path), fix the script, re-run Step 4, and ask again before re-running.

If not approved → give the command to run it later: `python <script.py>`.
