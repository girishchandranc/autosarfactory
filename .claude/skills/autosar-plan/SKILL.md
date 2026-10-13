---
name: autosar-plan
description: AUTOSAR Modelling Planner. Turns a natural-language AUTOSAR modelling request (system model - SWCs, ports, interfaces, data types, CAN/Ethernet networks - or ECUC/BSW module configuration) into a validated, step-by-step autosarfactory plan JSON through a human-in-the-loop dialogue. Writes no code. Use when the user wants to plan/design an arxml model before generating it, or invokes /autosar-plan.
argument-hint: <modelling request in plain language>
allowed-tools: Bash(python .claude/skills/autosar-plan/scripts/*), Read, Write, AskUserQuestion
---

# /autosar-plan — AUTOSAR Modelling Planner

Turn the request into an **approved, validated plan JSON**. You write **no Python
modelling code** in this skill — that is `/autosar-generate`'s job.

Request: `$ARGUMENTS` (if empty, ask the user what they want to model).

This skill is the Claude Code CLI form of the MCP prompt `autosar-plan`; the logic
lives in `mcp_server/autosarfactory_mcp/workflow/` and is shared by both. The helper
scripts run from the repo root, print JSON, and call the MCP server's tools
in-process (`af_mcp.py`), so they work even when the MCP server is not connected.

```
S=.claude/skills/autosar-plan/scripts
```

Plan format: read [plan_schema.md](../../../mcp_server/autosarfactory_mcp/workflow/prompts/plan_schema.md) (also served by the MCP tool `get_plan_schema`) before writing a plan.

---

## Step 1 — Detect the request type

```bash
python $S/detect_request_type.py "<request>"
```

- `type: "system"` → system model (AF.new_file + elements in ARPackages).
- `type: "ecuc"` → BSW module configuration (EcucModuleConfigurationValues + containers).
- `mixed` / `unknown`, or confidence < 0.7 → ask the user which one they mean
  (one AskUserQuestion). A mixed request becomes two plans; plan one at a time.

Keep the returned `ecuc_modules` / `use_cases` — they seed Step 4.

## Step 2 — Clarify intent (3–5 questions)

Ask **only** what the request leaves open, using AskUserQuestion (≤4 questions per
call, offer concrete options with a recommended default first). Never ask about
something the user already stated. Typical gaps:

**System**
- Element names: SWC names, port names, interface name, data element names.
- Data type: reuse a base type (uint8/uint16/float32…) or define a new one; compu method?
- Topology: single-ECU SWC-to-SWC, or over a bus (CAN / Ethernet SOME/IP) — ECU instance names, cluster/baud rate, frame/PDU/signal names and IDs.
- Output: arxml file name and root ARPackage name (default `Examples/generated/<slug>.arxml`, package `<Slug>`).

**ECUC**
- Module(s) and how many instances of each container (e.g. 3 OsTasks).
- Concrete parameter values, or "use defaults / sensible values within min-max".
- Is an ECUC **definition arxml** available? (path) — if not, the generator uses DEFINITION-REF post-processing.
- Implementation config variant (PRE-COMPILE / LINK-TIME / POST-BUILD).
- Output arxml file name.

## Step 3 — Confirm scope

Show a compact table, then ask **Approve / Adjust / Cancel** (AskUserQuestion):

| Item | Value |
|---|---|
| Request type | system / ecuc |
| Use case(s) / module(s) | … |
| Elements to create | … (names) |
| Values / topology | … |
| Inputs | definition arxml / read arxml / none |
| Output | `<arxml>` (root package `<name>`) |
| Assumptions | … |

Adjust → update and re-show. Cancel → stop.

## Step 4 — Gather live MCP context (no tokens on lookups)

One call per plan; pass every element type / container you expect to need:

```bash
# system
python $S/gather_context.py system --use-case "<keyword>" [--use-case ...] \
    --elements ClassA,ClassB,... [--enums EnumA,...] [--check-cli]
# ecuc
python $S/gather_context.py ecuc --modules Os[,CanIf] [--containers OsTask,OsAlarm] [--depth 1] [--check-cli]
```

- System: start with the element map (`--use-case`) to learn which classes are
  needed, then call again with `--elements` for those classes. Each class returns
  its `creation_chain`, `references` (set_/add_), `attributes` (set_), and enum
  values. When `ambiguous_parents` is present, choose the parent the element map /
  request implies (e.g. PPortPrototype → ApplicationSwComponentType), not the
  first chain shown.
- ECUC: containers come with `mandatory`, `min`/`max`/`default`, enum `literals`,
  reference `destination`, and the exact definition `path` to put in the plan.
- Unknown names come back with `did_you_mean` — use those, never guess.
- For a one-off lookup use `python $S/af_mcp.py <tool> '<json kwargs>'`
  (tools: find_creators_of, creation_chain, get_class, get_enum, search_classes,
  get_ecuc_container, get_ecuc_param_literals, get_system_element_map, list_ecuc_modules).

### MCP connectivity — always show it explicitly

Report a one-line banner from `mcp_connectivity` plus whether `mcp__autosarfactory__*`
tools are available in this session, e.g.:

> **MCP context:** API DB ✅ 2042 classes · ECUC DB ✅ 112 modules · element map ✅ · spec KB ❌ · MCP server tools in session: ❌ (using in-process DB — same data)

If `api_db` (or `ecuc_db` for ECUC) is not loaded, say that API names are
**unverified**, mark every affected step in the plan, and recommend fixing the
setup before generating.

## Step 5 — Write the plan JSON

Follow [plan_schema.md](../../../mcp_server/autosarfactory_mcp/workflow/prompts/plan_schema.md) exactly:
- Explicit order, one action per step, `depends_on` for every variable used.
- Methods and classes **only** from Step 4 output.
- Each shared element type in its own ARPackage (DataTypes, Interfaces, Swcs, …).
- Unique shortNames per parent; valid identifiers (`[A-Za-z][A-Za-z0-9_]*`).
- Variable names must not shadow script names (`os`, `sys`, `AF`, `main`, enum/class names).
- ECUC: every value step carries `definition.path/type` from `get_ecuc_container`;
  create all **mandatory** containers/parameters, values from the user → default →
  a value within min/max; enum literals only from `literals`.
- Copy `mcp_connectivity` into the plan; list every assumption.

Save it to `<dir of output.arxml>/<stem>.plan.json` (create the folder).

## Step 6 — Validate against live MCP (auto-correct)

```bash
python $S/validate_plan.py <plan.json> --fix
```

It corrects unknown/misspelled class names, wrong `new_` method names, wrong
returned classes, enum literal typos, ECUC def types/literals and missing
`depends_on`, and re-validates. Then:
- `errors` remaining → fix them yourself using Step 4 lookups and re-run (max 3 rounds);
  if still failing, show the errors to the user and ask how to proceed.
- `warnings` (e.g. missing mandatory ECUC items, values without defaults) → resolve
  or carry them into the presentation as open points.

## Step 7 — Present for approval

Show:
1. The MCP connectivity banner.
2. A step table: `Step | Action | Code-ish summary | Depends on`
   (e.g. `S6 | new | ifPkg.new_SenderReceiverInterface('SrIf_Speed') | S5`).
3. Auto-corrections the validator made (from → to, why).
4. Remaining warnings, assumptions, and the plan file path.

Ask **Approve / Adjust / Cancel**. On adjust, edit the plan and go back to Step 6.
On approve, tell the user to run `/autosar-generate <plan path>`. Do **not**
generate the script here.
