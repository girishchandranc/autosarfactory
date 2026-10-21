"""
Offline CLI for the autosarfactory MCP server: call any MCP tool or render any
MCP prompt in-process, without an MCP client or a working `mcp` installation.

    python -m autosarfactory_mcp.cli <tool> ['<json kwargs>']
    python -m autosarfactory_mcp.cli validate_plan '{"plan": "plan.json", "fix": true}'
    python -m autosarfactory_mcp.cli prompt autosar-plan '{"request": "two SWCs over SR"}'
    python -m autosarfactory_mcp.cli list

Run with PYTHONPATH=./mcp_server from the repo root (the same setup as the server).
Prints JSON (prompt text is printed as-is). Library use:

    from autosarfactory_mcp.cli import load_server
    srv = load_server()
    srv.validate_plan("plan.json")
"""

import contextlib
import inspect
import io
import json
import sys
import types


class _StubFastMCP:
    """Stands in for FastMCP: @mcp.tool() / @mcp.prompt() record the plain function and return it."""

    def __init__(self, *args, **kwargs):
        self.settings = types.SimpleNamespace()
        self.tools, self.prompts = {}, {}

    def tool(self, *args, **kwargs):
        def deco(fn):
            self.tools[kwargs.get("name") or fn.__name__] = fn
            return fn
        return deco

    def prompt(self, *args, **kwargs):
        def deco(fn):
            self.prompts[kwargs.get("name") or fn.__name__] = fn
            return fn
        return deco

    def run(self, *args, **kwargs):
        raise RuntimeError("offline CLI cannot run a server - use `python -m autosarfactory_mcp.server`")


_server = None


def load_server():
    """Import server.py with FastMCP stubbed; every tool/prompt is then a plain callable."""
    global _server
    if _server is not None:
        return _server
    if "autosarfactory_mcp.server" in sys.modules:  # already imported for real (e.g. inside the server)
        _server = sys.modules["autosarfactory_mcp.server"]
        return _server
    stub = types.ModuleType("mcp.server.fastmcp")
    stub.FastMCP = _StubFastMCP
    saved = {k: sys.modules.get(k) for k in ("mcp", "mcp.server", "mcp.server.fastmcp")}
    sys.modules.setdefault("mcp", types.ModuleType("mcp"))
    sys.modules.setdefault("mcp.server", types.ModuleType("mcp.server"))
    sys.modules["mcp.server.fastmcp"] = stub
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            from autosarfactory_mcp import server
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    _server = server
    return server


def _signature(fn) -> str:
    return f"{fn.__name__}{inspect.signature(fn)}"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1
    srv = load_server()
    mcp = srv.mcp
    sys.stdout.reconfigure(encoding="utf-8")

    if argv[0] == "list":
        print(json.dumps({"tools": {n: _signature(f) for n, f in sorted(mcp.tools.items())},
                          "prompts": {n: _signature(f) for n, f in sorted(mcp.prompts.items())}}, indent=1))
        return 0

    if argv[0] == "prompt":
        if len(argv) < 2 or argv[1] not in mcp.prompts:
            print(f"Unknown prompt; available: {sorted(mcp.prompts)}", file=sys.stderr)
            return 2
        kwargs = json.loads(argv[2]) if len(argv) > 2 else {}
        print(mcp.prompts[argv[1]](**kwargs))
        return 0

    name = argv[0]
    if name not in mcp.tools:
        print(f"Unknown tool '{name}'; run `list` to see the available tools", file=sys.stderr)
        return 2
    kwargs = json.loads(argv[1]) if len(argv) > 1 else {}
    print(json.dumps(mcp.tools[name](**kwargs), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
