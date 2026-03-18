"""
autosarfactory MCP Server

Provides queryable access to the autosarfactory API reference and
helps AI agents to generate Autosar complaint arxml files.
"""

from mcp.server.fastmcp import FastMCP
import json
import pathlib
import sys
import warnings
warnings.filterwarnings("ignore")

# Administrative base-class methods present on almost every AUTOSAR class.
# Stripped from get_class() responses by default; pass --include-common-methods
# to the server to include them.
_COMMON_METHODS = frozenset({
    "set_timestamp", "set_checksum",
    "new_AdminData", "new_Desc", "new_Introduction",
    "new_LongName", "new_ShortNameFragment", "new_Annotation",
})
_include_common_methods: bool = False  # overridden by --include-common-methods arg

_DB_PATH       = pathlib.Path(__file__).parent / "db/af_api_reference.json"
_ECUC_PATH     = pathlib.Path(__file__).parent / "db/ecuc_param_def.json"
_KB_DIR        = pathlib.Path(__file__).parent / "kb"
_ELEM_MAP_PATH = pathlib.Path(__file__).parent / "ar_map/autosar_element_map.md"

def _load_db() -> dict:
    """
    Load the json database of the autosarfactory apis.
    Normalizes list-of-single-key-dicts format into plain dicts for fast lookup.
    """
    if not _DB_PATH.exists():
        raise FileNotFoundError(
            f"af_api_reference.json not found at {_DB_PATH}. "
            "Please check the github repo or get in touch with the owner of autosarfactory to provide it."
        )
    db = json.loads(_DB_PATH.read_text(encoding="utf-8"))
    # af_api_reference.json stores classes/enums as lists of single-key dicts;
    # flatten them into plain name->data dicts for O(1) lookup.
    if isinstance(db.get("classes"), list):
        flat = {}
        for entry in db["classes"]:
            flat.update(entry)
        db["classes"] = flat
    if isinstance(db.get("enums"), list):
        flat = {}
        for entry in db["enums"]:
            flat.update(entry)
        db["enums"] = flat
    return db

# ECUC part
_ecuc_modules       = {}   # module_name -> module dict (top-level containers only)
_ecuc_containers    = {}   # container_name -> list of {module, path, parent, parentType, data}
_ecuc_enum_literals = {}   # param_path -> literals list  (EcucEnumerationParamDef only)

# Maps ECUC definition class names -> the configuration value class
_DEF_TO_VALUE: dict[str, str] = {
    # Module
    "EcucModuleDef":                  "EcucModuleConfigurationValues",
    "EcucParamConfContainerDef":      "EcucContainerValue",
    "EcucChoiceContainerDef":         "EcucContainerValue",
    # Integer / float / boolean parameters
    "EcucIntegerParamDef":            "EcucNumericalParamValue",
    "EcucFloatParamDef":              "EcucNumericalParamValue",
    "EcucBooleanParamDef":            "EcucNumericalParamValue",
    # String / enumeration / function-name parameters
    "EcucStringParamDef":             "EcucTextualParamValue",
    "EcucEnumerationParamDef":        "EcucTextualParamValue",
    "EcucFunctionNameDef":            "EcucTextualParamValue",
    "EcucLinkerSymbolDef":            "EcucTextualParamValue",
    # References
    "EcucReferenceDef":               "EcucReferenceValue",
    "EcucForeignReferenceDef":        "EcucReferenceValue",
    "EcucChoiceReferenceDef":         "EcucReferenceValue",
    "EcucSymbolicNameReferenceDef":   "EcucReferenceValue",
    "EcucInstanceReferenceDef":       "EcucInstanceReferenceValue",
}


def _enrich(items: list) -> list:
    """Add 'valueClass' to each parameter or reference dict (full data kept for literals lookup)."""
    return [{**item, "valueClass": _DEF_TO_VALUE.get(item["type"], item["type"])}
            for item in items]

# Fields returned by get_ecuc_container — constraint fields omitted to reduce token usage.
# Full data (including literals, min, max, default) stays in the index for get_ecuc_param_literals.
_RESPONSE_PARAM_KEYS = {"name", "type", "path", "valueClass", "multiplicity"}
_RESPONSE_REF_KEYS   = {"name", "type", "path", "valueClass", "multiplicity", "destination"}

