"""
Google Service Account authentication client.

Provides a single shared Credentials object and lazy-initialized API clients
for Sheets, Docs, Slides, and Drive — reused across all tools via lifespan.
"""

from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

import config


def build_credentials() -> service_account.Credentials:
    """Create scoped Service Account credentials."""
    return service_account.Credentials.from_service_account_info(
        config.SERVICE_ACCOUNT_INFO,
        scopes=config.GOOGLE_SCOPES,
    )


def build_clients(credentials: service_account.Credentials) -> dict[str, Any]:
    """
    Build all Google API clients from a single credentials object.
    Returns a dict keyed by service name for easy access in tools.
    """
    return {
        "sheets": build("sheets", "v4", credentials=credentials),
        "docs":   build("docs",   "v1", credentials=credentials),
        "slides": build("slides", "v1", credentials=credentials),
        "drive":  build("drive",  "v3", credentials=credentials),
    }
