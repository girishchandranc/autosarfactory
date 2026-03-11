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

_DB_PATH       = pathlib.Path(__file__).parent / "db/api_reference.json"
_KB_DIR        = pathlib.Path(__file__).parent / "kb"
_ELEM_MAP_PATH = pathlib.Path(__file__).parent / "ar_map/autosar_element_map.md"

def _load_db() -> dict:
    """
    Load the json database of the autosarfactory apis.
    Normalizes list-of-single-key-dicts format into plain dicts for fast lookup.
    """
    if not _DB_PATH.exists():
        raise FileNotFoundError(
            f"api_reference.json not found at {_DB_PATH}. "
            "Please check the github repo or get in touch with the owner of autosarfactory to provide it."
        )
    db = json.loads(_DB_PATH.read_text(encoding="utf-8"))
    # api_reference.json stores classes/enums as lists of single-key dicts;
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

_elem_map = ""
if _ELEM_MAP_PATH.exists():
    _elem_map = _ELEM_MAP_PATH.read_text(encoding="utf-8")
else:
    print(f"[autosarfactory-mcp] Warning: {_ELEM_MAP_PATH.name} not found — element map omitted.", file=sys.stderr)

_INSTRUCTIONS = f"""
You are an AUTOSAR modelling expert working with autosarfactory, a Python
library for creating AUTOSAR .arxml files.

## Mandatory workflow for using the autosarfactory APIs

1. Identify which AUTOSAR elements are needed using the domain knowledge below
2. Call search_autosar_knowledge(query) if you need specification details or constraints
3. Call list_classes() for an overview if unsure what the library supports
4. Call get_class(className) before using any new_/set_/add_ method on a class
5. Call find_creators_of(className) to find where in the hierarchy to create an element
6. Call get_enum(enumName) before passing any enum value to a set_ method
7. DO NOT create elements with same shortName under a parent node
8. Always put elements of same type under different ARPackage
9. If 2 elements of same type happen to have same shortName under a parent,
ALWAYS use some suffix to differentiate
10. NEVER ASSUME the api name yourself. Always use the method as returned to you
from autosarfactory mcp
11. Write the script only after confirming all API calls via these tools

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

# Rules for mapping Autosar elements
{_elem_map}
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
def get_class(class_name: str) -> dict:
    """
    Get all available methods for an autosarfactory class.
    Returns children (new_), references (set_/add_ for cross-references), and attributes (set_ for primitives).
    Always call this before using any new_/set_/add_ method.
    """
    cls = _db["classes"].get(class_name)
    if not cls:
        similar = [k for k in _db["classes"] if class_name.lower() in k.lower()]
        return {"error": f"Class '{class_name}' not found.", "similar": similar[:5]}
    return cls

@mcp.tool()
def find_creators_of(class_name: str) -> list:
    """
    Find which autosarfactory classes have a new_X() method that creates the given class.
    Call this FIRST when you know what element you need but not where to create it.
    Example: find_creators_of('CanFrameTriggering') -> CanPhysicalChannel.new_CanFrameTriggering()
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
        return [{"info": f"No creator found for '{class_name}'. The provided class name could be wrong or it may be a top-level package element."}]
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
def new_file_script_template(ar_package_name: str, output_arxml: str) -> str:
    """
    Return the mandatory boilerplate for a creating a new arxml file using 
    autosarfactory Python script.
    Call this FIRST before writing any modelling code.

    Args:
        ar_package_name: Name of the root ArPackage (e.g. 'MyPackage').
        output_arxml:    Desired output arxml filename (e.g. 'output.arxml').

    Returns a Python code string with the correct imports, factory initialisation,
    new_file() call, and save() call.  The agent should fill in the modelling code
    between the new_file() and save() lines, then write the result with create_file().

    new_file(ar_package_name) -> ArPackage
      Creates a new arxml file and returns the root ArPackage.
      Use get_class('ArPackage') to discover what can be created inside it.
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
        "# Use arPkg.new_X() / arPkg.set_X() / arPkg.add_X() to build the model.\n"
        "# Call get_class('ArPackage') to see all available methods.\n"
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
    read() call, and save() call.  The agent should fill in the modelling code
    between the read() and save() lines, then write the result with create_file().

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
        "ApplicationSwComponentType = AF.get_node(/some/path/to/ApplicationSwComponentType)\n"
        "# Use ApplicationSwComponentType.new_X() / ApplicationSwComponentType.set_X() / ApplicationSwComponentType.add_X() to build the model.\n"
        "# Call get_class('ApplicationSwComponentType') to see all available methods.\n"
        "# --- modelling code goes here for using get_all_instances ---\n"
        "swComponentTypes = AF.get_all_instances(root, AF.ApplicationSwComponentType)\n"
        "for swc in swComponentTypes:\n"
        "    if swc.name == 'name':\n"
        "        # Use ApplicationSwComponentType.new_X() / ApplicationSwComponentType.set_X() / ApplicationSwComponentType.add_X() to build the model.\n"
        "        # Call get_class('ApplicationSwComponentType') to see all available methods.\n"
        "\n"
        f"AF.save()\n"
    )

@mcp.tool()
def create_file(path: str, content: str, overwrite: bool = False) -> dict:
    """
    Write a Python script (or any text file) to the local filesystem.
    Use this to save the generated autosarfactory script once you have finished
    building and verifying it with get_class / find_creators_of.

    Args:
        path:      Absolute or workspace-relative file path (e.g. 'Examples/my_model.py').
        content:   Full text content to write.
        overwrite: If False (default), returns an error when the file already exists.

    Returns a dict with 'status' ('ok' or 'error') and a 'message'.
    """
    target = pathlib.Path(path)
    if not target.is_absolute():
        target = pathlib.Path.cwd() / target
    if target.exists() and not overwrite:
        return {
            "status":  "error",
            "message": f"File already exists: {target}. Pass overwrite=True to replace it."
        }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"status": "ok", "message": f"File written: {target}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    if args.transport != "stdio":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)
