"""
Centralized error handling for Google API calls.
"""

from googleapiclient.errors import HttpError


def handle_google_error(e: Exception) -> str:
    """Convert Google API exceptions into actionable error strings."""
    if isinstance(e, HttpError):
        status = e.resp.status
        reason = _extract_reason(e)

        if status == 400:
            return f"Error: Bad request — {reason}. Check your parameters."
        if status == 401:
            return "Error: Authentication failed. Verify your Service Account credentials and scopes."
        if status == 403:
            return (
                f"Error: Permission denied — {reason}. "
                "Ensure the Service Account has been granted access to this resource."
            )
        if status == 404:
            return f"Error: Resource not found — {reason}. Check the ID is correct."
        if status == 429:
            return "Error: Rate limit exceeded. Wait a moment and retry."
        if status >= 500:
            return f"Error: Google API server error ({status}). Try again later."
        return f"Error: Google API error {status} — {reason}."

    if isinstance(e, ValueError):
        return f"Error: Invalid input — {e}"

    return f"Error: Unexpected error — {type(e).__name__}: {e}"


def _extract_reason(e: HttpError) -> str:
    """Extract a human-readable reason from an HttpError."""
    try:
        import json
        details = json.loads(e.content.decode())
        return details.get("error", {}).get("message", str(e))
    except Exception:
        return str(e)
