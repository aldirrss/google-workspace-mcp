"""
Configuration and environment variables for google-workspace-mcp.
"""

import os

# OAuth2 client secret (Web Application type from Google Cloud Console)
GOOGLE_OAUTH_CLIENT_SECRET_JSON: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON", "")
GOOGLE_OAUTH_CLIENT_SECRET_FILE: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", "")

# Public base URL of this server.
# Used to build OAuth2 redirect URIs — must match what is registered in Google Cloud Console.
# Example: https://gcp.lemacore.com
SERVER_BASE_URL: str = os.getenv("SERVER_BASE_URL", "http://localhost:8347")

SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8347"))
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
LOG_LEVEL: str   = os.getenv("LOG_LEVEL", "INFO")
