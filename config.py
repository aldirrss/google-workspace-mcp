"""
Configuration and environment variables for google-workspace-mcp.
"""

import json
import os
from pathlib import Path


def _load_service_account() -> dict:
    """Load service account credentials from env or file path."""
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        return json.loads(raw_json)

    file_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if file_path:
        return json.loads(Path(file_path).read_text())

    raise ValueError(
        "Google Service Account credentials not found. "
        "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE."
    )


GOOGLE_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

SERVICE_ACCOUNT_INFO: dict = _load_service_account()

SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8080"))
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
