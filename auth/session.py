"""
Per-user Google API client session store.

Tools call get_current_clients() to get the API clients for the currently
authenticated user. The MCP auth middleware populates the contextvar with the
access token before each tool call, allowing us to look up the user's clients.
"""

from mcp.server.auth.middleware.auth_context import get_access_token

_user_clients: dict[str, dict] = {}


def get_current_clients() -> dict:
    """Return Google API clients for the currently authenticated user, or {} if not authenticated."""
    token = get_access_token()
    if token is None:
        return {}
    user_id = getattr(token, "user_id", None) or token.client_id
    return _user_clients.get(user_id, {})


def set_user_clients(user_id: str, clients: dict) -> None:
    _user_clients[user_id] = clients


def remove_user_clients(user_id: str) -> None:
    _user_clients.pop(user_id, None)
