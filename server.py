#!/usr/bin/env python3
"""
google-workspace-mcp — MCP server for Google Sheets, Docs, and Slides.

Supports two transports:
  stdio              (default) — for Claude Desktop / Claude Code local usage
  streamable_http    — for Docker / remote multi-client deployment

Usage:
  python server.py                          # stdio
  python server.py --transport http         # HTTP on :8347
  python server.py --transport http --port 9000
"""

import argparse
import logging
import sys

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Mount, Route

import config
from auth.oauth2 import build_clients, build_flow, get_client_config, load_credentials, save_credentials
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
        "via your Google account. All tools are prefixed with 'gws_'.\n\n"
        "Sheets tools: gws_sheets_* (full CRUD + formatting + workflow)\n"
        "Docs tools:   gws_docs_*   (basic CRUD)\n"
        "Slides tools: gws_slides_* (basic CRUD)\n\n"
        "Use gws_sheets_list / gws_docs_list / gws_slides_list to discover files."
    ),
)


# ---------------------------------------------------------------------------
# Shared mutable clients dict — updated in-place after OAuth authorization
# ---------------------------------------------------------------------------

_clients: dict = {}


def _reload_clients() -> bool:
    creds = load_credentials(config.GOOGLE_TOKEN_FILE)
    if creds:
        new = build_clients(creds)
        _clients.clear()
        _clients.update(new)
        return True
    return False


if _reload_clients():
    _logger.info("OAuth2 credentials loaded successfully.")
else:
    _logger.warning(
        "No OAuth2 credentials found. "
        "Visit %s/auth/setup to authorize.",
        config.SERVER_BASE_URL,
    )

register_sheets_atomic_tools(mcp, _clients)
register_sheets_workflow_tools(mcp, _clients)
register_docs_atomic_tools(mcp, _clients)
register_slides_atomic_tools(mcp, _clients)
_logger.info("All tools registered.")


# ---------------------------------------------------------------------------
# OAuth2 auth endpoints
# ---------------------------------------------------------------------------

_pending_flows: dict = {}  # {state: Flow}


def _get_oauth_client_config() -> dict:
    return get_client_config(
        json_str=config.GOOGLE_OAUTH_CLIENT_SECRET_JSON,
        file_path=config.GOOGLE_OAUTH_CLIENT_SECRET_FILE,
    )


async def auth_status(request: Request) -> HTMLResponse:
    if _clients:
        return HTMLResponse(
            "<html><head><title>Auth Status</title></head><body>"
            "<h1>&#x2705; Authorized</h1>"
            "<p>Google Workspace MCP is connected to your Google account.</p>"
            "</body></html>"
        )
    return HTMLResponse(
        "<html><head><title>Auth Status</title></head><body>"
        "<h1>&#x26A0;&#xFE0F; Not Authorized</h1>"
        "<p>Google Workspace MCP is not connected yet.</p>"
        '<p><a href="/auth/setup"><strong>Click here to authorize</strong></a></p>'
        "</body></html>"
    )


async def auth_setup(request: Request) -> RedirectResponse | HTMLResponse:
    try:
        client_config = _get_oauth_client_config()
    except ValueError as e:
        return HTMLResponse(
            f"<html><body><h1>Configuration Error</h1><p>{e}</p></body></html>",
            status_code=500,
        )

    redirect_uri = f"{config.SERVER_BASE_URL}/auth/callback"
    flow = build_flow(client_config, redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    _pending_flows[state] = flow
    return RedirectResponse(auth_url)


async def auth_callback(request: Request) -> HTMLResponse:
    error = request.query_params.get("error")
    if error:
        return HTMLResponse(
            f"<html><body><h1>Authorization Failed</h1><p>{error}</p></body></html>",
            status_code=400,
        )

    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    flow  = _pending_flows.pop(state, None)

    if not flow:
        return HTMLResponse(
            "<html><body><h1>Invalid or Expired Session</h1>"
            '<p><a href="/auth/setup">Try again</a></p></body></html>',
            status_code=400,
        )

    try:
        flow.fetch_token(code=code)
        save_credentials(flow.credentials, config.GOOGLE_TOKEN_FILE)

        new = build_clients(flow.credentials)
        _clients.clear()
        _clients.update(new)
        _logger.info("OAuth2 authorization successful. All tools are now active.")

        return HTMLResponse(
            "<html><head><title>Authorized</title></head><body>"
            "<h1>&#x2705; Authorization Successful!</h1>"
            "<p>Google Workspace MCP is now connected to your Google account.</p>"
            "<p>You can close this tab. All tools (gws_*) are now active.</p>"
            "</body></html>"
        )
    except Exception as e:
        _logger.error("OAuth2 callback error: %s", e)
        return HTMLResponse(
            f"<html><body><h1>Authorization Error</h1><p>{e}</p></body></html>",
            status_code=500,
        )


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
            "  python server.py --transport http       # HTTP on :8347\n"
            "  python server.py --transport http --port 9000\n"
        ),
    )
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=config.SERVER_PORT)
    parser.add_argument("--host", default=config.SERVER_HOST)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.transport == "http":
        _logger.info("Starting HTTP transport on %s:%d", args.host, args.port)
        mcp.settings.host = args.host
        mcp.settings.port = args.port

        # Merge auth routes with the MCP Starlette app
        mcp_app = mcp.streamable_http_app()
        app = Starlette(routes=[
            Route("/auth/status",   auth_status),
            Route("/auth/setup",    auth_setup),
            Route("/auth/callback", auth_callback),
            Mount("/", app=mcp_app),
        ])

        uvicorn.run(app, host=args.host, port=args.port)
    else:
        _logger.info("Starting stdio transport")
        mcp.run()
