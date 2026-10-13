"""
CLI for the MCP tool gather_modelling_context: all API context for a plan in one call.

System model:
    python gather_context.py system --use-case "Sender-Receiver" \
        --elements SenderReceiverInterface,VariableDataPrototype [--enums ByteOrderEnum]
ECUC:
    python gather_context.py ecuc --modules Os [--containers OsTask,OsAlarm] [--depth 1]

--check-cli additionally reports whether the MCP server is registered with Claude Code.
"""

import argparse

from af_mcp import connectivity, dump, srv


def _csv(s: str) -> list:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("type", choices=["system", "ecuc"])
    ap.add_argument("--use-case", action="append", default=[], help="element map use case keyword (repeatable)")
    ap.add_argument("--elements", default="", help="comma separated autosarfactory class names")
    ap.add_argument("--enums", default="", help="comma separated enum names")
    ap.add_argument("--modules", default="", help="comma separated ECUC module names")
    ap.add_argument("--containers", default="", help="comma separated ECUC container names")
    ap.add_argument("--depth", type=int, default=1, help="ECUC sub-container expansion depth")
    ap.add_argument("--check-cli", action="store_true", help="also run `claude mcp list` (slower)")
    a = ap.parse_args()
    result = srv.gather_modelling_context(a.type, a.use_case, _csv(a.elements), _csv(a.enums),
                                          _csv(a.modules), _csv(a.containers), a.depth)
    result["mcp_connectivity"] = connectivity(check_cli=a.check_cli)
    dump(result)
