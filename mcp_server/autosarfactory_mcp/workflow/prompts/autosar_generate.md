# autosar-generate — AUTOSAR Code Generator

Turn an approved `autosar-plan` plan into a working autosarfactory script, check it,
and — only with the user's permission — run it.

**Plan:** {{PLAN}}

(A path to a plan JSON file, or empty → use the most recent approved plan in this
conversation. No plan at all → stop and suggest the `autosar-plan` prompt.)

---

## Step 1 — Load and re-validate the plan

Call `validate_plan(plan=<path or JSON>)` (no fix). Errors → do not generate; show them
and suggest re-running `autosar-plan`. If the user never approved the plan, show its
step table and get approval first.

## Step 2 — Enrich via MCP and render the draft (deterministic)

Call `render_script_draft(plan=<path or JSON>, draft_path=<plan.output.script>, summary=true)`
(omit `draft_path` and `summary` if you cannot write files — the script text is then
returned as `script`).

It returns the **mode**, mode-specific **rules**, enum aliases with their literals,
per-class API (`new` / `references` / `attributes`), ECUC definition constraints, and a
draft rendered from the plan with the correct boilerplate:

| mode | file workflow |
|---|---|
| `system_new` | `AF.new_file(OUTPUT_ARXML, defaultArPackage=…, overWrite=True)` → model → `AF.save()` |
| `system_modify` | `AF.read(INPUT_ARXMLS)` (check flag) → `AF.get_node()` (check None) → model → `AF.save()` |
| `ecuc_with_defs` | `AF.read(ECUC_DEFS)` → `AF.new_file(...)` → values + `set_definition(_def(path))` → `AF.save([OUTPUT_ARXML])` |
| `ecuc_defref_postprocess` | `AF.new_file(...)` → values + `_defref(obj, path, DEST)` → `AF.save([OUTPUT_ARXML])` → `_apply_definition_refs(OUTPUT_ARXML)` |

Why ECUC differs: `set_definition()` needs the definition object, which exists only after
the definition arxml is loaded. Without it, DEFINITION-REF elements are patched into the
saved file — strictly *after* `AF.save()`, because save rebuilds dirty nodes. ECUC saves
with an explicit file list so the loaded definition arxml is never rewritten.

## Step 3 — Generate the script

Finish the draft into the final script at `output.script`. The draft already encodes
every plan step; make it complete and correct for the request. Strict rules:

1. **Imports**: keep `from autosarfactory import autosarfactory as AF` (plus the `sys.path`
   fallback if the draft has one). No other import style.
2. **Enum aliasing**: module-level aliases (`ByteOrderEnum = AF.ByteOrderEnum`) used as bare
   expressions `ByteOrderEnum.VALUE_…`. Never quote an enum. Literals only from `enum_aliases`.
3. **API names**: only methods listed under `classes` (or returned by the lookup tools).
   Never invent `new_`/`set_`/`add_` names.
4. **Save workflow**: follow the mode table verbatim — never mix modes.
5. **ECUC DEFINITION-REF**: `ecuc_with_defs` → `set_definition(_def(path))` on every value;
   `ecuc_defref_postprocess` → `_defref(obj, path, DEST)` on every value and
   `_apply_definition_refs()` after `AF.save([OUTPUT_ARXML])`. Paths and DEST come from the plan.
6. **Structure**: one `# --- Sx: description ---` section comment and one `_step("Sx", …)`
   progress print per plan step, in plan order; all modelling inside `main()`;
   `AF.reinit()` first.
7. **Fidelity**: implement nothing outside the plan. If the plan lacks something the request
   clearly needs, stop and tell the user (suggest adjusting the plan) instead of improvising.

## Step 4 — Syntax / API check

Call `check_generated_script(script=<path or source>, plan=<path or JSON>)`. It checks
syntax, the import, quoted enums, enum literals, every `new_/set_/add_` name against the
API DB, the save / DEFINITION-REF ordering rules, and per-step sections. Fix all `errors`
and re-check until `ok: true` (max 3 rounds, then show the remaining errors). Mention
warnings in the summary.

## Step 5 — Approve execution, run, confirm

Show a short summary (script path, mode, output arxml, step count, check result) and ask
**Run now / Don't run**. For `system_modify`, warn that the input arxml files will be
rewritten in place.

If approved, run `python <script.py>` with your shell tool, then call
`verify_arxml(arxml_path=<output.arxml>, plan=<path or JSON>)`:

- Success → report the arxml path, size, element counts, DEFINITION-REF count (ECUC) and
  that every planned shortName is present.
- Failure → show the traceback, diagnose (usually a wrong parent/method or a missing
  definition path), fix, re-check (Step 4) and ask again before re-running.

If not approved (or no shell tool is available) → give the command: `python <script.py>`.
