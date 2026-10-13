# AutosarFactory MCP Server

The MCP server exposes the autosarfactory API to AI coding assistants such as Claude Code. It allows an AI agent to query the full API reference, discover element hierarchies, look up enum values, and generate correct autosarfactory Python scripts — all without needing to read source code manually.

## Setup

Install the required dependency first:

```bash
pip install "mcp[cli]<2"
```

> The server uses the mcp 1.x `FastMCP` API; mcp 2.x renamed it. If startup fails with
> `PydanticUserError: A non-annotated attribute was detected`, upgrade pydantic
> (`pip install -U pydantic`).

### Claude Code (quickest)

Run once from the repo root — Claude Code registers the server globally for this project:

```bash
claude mcp add autosarfactory -e PYTHONPATH=./mcp_server -- python -m autosarfactory_mcp.server
```

To include the optional `--include-common-methods` flag:

```bash
claude mcp add autosarfactory -e PYTHONPATH=./mcp_server -- python -m autosarfactory_mcp.server --include-common-methods
```

Verify the server is registered:

```bash
claude mcp list
```

---

### VS Code / other MCP clients

There are two ways to run the server: **stdio** (recommended, VS Code manages the process) or **HTTP** (you start the server manually and VS Code connects to it).

---

### Option A — stdio (recommended)

VS Code starts and stops the server automatically. No manual process management needed.

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "autosarfactory": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "autosarfactory_mcp.server"],
      "env": {
        "PYTHONPATH": "${workspaceFolder}/mcp_server"
      }
    }
  }
}
```

#### Server flags

| Flag | Default | Description |
|---|---|---|
| `--include-common-methods` | off | Include arxml infrastructure base-class methods (`set_timestamp`, `set_checksum`, `new_AdminData`, `new_Desc`, `new_Introduction`, `new_LongName`, `new_ShortNameFragment`, `new_Annotation`) in `get_class()` responses. Omitted by default to keep responses lean — these methods are rarely needed for modelling. |

To enable, add the flag to the `args` array:

```json
"args": ["-m", "autosarfactory_mcp.server", "--include-common-methods"]
```

---

### Option B — HTTP (manual server start)

Use this if you want to keep the server running persistently, share it across workspaces, or inspect its output directly.

**1. Start the server manually** (choose one transport):

```bash
# SSE transport (default port 8080)
cd mcp_server
PYTHONPATH=. python -m autosarfactory_mcp.server --transport sse --port 8080