def _trim_for_response(entry: dict) -> dict:
    """Return a token-lean copy of a container index entry for get_ecuc_container responses."""
    return {
        "module":           entry["module"],
        "path":             entry["path"],
        "parent":           entry["parent"],
        "parentType":       entry["parentType"],
        "parentValueClass": entry["parentValueClass"],
        "type":             entry["type"],
        "valueClass":       entry["valueClass"],
        "parameters":  [{k: v for k, v in p.items() if k in _RESPONSE_PARAM_KEYS}
                        for p in entry["parameters"]],
        "references":  [{k: v for k, v in r.items() if k in _RESPONSE_REF_KEYS}
                        for r in entry["references"]],
        "subContainers": entry["subContainers"],
    }


def _index_container(container: dict, module_name: str,
                     parent_name: str, parent_type: str):
    """Recursively index every container into _ecuc_containers."""
    entry = {
        "module":      module_name,
        "path":        container.get("path", ""),
        "parent":      parent_name,
        "parentType":  parent_type,
        "parentValueClass": _DEF_TO_VALUE.get(parent_type, parent_type),
        "type":        container["type"],
        "valueClass":  _DEF_TO_VALUE.get(container["type"], container["type"]),
        "multiplicity": container.get("multiplicity"),
        "parameters":  _enrich(container.get("parameters", [])),
        "references":  _enrich(container.get("references", [])),
        "subContainers": [s["name"] for s in container.get("subContainers", [])],
    }
    name = container["name"]
    _ecuc_containers.setdefault(name, []).append(entry)
    for param in entry["parameters"]:
        if param["type"] == "EcucEnumerationParamDef" and param.get("path"):
            _ecuc_enum_literals[param["path"]] = param.get("literals", [])
    for sub in container.get("subContainers", []):
        _index_container(sub, module_name,
                         parent_name=name, parent_type=container["type"])

if _ECUC_PATH.exists():
    try:
        _ecuc_raw = json.loads(_ECUC_PATH.read_text(encoding="utf-8"))
        for mod in _ecuc_raw.get("modules", []):
            _ecuc_modules[mod["name"]] = mod
            for c in mod.get("containers", []):
                _index_container(c, mod["name"],
                                 parent_name=mod["name"], parent_type="EcucModuleDef")
    except Exception as e:
        print(f"[autosarfactory-mcp] Failed to load ECUC param def: {e}", file=sys.stderr)
else:
    print(f"[autosarfactory-mcp] No ecuc_param_def.json found — ECUC tools disabled.", file=sys.stderr)

# ---------------------------------------------------------------------------

_kb       = None   # {'chunks': list[str], 'embeddings': np.ndarray}
_kb_model = None   # SentenceTransformer instance

_pkl_files = sorted(_KB_DIR.glob("*.pkl"))
if _pkl_files:
    try:
        import pickle
        import numpy as np
        from sentence_transformers import SentenceTransformer

        all_chunks     = []
        all_embeddings = []

        for pkl_path in _pkl_files:
            with open(pkl_path, "rb") as f:
                kb = pickle.load(f)
            all_chunks.extend(kb["chunks"])
            all_embeddings.append(kb["embeddings"])
            print(f"[autosarfactory-mcp] Loaded KB: {pkl_path.name} ({len(kb['chunks'])} chunks)", file=sys.stderr)

        _kb = {
            "chunks":     all_chunks,
            "embeddings": np.vstack(all_embeddings),
        }
        _kb_model = SentenceTransformer("all-MiniLM-L6-v2")
        print(f"[autosarfactory-mcp] Knowledge base ready: {len(_kb['chunks'])} chunks total "
              f"from {len(_pkl_files)} file(s)", file=sys.stderr)
    except ImportError:
        print("[autosarfactory-mcp] sentence-transformers not installed — knowledge base disabled.", file=sys.stderr)
    except Exception as e:
        print(f"[autosarfactory-mcp] Failed to load knowledge base: {e}", file=sys.stderr)

