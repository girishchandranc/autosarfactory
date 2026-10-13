"""
Planner / generator workflow for autosarfactory (backs the autosar-plan and
autosar-generate MCP prompts and the matching Claude Code skills).

The modules here reuse the data already loaded by server.py. server.py calls
bind() on itself at import time; standalone users import the server first.
"""

_server = None


def bind(server_module) -> None:
    global _server
    _server = server_module


def srv():
    if _server is None:
        raise RuntimeError("autosarfactory_mcp.workflow is not bound - import autosarfactory_mcp.server first")
    return _server
