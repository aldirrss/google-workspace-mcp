"""
OAuth2 user authentication for google-workspace-mcp.

Replaces Service Account with personal Google account OAuth2 flow.
Token is stored on disk and refreshed automatically.
"""

import json
import logging
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

_logger = logging.getLogger(__name__)

SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]


def load_credentials(token_path: str) -> Credentials | None:
    """Load and auto-refresh credentials from a stored token file."""
    p = Path(token_path)
    if not p.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds.expired and creds.refresh_token:
            _logger.info("Refreshing expired OAuth2 token...")
            creds.refresh(Request())
            p.write_text(creds.to_json())
            _logger.info("Token refreshed and saved.")
        return creds if creds.valid else None
    except Exception as e:
        _logger.warning("Failed to load credentials from %s: %s", token_path, e)
        return None


def save_credentials(creds: Credentials, token_path: str) -> None:
    Path(token_path).write_text(creds.to_json())
    _logger.info("OAuth2 token saved to %s", token_path)


def get_client_config(json_str: str = "", file_path: str = "") -> dict[str, Any]:
    """Load OAuth2 client secret from env string or file path."""
    if json_str:
        # Strip surrounding whitespace and accidental shell quotes that docker-compose
        # may include when the .env value is wrapped in single or double quotes.
        cleaned = json_str.strip().strip("'\"")
        if not cleaned:
            raise ValueError(
                "GOOGLE_OAUTH_CLIENT_SECRET_JSON is set but empty after stripping. "
                "Paste the full client_secret.json content without surrounding quotes."
            )
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"GOOGLE_OAUTH_CLIENT_SECRET_JSON is not valid JSON: {exc}. "
                "Make sure you pasted the full content of client_secret.json "
                "without surrounding shell quotes."
            ) from exc
    if file_path:
        content = Path(file_path).read_text().strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"client_secret.json at {file_path!r} is not valid JSON: {exc}"
            ) from exc
    raise ValueError(
        "OAuth2 client secret not configured. "
        "Set GOOGLE_OAUTH_CLIENT_SECRET_JSON or GOOGLE_OAUTH_CLIENT_SECRET_FILE."
    )


def build_flow(client_config: dict[str, Any], redirect_uri: str) -> Flow:
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def build_clients(credentials: Credentials) -> dict[str, Any]:
    return {
        "sheets": build("sheets", "v4", credentials=credentials),
        "docs":   build("docs", "v1", credentials=credentials),
        "slides": build("slides", "v1", credentials=credentials),
        "drive":  build("drive", "v3", credentials=credentials),
    }