# Server instructions (this information is sent automatically during MCP handshake)
_kb_instruction = (
    "\n\n## AUTOSAR specification knowledge base\n"
    "A semantic knowledge base built from AUTOSAR specification documents is available.\n"
    "Call search_autosar_knowledge(query, top_k=5) whenever you need:\n"
    "  - Authoritative definitions of AUTOSAR elements\n"
    "  - Constraints and rules from the specification\n"
    "  - Clarification on element semantics or relationships\n"
    "Always search before making assumptions about AUTOSAR rules.\n"
) if _kb is not None else ""

_elem_map_sections: dict[str, str]        = {}  # use-case title -> section text (no depends_on lines)
_elem_map_chain:    dict[str, list[str]]  = {}  # use-case title -> [prereq1, prereq2, ..., self] (pre-resolved)
if _ELEM_MAP_PATH.exists():
    _deps: dict[str, list[str]] = {}
    _current_title: str | None = None
    _current_lines: list[str] = []
    for _line in _ELEM_MAP_PATH.read_text(encoding="utf-8").splitlines(keepends=True):
        if _line.startswith("### "):
            if _current_title is not None:
                _elem_map_sections[_current_title] = "".join(_current_lines).rstrip()
            _current_title = _line[4:].strip()
            _current_lines = [_line]
        elif _current_title is not None:
            if _line.strip().startswith("depends_on:"):
                dep = _line.strip()[len("depends_on:"):].strip()
                _deps.setdefault(_current_title, []).append(dep)
            else:
                _current_lines.append(_line)
    if _current_title is not None:
        _elem_map_sections[_current_title] = "".join(_current_lines).rstrip()

    # Resolve full dependency chains at startup (depth-first)
    def _build_chain(title: str, visited: set) -> list[str]:
        if title in visited:
            return []
        visited.add(title)
        result = []
        for dep in _deps.get(title, []):
            result.extend(_build_chain(dep, visited))
        result.append(title)
        return result

    for _t in _elem_map_sections:
        _elem_map_chain[_t] = _build_chain(_t, set())

    print(f"[autosarfactory-mcp] Element map loaded: {len(_elem_map_sections)} use case(s).", file=sys.stderr)
else:
    print(f"[autosarfactory-mcp] Warning: {_ELEM_MAP_PATH.name} not found — element map omitted.", file=sys.stderr)

