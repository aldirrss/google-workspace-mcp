"""
Response formatting utilities — JSON and Markdown output helpers.
"""

import json
from enum import Enum
from typing import Any


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


def to_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def file_url(file_id: str, mime_type: str) -> str:
    """Build a Google Workspace URL from file ID and MIME type."""
    routes = {
        "application/vnd.google-apps.spreadsheet": "spreadsheets",
        "application/vnd.google-apps.document":    "document",
        "application/vnd.google-apps.presentation": "presentation",
    }
    path = routes.get(mime_type, "file")
    return f"https://docs.google.com/{path}/d/{file_id}/edit"


def format_file_list(files: list[dict], title: str) -> str:
    """Render a list of Drive files as a Markdown table."""
    if not files:
        return f"No {title} found."

    lines = [f"## {title}", "", "| Name | ID | Link |", "|------|-----|------|"]
    for f in files:
        name = f.get("name", "Untitled")
        fid  = f.get("id", "")
        mime = f.get("mimeType", "")
        url  = file_url(fid, mime)
        lines.append(f"| {name} | `{fid}` | [Open]({url}) |")

    return "\n".join(lines)


def format_spreadsheet_values(values: list[list[Any]], range_name: str) -> str:
    """Render spreadsheet cell values as a Markdown table."""
    if not values:
        return f"No data found in range `{range_name}`."

    headers = values[0] if values else []
    rows    = values[1:] if len(values) > 1 else []

    header_row    = "| " + " | ".join(str(h) for h in headers) + " |"
    separator_row = "| " + " | ".join("---" for _ in headers) + " |"

    lines = [f"## Data: `{range_name}`", "", header_row, separator_row]
    for row in rows:
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(str(c) for c in padded) + " |")

    return "\n".join(lines)
