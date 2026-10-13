"""
CLI for the MCP tool detect_request_type: classify a modelling request as
ecuc / system / mixed / unknown.

Usage:
    python detect_request_type.py "Configure CanIf with two Rx PDUs ..."
"""

import sys

from af_mcp import dump, srv

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    dump(srv.detect_request_type(" ".join(sys.argv[1:])))