_INSTRUCTIONS = f"""
You are an AUTOSAR modelling expert working with autosarfactory, a Python
library for creating AUTOSAR .arxml files.

## Mandatory workflow for using the autosarfactory APIs

1. Call get_system_element_map() to list available use cases, then call get_system_element_map(useCase)
   to retrieve the AUTOSAR elements and hierarchy needed for your specific use case.
   NOTE: this is for system model configuration only — do NOT call it for ECUC configuration.
2. ONLY call search_autosar_knowledge(query) if you need specification details or constraints.
3. Call search_classes(keyword) for an overview if unsure what the library supports.
4. For each element type you need to create, call find_creators_of(elementType) to discover
   which parent class and method to use. Do this BEFORE calling get_class on any parent.
   NEVER browse a parent class (e.g. ArPackage) to find what it can create — always go
   bottom-up: know the element you need, then find its creator.
5. After find_creators_of() succeeds you already have the method name and hasName — do NOT
   call get_class(section='children'), that is redundant. Only call get_class when you need
   cross-reference or attribute info:
     get_class(className, section='references') — dict of {{method: targetType}} for set_/add_
     get_class(className, section='attributes') — dict of {{method: primitiveType}} for set_
     get_class(className, section='all')        — full overview (rarely needed)
6. Call get_enum(enumName) before passing any enum value to a set_ method.
7. DO NOT create elements with same shortName under a parent node.
8. Always put elements of same type under different ARPackage.
9. If 2 elements of same type happen to have same shortName under a parent,
   ALWAYS use some suffix to differentiate.
10. NEVER ASSUME the api name yourself. Always use the method as returned to you
    from autosarfactory mcp.
11. Write the script only after confirming all API calls via these tools.

## API rules

- new_X(name) — creates an owned child element with a SHORT-NAME
- new_X()     — creates an anonymous owned element OR a ref-conditional wrapper
                call set_X() on it immediately
- set_X(obj)  — sets a cross-reference to an element defined elsewhere in the model
- add_X(obj)  — adds to a list of references (multiple values allowed)

## Ownership rule

If an element can be shared/referenced from multiple places, it lives in an ArPackage
and others reference it via set_(). If it belongs exclusively to one parent, it is
created directly on that parent via new_().

## ECUC module configuration workflow

The ecuc_param_def.json describes the Definition side (containers, parameters, references).
Tool responses include pre-computed 'valueClass'/'parentValueClass' fields — use them directly.

### Step-by-step

1. Call list_ecuc_modules() to see which BSW modules are available.
2. Call get_ecuc_module(moduleName) to see the top-level containers of a module.
3. Call get_ecuc_container(containerName, moduleName) to get the full container definition:
     - 'valueClass'       — autosarfactory class to CREATE this container's value
     - 'parentValueClass' — autosarfactory class of the parent value object
     - 'parameters[].valueClass' — class to use for each parameter value
     - 'references[].valueClass' — class to use for each reference value
4. Call find_creators_of(valueClass) to find which parent class creates a given value
   object. Do this for EVERY value class before writing code — do NOT browse parent
   classes manually. This is especially important for EcucModuleConfigurationValues
   (the module root) where the parent is typically ArPackage.
5. Call get_class(valueClass) and get_class(parentValueClass) to confirm the
   exact new_/set_ method names before writing any code.
6. Each value object must link back to its definition element via set_definition().
   Use the 'path' field from get_ecuc_container() (or from each parameter/reference
   entry) with AF.get_node(path) to retrieve the definition object, then pass it
   to set_definition(defObject).
   Do NOT construct the path manually — always use the 'path' field from the tool.
7. For references, the 'destination' field shows the target container path
   — use AF.get_node(destination) to retrieve the referenced definition object.
8. Setting parameter values:
   - EcucNumericalParamValue has an inner NumericalValueVariationPoint layer:
       * First time: call param.new_Value().set(numericValue)
       * To update:  call param.get_value().set(numericValue)
   - EcucTextualParamValue has no extra layer — call param.set_value(str) directly.
   - EcucEnumerationParamDef maps to EcucTextualParamValue but the valid strings are
     ECUC-specific — call get_ecuc_param_literals(param['path']) using the path to the parameter
     already returned by get_ecuc_container(), then param.set_value("CHOSEN_LITERAL").
     Do NOT guess literal strings.
9. MULTIPLICITY is provided in lower:upper format. If lower is greater than 0, it's a
   mandatory container/parameter. ALWAYS try to create mandatory container/parameter
   and set the value for it considering the min, max and default value.
   SET the value in following order:
   - If user has provided a value in the prompt, use it.
   - If not, use the default value.
   - If default value is missing, then use a value between min and max for EcucNumericalParamValue.
10. ECUC definition file MUST be loaded before any AF.get_node() call or set_definition()
    will fail. The generated script MUST include a read() call for the definition arxml
    at the top, with a clearly marked placeholder for the user to fill in:

      # ---------------------------------------------------------------
      # REQUIRED: path(s) to your ECUC module definition arxml file(s).
      # AF.get_node() calls for set_definition() will fail without this.
      # ---------------------------------------------------------------
      ECUC_DEFS = ["path/to/your/ecuc_module_defs.arxml"]  # <-- UPDATE THIS
      _, ok = AF.read(files=ECUC_DEFS)
      if not ok:
          raise RuntimeError(f"Failed to load ECUC definitions: {{ECUC_DEFS}}")


{_kb_instruction}"""

# MCP server initialization
mcp = FastMCP("autosarfactory", instructions=_INSTRUCTIONS)
_db = _load_db()

# provided tools/apis

@mcp.tool()
def search_autosar_knowledge(query: str, top_k: int = 5) -> list:
    """
    Semantic search over AUTOSAR specification documents.
    Call this when you need authoritative AUTOSAR definitions, constraints, or
    element semantics — especially before making assumptions about rules or
    relationships not covered by get_class().
    Returns the top_k most relevant passages from the specification.
    Example: search_autosar_knowledge("ISignalTriggering constraints and rules", top_k=5)
    """
    if _kb is None:
        return [{
            "info": "Knowledge base not available.",
            "hint": "No *.pkl files found in autosarfactory_mcp/kb/. Run kb_builder/build_knowledge_base.py with AUTOSAR spec documents to enable this tool."
        }]

    import numpy as np
    query_vec = _kb_model.encode([query])
    scores    = np.dot(_kb["embeddings"], query_vec.T).flatten()
    top_idx   = np.argsort(scores)[::-1][:top_k]

    return [
        {"rank": int(i + 1), "score": round(float(scores[idx]), 4), "text": _kb["chunks"][idx]}
        for i, idx in enumerate(top_idx)
    ]

