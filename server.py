#!/usr/bin/env python3
"""
google-workspace-mcp — MCP server for Google Sheets, Docs, and Slides.

Supports two transports:
  stdio              (default) — for Claude Desktop / Claude Code local usage
  streamable_http    — for Docker / remote multi-client deployment (OAuth2 multi-user)

Usage:
  python server.py                          # stdio
  python server.py --transport http         # HTTP on :8347
"""

import argparse
import logging
import sys

import uvicorn
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Mount, Route

import config
from auth.mcp_provider import GoogleOAuthProvider
from auth.oauth2 import get_client_config
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
# OAuth2 provider (multi-user, delegates identity to Google)
# ---------------------------------------------------------------------------

def _load_client_config() -> dict:
    return get_client_config(
        json_str=config.GOOGLE_OAUTH_CLIENT_SECRET_JSON,
        file_path=config.GOOGLE_OAUTH_CLIENT_SECRET_FILE,
    )


_provider = GoogleOAuthProvider(
    client_config=_load_client_config(),
    base_url=config.SERVER_BASE_URL,
)


# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "google_workspace_mcp",
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(config.SERVER_BASE_URL),
        resource_server_url=AnyHttpUrl(config.SERVER_BASE_URL),
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["gws"],
            default_scopes=["gws"],
        ),
    ),
    auth_server_provider=_provider,
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

register_sheets_atomic_tools(mcp)
register_sheets_workflow_tools(mcp)
register_docs_atomic_tools(mcp)
register_slides_atomic_tools(mcp)
_logger.info("All tools registered.")


# ---------------------------------------------------------------------------
# Google OAuth2 callback endpoint (outside the MCP auth flow)
# ---------------------------------------------------------------------------

async def google_callback(request: Request) -> RedirectResponse | HTMLResponse:
    """Google redirects here after the user approves permissions."""
    error = request.query_params.get("error")
    if error:
        return HTMLResponse(
            f"<html><body><h1>Google Authorization Failed</h1><p>{error}</p></body></html>",
            status_code=400,
        )

    code  = request.query_params.get("code", "")
    state = request.query_params.get("state", "")

    try:
        redirect_url = await _provider.handle_google_callback(code=code, state=state)
        return RedirectResponse(redirect_url)
    except Exception as e:
        _logger.error("Google callback error: %s", e)
        return HTMLResponse(
            f"<html><body><h1>Authorization Error</h1><p>{e}</p></body></html>",
            status_code=500,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Workspace MCP Server")
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

        mcp_app = mcp.streamable_http_app()
        app = Starlette(routes=[
            Route("/google/callback", google_callback),
            Mount("/", app=mcp_app),
        ])

        uvicorn.run(app, host=args.host, port=args.port)
    else:
        _logger.info("Starting stdio transport")
        mcp.run()
