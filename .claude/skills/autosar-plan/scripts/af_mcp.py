"""
Direct, token-free access to the autosarfactory MCP server's tools from the CLI.

Imports mcp_server/autosarfactory_mcp/server.py with FastMCP stubbed out, so every
MCP tool (including the plan/generate workflow tools) runs in-process - no MCP
round trip, and no dependency on the `mcp` package being importable.

Library use:
    from af_mcp import srv, dump
    srv.validate_plan("plan.json", fix=True)

CLI use (prints JSON):
    python af_mcp.py <tool_name> [json_kwargs]
    python af_mcp.py find_creation_chain '{"class_name": "ISignalTriggering"}'
    python af_mcp.py connectivity
"""

import contextlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import types

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
MCP_SERVER_DIR = REPO_ROOT / "mcp_server"


class _StubFastMCP:
    """Stands in for FastMCP: @mcp.tool() / @mcp.prompt() return the plain function unchanged."""

    def __init__(self, *args, **kwargs):
        self.settings = types.SimpleNamespace()

    def tool(self, *args, **kwargs):
        return lambda fn: fn

    def prompt(self, *args, **kwargs):
        return lambda fn: fn

    def run(self, *args, **kwargs):
        raise RuntimeError("af_mcp stub cannot run a server")


def _load_server():
    stub = types.ModuleType("mcp.server.fastmcp")
    stub.FastMCP = _StubFastMCP
    saved = {k: sys.modules.get(k) for k in ("mcp", "mcp.server", "mcp.server.fastmcp")}
    sys.modules.setdefault("mcp", types.ModuleType("mcp"))
    sys.modules.setdefault("mcp.server", types.ModuleType("mcp.server"))
    sys.modules["mcp.server.fastmcp"] = stub
    sys.path.insert(0, str(MCP_SERVER_DIR))
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            from autosarfactory_mcp import server
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return server


srv = _load_server()


def mcp_cli_registration() -> str:
    """Best-effort check whether the autosarfactory server is registered with Claude Code."""
    claude = shutil.which("claude")
    if not claude:
        return "unknown (claude CLI not on PATH)"
    try:
        out = subprocess.run([claude, "mcp", "list"], capture_output=True, text=True,
                             timeout=20, cwd=REPO_ROOT).stdout
    except Exception as exc:  # noqa: BLE001 - diagnostic only
        return f"unknown ({exc.__class__.__name__})"
    for line in out.splitlines():
        if "autosarfactory" in line.lower():
            return "connected" if ("connected" in line.lower() or "✓" in line) else f"registered ({line.strip()})"
    return "not registered"


def connectivity(check_cli: bool = False) -> dict:
    """The server's data-source status plus CLI-side MCP checks."""
    from autosarfactory_mcp.workflow.af_api import connectivity as data_status
    info = data_status()
    try:
        import mcp.server.fastmcp  # noqa: F401
        info["mcp_package_importable"] = True
    except Exception as exc:  # noqa: BLE001
        info["mcp_package_importable"] = f"import failed: {exc.__class__.__name__}"
    info["source"] = "in-process import of mcp_server/autosarfactory_mcp/server.py (same data as the MCP server)"
    if check_cli:
        info["claude_mcp_registration"] = mcp_cli_registration()
    return info


def dump(obj) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    name = sys.argv[1]
    kwargs = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    if name == "connectivity":
        dump(connectivity(check_cli=kwargs.get("check_cli", True)))
    elif callable(getattr(srv, name, None)) and not name.startswith("_"):
        dump(getattr(srv, name)(**kwargs))
    else:
        print(f"Unknown tool '{name}'", file=sys.stderr)
        sys.exit(2)