@mcp.tool()
def get_class(class_name: str, section: str = "all") -> dict:
    """
    Get available methods for an autosarfactory class.

    section: which method group to return — "references", "attributes", or "all" (default).
      Use "references" to find set_/add_ cross-reference methods and their target types.
      Use "attributes" to find set_ primitive methods and their value types.
      Use "all"        for a full class overview (children + references + attributes).
      NOTE: do NOT call with section="children" after find_creators_of() — the method
            and hasName returned by find_creators_of() are already sufficient to write the call.

    Response format:
      children   — list of {method, returns, hasName}   (new_ creators)
      references — dict  of {method: targetType}        (set_/add_ cross-references)
      attributes — dict  of {method: primitiveType}     (set_ primitives)
    """
    cls = _db["classes"].get(class_name)
    if not cls:
        similar = [k for k in _db["classes"] if class_name.lower() in k.lower()]
        return {"error": f"Class '{class_name}' not found.", "similar": similar[:5]}

    _SECTIONS = ("children", "references", "attributes")
    if section not in _SECTIONS and section != "all":
        return {"error": f"Invalid section '{section}'. Choose from: all, children, references, attributes."}

    result = {k: v for k, v in cls.items() if k not in _SECTIONS}
    for s in _SECTIONS:
        if section != "all" and section != s:
            continue
        methods = cls.get(s, [])
        if not _include_common_methods:
            methods = [m for m in methods if m["method"] not in _COMMON_METHODS]
        if s == "children":
            result[s] = methods                                      # list — 3 fields per entry
        else:
            result[s] = {m["method"]: m["type"] for m in methods}   # compact {method: type} dict
    return result

@mcp.tool()
def find_creators_of(class_name: str) -> list:
    """
    Find which autosarfactory classes have a new_X() method that creates the given class.
    Call this FIRST when you know what element you need but not where to create it.
    Example: find_creators_of('CanFrameTriggering') -> CanPhysicalChannel.new_CanFrameTriggering()

    The returned 'method' and 'hasName' are sufficient to write the call directly:
      hasName=True  -> parentObj.new_X('shortName')
      hasName=False -> parentObj.new_X()
    Do NOT follow up with get_class(section='children') — that would be redundant.
    """
    results = []
    for parent_name, cls in _db["classes"].items():
        for child in cls.get("children", []):
            if child["returns"] == class_name:
                results.append({
                    "parentClass":     parent_name,
                    "method":          child["method"],
                    "hasName":         child.get("hasShortName", True)
                })
    if not results:
        similar = [k for k in _db["classes"] if class_name.lower() in k.lower()]
        return [{"info": f"No creator found for '{class_name}'.",
                 "hints": [
                     "The class name may be misspelled — call search_classes(keyword) to find the correct name.",
                     "It may be a top-level element created only by AF.new_file() or AF.read() (e.g. ArPackage).",
                 ],
                 "similar_classes": similar[:5]}]
    return results

@mcp.tool()
def search_classes(keyword: str) -> list:
    """
    Find autosarfactory classes whose name contains the given keyword (case-insensitive).
    Example: search_classes('CAN') -> ['CanCluster', 'CanFrame', 'CanFrameTriggering', ...]
    """
    kw = keyword.lower()
    matches = [name for name in _db["classes"] if kw in name.lower()]
    return sorted(matches) if matches else [f"No classes found matching '{keyword}'"]

