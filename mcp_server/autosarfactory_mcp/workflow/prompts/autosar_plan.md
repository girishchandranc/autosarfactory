# autosar-plan — AUTOSAR Modelling Planner

Turn the request below into an **approved, validated plan JSON** through a dialogue
with the user. Write **no Python modelling code** — generation is the
`autosar-generate` prompt's job.

**Request:** {{REQUEST}}

(If the request is empty, ask the user what they want to model.)

All lookups go through the autosarfactory MCP tools named below. Never guess an
API name — use only names returned by these tools.

---

## Step 1 — Detect the request type

Call `detect_request_type(request)`.

- `type: "system"` → system model (SWCs, ports, interfaces, data types, networks).
- `type: "ecuc"` → BSW module configuration (EcucModuleConfigurationValues + containers).
- `mixed` / `unknown`, or confidence < 0.7 → ask the user which one they mean. A mixed
  request becomes two plans; plan one at a time.

Keep `ecuc_modules` / `use_cases` from the result — they seed Step 4.

## Step 2 — Clarify intent (3–5 questions)

Ask **only** what the request leaves open, in one round, offering concrete options with
a recommended default first (use your client's question tool if it has one). Never ask
about something already stated. Typical gaps:

**System** — SWC / port / interface / data element names · data type (reuse uint8/uint16/
float32… or define one, compu method?) · topology: single-ECU SWC-to-SWC or over a bus
(CAN / Ethernet SOME/IP: ECU instances, cluster, baud rate, frame/PDU/signal names, IDs) ·
output arxml file and root ARPackage name.

**ECUC** — module(s) and number of instances per container · concrete parameter values
or "defaults / sensible values within min–max" · is an ECUC **definition arxml**
available (path)? — if not, the generator uses DEFINITION-REF post-processing ·
implementation config variant · output arxml file.

## Step 3 — Confirm scope

Show this table, then ask **Approve / Adjust / Cancel**:

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

## Step 4 — Gather live MCP context

One call per plan, listing everything you expect to need:

- System: `gather_modelling_context(request_type="system", use_cases=[...], elements=[...], enums=[...])`.
  Start with `use_cases` to learn which classes the use case needs, then call again with
  `elements`. Each class returns `creation_chain`, `references` (set_/add_), `attributes`
  (set_) and enum values. With `ambiguous_parents`, choose the parent the use case /
  request implies (e.g. PPortPrototype → ApplicationSwComponentType), not the first chain.
- ECUC: `gather_modelling_context(request_type="ecuc", modules=[...], containers=[...], depth=1)`.
  Containers come with `mandatory`, `min`/`max`/`default`, enum `literals`, reference
  `destination` and the exact definition `path` to put in the plan.
- Unknown names return `did_you_mean` — use those.
- Single lookups: `find_creators_of`, `find_creation_chain`, `get_class`, `get_enum`,
  `search_classes`, `get_ecuc_container`, `get_ecuc_param_literals`.

### MCP connectivity — always show it explicitly

Show a one-line banner from `mcp_connectivity`, e.g.

> **MCP context:** API DB ✅ 2042 classes · ECUC DB ✅ 112 modules · element map ✅ · spec KB ❌

If `api_db` (or `ecuc_db` for ECUC) is not loaded, say that API names are **unverified**,
mark the affected steps, and recommend fixing the setup before generating.

## Step 5 — Write the plan JSON

Call `get_plan_schema()` and follow it exactly:
- Explicit order, one action per step, `depends_on` for every variable used.
- Classes and methods **only** from Step 4 results.
- Each shared element type in its own ARPackage (DataTypes, Interfaces, Swcs, …).
- Unique shortNames per parent; identifiers match `[A-Za-z][A-Za-z0-9_]*`.
- Variable names must not shadow script names (`os`, `sys`, `AF`, `main`, enum/class names).
- ECUC: every value step carries `definition.path/type` from the context; create all
  **mandatory** containers/parameters; values from the user → default → a value within
  min/max; enumeration literals only from `literals`.
- Copy `mcp_connectivity` into the plan and list every assumption.

Save it to `<dir of output.arxml>/<stem>.plan.json` if you can write files; otherwise
keep it in the conversation.

## Step 6 — Validate against live MCP (auto-correct)

Call `validate_plan(plan=<path or JSON>, fix=true)`. It corrects misspelled classes, wrong
`new_` methods, wrong returned classes, enum literal typos, ECUC def types/literals and
missing `depends_on`, re-validates, and returns the corrected `plan` (and writes it back
when given a path).

- `errors` left → fix them using Step 4 lookups and re-validate (max 3 rounds); then show
  the remaining errors to the user and ask how to proceed.
- `warnings` (missing mandatory ECUC items, values without defaults…) → resolve, or carry
  them into the presentation as open points.

## Step 7 — Present for approval

Show:
1. The MCP connectivity banner.
2. Step table: `Step | Action | Code-ish summary | Depends on`
   (e.g. `S6 | new | ifPkg.new_SenderReceiverInterface('SrIf_Speed') | S5`).
3. The validator's auto-corrections (from → to, why).
4. Remaining warnings, assumptions, and the plan location.

Ask **Approve / Adjust / Cancel**. Adjust → edit the plan and go back to Step 6.
Approve → tell the user to run the `autosar-generate` prompt with the plan. Do **not**
generate the script here.
