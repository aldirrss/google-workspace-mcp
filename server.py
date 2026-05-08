#!/usr/bin/env python3
"""
google-workspace-mcp — MCP server for Google Sheets, Docs, and Slides.

Supports two transports:
  stdio              (default) — for Claude Desktop / Claude Code local usage
  streamable_http    — for Docker / remote multi-client deployment

Usage:
  python server.py                          # stdio
  python server.py --transport http         # HTTP on :8080
  python server.py --transport http --port 9000
"""

import argparse
import logging
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import config
from auth import build_clients, build_credentials
from tools import (
    register_docs_atomic_tools,
    register_sheets_atomic_tools,
    register_sheets_workflow_tools,
    register_slides_atomic_tools,
)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
_logger = logging.getLogger("google-workspace-mcp")


# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "google_workspace_mcp",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"],
    ),
    instructions=(
        "Google Workspace MCP — interact with Google Sheets, Docs, and Slides "
        "via Service Account authentication. All tools are prefixed with 'gws_'.\n\n"
        "Sheets tools: gws_sheets_* (full CRUD + formatting + workflow)\n"
        "Docs tools:   gws_docs_*   (basic CRUD)\n"
        "Slides tools: gws_slides_* (basic CRUD)\n\n"
        "Use gws_sheets_list / gws_docs_list / gws_slides_list to discover accessible files."
    ),
)


# ---------------------------------------------------------------------------
# Build API clients and register tools once at module load
# ---------------------------------------------------------------------------

_logger.info("Initializing Google API clients...")
_credentials = build_credentials()
_clients     = build_clients(_credentials)
_logger.info("Google API clients ready.")

register_sheets_atomic_tools(mcp, _clients)
register_sheets_workflow_tools(mcp, _clients)
register_docs_atomic_tools(mcp, _clients)
register_slides_atomic_tools(mcp, _clients)

_logger.info("All tools registered.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google Workspace MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python server.py                        # stdio (Claude Desktop/Code)\n"
            "  python server.py --transport http       # HTTP on :8080\n"
            "  python server.py --transport http --port 9000\n"
        ),
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mechanism (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.SERVER_PORT,
        help=f"HTTP port (default: {config.SERVER_PORT}, only used with --transport http)",
    )
    parser.add_argument(
        "--host",
        default=config.SERVER_HOST,
        help=f"HTTP host (default: {config.SERVER_HOST})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.transport == "http":
        _logger.info("Starting HTTP transport on %s:%d", args.host, args.port)
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        _logger.info("Starting stdio transport")
        mcp.run()