@mcp.tool()
def get_enum(enum_name: str) -> dict:
    """
    Get valid values for an autosarfactory enum class.
    Always call this before passing an enum value to a set_X() method.

    The returned values are Python attribute-access expressions that must be written
    into generated code WITHOUT surrounding quotes.

    WRONG:  obj.set_addressingMode("CanAddressingModeType.VALUE_STANDARD")  # string — will fail
    RIGHT:  obj.set_addressingMode(CanAddressingModeType.VALUE_STANDARD)     # expression — correct

    There is no need to import enum classes as you can instead use AF.CanAddressingModeType.VALUE_STANDARD
    """
    values = _db["enums"].get(enum_name)
    if values is None:
        similar = [k for k in _db["enums"] if enum_name.lower() in k.lower()]
        return {"error": f"Enum '{enum_name}' not found.", "similar": similar[:5]}
    return {
        "enum":   enum_name,
        "values": [f"{enum_name}.{v}" for v in values],
    }

@mcp.tool()
def list_enums() -> list:
    """List all available enum class names."""
    return sorted(_db["enums"].keys())


@mcp.tool()
def get_system_element_map(use_case: str = "") -> dict:
    """
    Return the AUTOSAR element hierarchy needed for a system model use case
    (SWC communication, CAN, Ethernet/SOME-IP, DEXT, data types, etc.).

    Do NOT call this for ECUC/BSW module configuration — use list_ecuc_modules() instead.

    Call with no argument (or use_case="") to list all available use case titles.
    Call with a keyword (e.g. "CAN", "DEXT", "Ethernet") to retrieve the matching
    section(s). Matching is case-insensitive substring search on the section title.

    When a use case builds on another (e.g. CAN builds on Sender-Receiver), all
    prerequisite sections are automatically included in the response.
    """
    if not _elem_map_sections:
        return {"error": "Element map not loaded — autosar_element_map.md not found."}

    if not use_case:
        return {"use_cases": list(_elem_map_sections.keys())}

    lc = use_case.lower()
    matches = [k for k in _elem_map_sections if lc in k.lower()]

    if not matches:
        return {
            "error": f"No use case matching '{use_case}' found.",
            "available": list(_elem_map_sections.keys()),
        }

    # Merge pre-resolved chains for all matches, preserving order and deduplicating
    seen: set[str] = set()
    ordered: list[str] = []
    for title in matches:
        for t in _elem_map_chain.get(title, [title]):
            if t not in seen:
                seen.add(t)
                ordered.append(t)

    sections = {t: _elem_map_sections[t] for t in ordered if t in _elem_map_sections}
    if len(sections) == 1:
        title, content = next(iter(sections.items()))
        return {"use_case": title, "content": content}
    return {"sections": sections}


@mcp.tool()
def list_ecuc_modules() -> list:
    """
    List all ECUC module names available in the loaded ecuc_param_def.json.
    Call this first to discover which BSW modules are defined.
    Returns an empty list if no ecuc_param_def.json was loaded.
    """
    return sorted(_ecuc_modules.keys())


@mcp.tool()
def get_ecuc_module(module_name: str) -> dict:
    """
    Get the top-level container, parameter, and reference names and their types for an ECUC module.
    Use this to understand the structure of a BSW module before creating containers.

    The 'type' field in each container maps directly to the autosarfactory class name,
    e.g. 'EcucParamConfContainerDef' -> use parent.new_EcucParamConfContainerDef('name').

    Args:
        module_name: Name of the BSW module, e.g. 'CanIf', 'Os', 'Rte'.
    """
    if not _ecuc_modules:
        return {"error": "No ECUC data loaded. Place ecuc_param_def.json in the db/ folder."}
    mod = _ecuc_modules.get(module_name)
    if mod is None:
        similar = [k for k in _ecuc_modules if module_name.lower() in k.lower()]
        return {"error": f"Module '{module_name}' not found.", "similar": similar[:8]}
    return {
        "module": module_name,
        "containers": [
            {"name": c["name"], "type": c["type"], "subContainers": [s["name"] for s in c.get("subContainers", [])]}
            for c in mod.get("containers", [])
        ],
    }