# Streamable HTTP transport
cd mcp_server
PYTHONPATH=. python -m autosarfactory_mcp.server --transport streamable-http --port 8080
```

The `--host` flag defaults to `0.0.0.0`. To bind to localhost only:

```bash
python -m autosarfactory_mcp.server --transport sse --host 127.0.0.1 --port 8080
```

**2. Point `.vscode/mcp.json` at the running server:**

```json
{
  "servers": {
    "autosarfactory": {
      "type": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

For `streamable-http` transport, use:

```json
{
  "servers": {
    "autosarfactory": {
      "type": "http",
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

## What it does

- **`find_creation_chain(elementType)`** — full creation chain from ArPackage down to an element in one call (use this first)
- **`find_creators_of(elementType)`** — immediate parent class and method for a given element type
- **`get_class(className, section)`** — cross-reference and attribute methods on a class (`section`: `references`, `attributes`, or `all`)
- **`search_classes(keyword)`** — finds class names matching a keyword
- **`get_enum(enumName)`** / **`list_enums()`** — valid enum values as ready-to-use Python expressions
- **`get_system_element_map(useCase)`** — AUTOSAR element hierarchy for a modelling use case (SWC, CAN, Ethernet, DEXT etc.)
- **`new_file_script_template()`** — boilerplate for creating a new arxml file
- **`read_file_script_template()`** — boilerplate for reading and modifying existing arxml files
- **`search_autosar_knowledge(query)`** — semantic search over AUTOSAR spec documents (requires a knowledge base, see below)
- **`list_ecuc_modules()`** / **`get_ecuc_module()`** / **`get_ecuc_container()`** — ECUC/BSW module configuration (requires `ecuc_param_def.json`, see below)

## Plan-then-generate workflow

Two MCP **prompts** drive a human-in-the-loop workflow. MCP clients list them as prompts
or slash commands; in Claude Code they appear as `/mcp__autosarfactory__autosar-plan` and
`/mcp__autosarfactory__autosar-generate`.

| Prompt | Argument | What it does |
|---|---|---|
| `autosar-plan` | `request` | Detects system vs ECUC, asks 3-5 clarifying questions, confirms scope, gathers API context, writes a plan JSON, validates and auto-corrects it, and presents it for approval. Writes no code. |
| `autosar-generate` | `plan` (path, optional) | Re-validates the approved plan, renders a draft script, finishes it, checks it, and (after approval) runs it and verifies the arxml. |

The prompts use these tools, which can also be called directly:

- **`detect_request_type(request)`** — classify a request as `system`, `ecuc`, `mixed` or `unknown`
- **`gather_modelling_context(request_type, ...)`** — all classes, creation chains, enums and ECUC container definitions for a plan in one call, with an explicit `mcp_connectivity` status
- **`get_plan_schema()`** — the plan JSON format
- **`validate_plan(plan, fix)`** — validate a plan against the API / ECUC data; `fix=True` auto-corrects class, method, enum and ECUC names
- **`render_script_draft(plan, draft_path)`** — render a deterministic draft script. The mode is chosen from the plan: `system_new`, `system_modify`, `ecuc_with_defs`, or `ecuc_defref_postprocess` (writes DEFINITION-REF after save when no ECUC definition arxml is available)
- **`check_generated_script(script, plan)`** — syntax, API-name, enum and save-order checks
- **`verify_arxml(arxml_path, plan)`** — confirm the arxml loads and contains everything the plan creates

`plan`, `script` and `arxml_path` accept file paths (resolved on the machine running the
server) or inline content. The workflow code lives in `autosarfactory_mcp/workflow/`.
The same workflow is available as the Claude Code project skills `/autosar-plan` and
`/autosar-generate` (`.claude/skills/`), which call these tools in-process and work
without a connected MCP server.

## Optional: AUTOSAR specification knowledge base

The `search_autosar_knowledge` tool becomes available when a pre-built knowledge base (`.pkl` file) is placed in `mcp_server/autosarfactory_mcp/kb/`. To build one from AUTOSAR spec PDFs or text files:

```bash
pip install sentence-transformers numpy pdfplumber
python mcp_server/kb_builder/build_knowledge_base.py --docs /path/to/autosar/specs/ --output autosar_kb.pkl
```

Multiple `.pkl` files are supported — the server merges them all at startup. Use distinct output names for different topic areas (e.g. `autosar_com_kb.pkl`, `autosar_dext_kb.pkl`).

## Optional: ECUC parameter definition

The `list_ecuc_modules`, `get_ecuc_module`, and `get_ecuc_container` tools become
available when a pre-built `ecuc_param_def.json` file is placed in
`mcp_server/autosarfactory_mcp/db/`. This file captures the module → container →
parameter / reference hierarchy from AUTOSAR ECUC module definition arxml files
and is used by the agent to look up container structure and value classes when
generating ECU configuration scripts.

Use the `ecuc_module_def_to_json.py` script (at the repo root) to generate or
update this file from your own arxml files.

### Generate from scratch

```bash
python ecuc_module_def_to_json.py <file.arxml> [<file2.arxml> ...] -o mcp_server/autosarfactory_mcp/db/ecuc_param_def.json
```

### Update specific modules (merge mode)

Modules found in the arxml replace their counterpart in the existing JSON by name.
Modules not present in the arxml are left untouched. New modules are appended.

```bash
# Update in-place
python ecuc_module_def_to_json.py <file.arxml> --update mcp_server/autosarfactory_mcp/db/ecuc_param_def.json

# Update only a specific module
python ecuc_module_def_to_json.py <file.arxml> --module CanIf --update mcp_server/autosarfactory_mcp/db/ecuc_param_def.json

# Update and write to a different file
python ecuc_module_def_to_json.py <file.arxml> --update mcp_server/autosarfactory_mcp/db/ecuc_param_def.json -o ecuc_param_def_new.json
```

After updating the file, restart the MCP server so it reloads the new data.

## AUTOSAR element map

The file `autosarfactory_mcp/ar_map/autosar_element_map.md` contains a human-readable and agent-readable map of which AUTOSAR elements are needed for each modelling use case (Sender-Receiver, CAN, Ethernet/SOME/IP, DEXT, calibration, etc.). This file is loaded automatically at server startup and can be extended without modifying any Python code — just edit the `.md` file and restart the MCP server.