@mcp.tool()
def get_ecuc_container(container_name: str, module_name: str = "") -> list:
    """
    Look up an ECUC container by name and return its lean definition:
    type, parent, parameters and references (name/type/path/valueClass only),
    and direct sub-container names.

    Constraint fields (min, max, default, literals) are intentionally
    omitted to keep responses lean. For EcucEnumerationParamDef parameters, call
    get_ecuc_param_literals(paramName, containerName) to get the valid literal strings.

    Key fields in the response:
      'path'       — full AUTOSAR path to this container's definition,
                     e.g. '/AUTOSAR/EcucDefs/Os/OsTask'
                     Pass to AF.get_node(path) to get the def object, then
                     call valueObject.set_definition(defObject) to link them.
      'type'       — autosarfactory class for THIS container
                     e.g. 'EcucParamConfContainerDef'
      'parent'     — name of the parent container (or module name if top-level)
      'parentType' — autosarfactory class of the parent
                     e.g. 'EcucParamConfContainerDef' or 'EcucModuleDef'

    Usage pattern:
      1. Call get_class(parentType) to find the new_ method on the parent.
      2. Call parentObject.new_<type>('containerName') to create the container.
      3. For each parameter, 
         1. call container.new_<paramType>().
         2. set the definition using param.set_definition()
         3. ALWAYS, add mandatory parameter(multiplicity with )

    Example — creating an OsTask container value:
      entry = get_ecuc_container('OsTask', 'Os')[0]
      # entry['path']                         = '/AUTOSAR/EcucDefs/Os/OsTask'
      # entry['valueClass']                   = 'EcucContainerValue'
      # entry['parentValueClass']             = 'EcucContainerValue'
      # entry['parameters'][0]['valueClass']  = 'EcucNumericalParamValue'
      # entry['parameters'][0]['path']        = '/AUTOSAR/EcucDefs/Os/OsTask/OsTaskPriority'

      osTaskVal = osVal.new_EcucContainerValue('MyOsTask')
      osTaskVal.set_definition(AF.get_node('/AUTOSAR/EcucDefs/Os/OsTask'))

      prio = osTaskVal.new_EcucNumericalParamValue()
      prio.set_definition(AF.get_node('/AUTOSAR/EcucDefs/Os/OsTask/OsTaskPriority'))
      prio.new_Value().set(1)

    Args:
        container_name: Name of the container, e.g. 'OsTask', 'CanIfRxPduCfg'.
        module_name:    Optional module filter to narrow results when the same name
                        appears in multiple modules.
    """
    if not _ecuc_containers:
        return [{"error": "No ECUC data loaded. Place ecuc_param_def.json in the db/ folder."}]
    matches = _ecuc_containers.get(container_name)
    if not matches:
        kw = container_name.lower()
        similar = [k for k in _ecuc_containers if kw in k.lower()]
        return [{"error": f"Container '{container_name}' not found.", "similar": similar[:8]}]
    if module_name:
        filtered = [m for m in matches if m["module"] == module_name]
        if filtered:
            matches = filtered
    return [_trim_for_response(m) for m in matches]

@mcp.tool()
def get_ecuc_param_literals(param_path: str) -> dict:
    """
    Get the valid literal strings for an EcucEnumerationParamDef parameter.
    Call this ONLY when get_ecuc_container shows a parameter with type 'EcucEnumerationParamDef'.
    NOT needed for integer, float, boolean, string, or reference parameters.

    The returned literals are the exact strings to pass to param.set_value("LITERAL").

    Args:
        param_path: The 'path' field of the parameter from get_ecuc_container(),
                    e.g. '/AUTOSAR/EcucDefs/Os/OsTask/OsStackMonitoring'.
    """
    if not _ecuc_enum_literals:
        return {"error": "No ECUC data loaded."}
    literals = _ecuc_enum_literals.get(param_path)
    if literals is None:
        return {
            "error": f"No enum literals found for path '{param_path}'.",
            "hint": "Only call this tool for parameters with type 'EcucEnumerationParamDef'."
        }
    return {"path": param_path, "literals": literals}


@mcp.tool()
def new_file_script_template(ar_package_name: str, output_arxml: str) -> str:
    """
    Return the mandatory boilerplate for a creating a new arxml file using 
    autosarfactory Python script.
    Call this FIRST before writing any modelling code.

    Args:
        ar_package_name: Name of the root ArPackage (e.g. 'MyPackage').
        output_arxml:    Desired output arxml filename (e.g. 'output.arxml').

    Returns a Python code string with the correct imports, factory initialisation,
    new_file() call, and save() call.  Fill in the modelling code between the
    new_file() and save() lines.

    new_file(ar_package_name) -> ArPackage
      Creates a new arxml file and returns the root ArPackage.
      For each element you need to create, call find_creators_of(elementType) to
      discover which parent class and method to use — do NOT browse ArPackage directly.

    After building the complete script, write it to a .py file using your own file-writing tool.
    """
    return (
        "from autosarfactory import autosarfactory as AF\n"
        "# For enum class you use the enum types directly as shown below :\n"
        "#   AF.CanAddressingModeType, AF.ByteOrderEnum\n"
        "# Then use as bare expressions (NO quotes): AF.CanAddressingModeType.VALUE_STANDARD\n"
        "\n"
        f"arPkg = AF.new_file(path= '{output_arxml}', defaultArPackage='{ar_package_name}', overWrite=True)  # returns ArPackage\n"
        "\n"
        "# --- modelling code goes here ---\n"
        "# For each element to create: call find_creators_of(elementType) -> get_class(parentType) -> call the method.\n"
        "\n"
        f"AF.save()\n"
    )

@mcp.tool()
def read_file_script_template(input_arxmls: list[str]) -> str:
    """
    Return the mandatory boilerplate for reading an arxml file
    with autosarfactory Python script.
    Call this FIRST before writing any modelling code.

    Args:
        input_arxmls:    List of input arxml files or list of folders containing arxml files

    Returns a Python code string with the correct imports, factory initialisation,
    read() call, and save() call.  Fill in the modelling code between the
    read() and save() lines.

    - read(input_arxmls) -> AUTOSAR
      Reads the arxml files and returns the tuple[AUTOSAR, bool] of the root AUTOSAR node
      and status of if the file read was successful. So, better to put a check if the file
      read failed.
    - use get_node('/some/path/to/element') to get the element if user specified 
      an Autosar arxml path(backward slash separated path) to be read where elements 
      needs to be added. Check if the returned element is not None
    - If a user passes a type of an element to be retrieved under a parent node, 
      use get_all_instances(AutosarNode, ElementType) to get all the instances of an 
      element of a specific type(eg: ApplicationSwComponentType) under the parent 
      AutosarNode(eg: ArPackage or ApplicationSwComponentType). This returns a list of elements.
    - If a user passes a name of an element to be retrieved under a parent node, 
      use get_all_instances(AutosarNode, ElementType) to get all the instances of an 
      element of a specific type(eg: ApplicationSwComponentType) under the parent 
      AutosarNode(eg: ArPackage or ApplicationSwComponentType). This returns a list of elements
      and you can get the right element by filtering the list by comparing the name. eg: element.name == userPassedName.

    After building the complete script, write it to a .py file using your own file-writing tool.
    """
    return (
        "from autosarfactory import autosarfactory as AF\n"
        "# For enum class you use the enum types directly as shown below :\n"
        "#   AF.CanAddressingModeType, AF.ByteOrderEnum\n"
        "# Then use as bare expressions (NO quotes): AF.CanAddressingModeType.VALUE_STANDARD\n"
        "\n"
        f"root, status = AF.read(files={input_arxmls})  # returns AUTOSAR root\n"
        "\n"
        "if status is False:\n"
        "    return some error\n"
        "# --- modelling code goes here for using get_node ---\n"
        "ApplicationSwComponentType = AF.get_node('/some/path/to/ApplicationSwComponentType')\n"
        "# For each element you need to create: call find_creators_of(elementType) to discover\n"
        "# the right parent method, then call get_class(parentType) to confirm the exact signature.\n"
        "# --- modelling code goes here for using get_all_instances ---\n"
        "swComponentTypes = AF.get_all_instances(root, AF.ApplicationSwComponentType)\n"
        "for swc in swComponentTypes:\n"
        "    if swc.name == 'name':\n"
        "        # For each element you need to add: call find_creators_of(elementType) first.\n"
        "\n"
        f"AF.save()\n"
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--include-common-methods", action="store_true", default=False,
        help=(
            "Include arxml infrastructure related base-class methods (set_timestamp, set_checksum, "
            "new_AdminData, new_Desc, new_Introduction, new_LongName, "
            "new_ShortNameFragment, new_Annotation) in get_class() responses. "
            "Disabled by default to keep responses lean."
        ),
    )
    args = parser.parse_args()

    _include_common_methods = args.include_common_methods

    if args.transport != "stdio":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)
