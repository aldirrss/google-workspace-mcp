"""
Google Docs atomic tools — basic CRUD operations on documents.
"""

from typing import Optional

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field

from auth.session import get_current_clients
from utils import ResponseFormat, format_file_list, handle_google_error, to_json

_NOT_AUTHORIZED = "Not authorized. Visit /auth/setup to connect your Google account."


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class DocsCreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(..., description="Document title", min_length=1, max_length=200)


class DocsGetInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    document_id: str = Field(..., description="Document ID from the URL", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class DocsListInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: Optional[str] = Field(default=None, description="Filter by document name (partial match)")
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class DocsAppendTextInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    document_id: str = Field(..., description="Document ID", min_length=1)
    text: str = Field(..., description="Text to append at the end of the document", min_length=1)
    add_newline: bool = Field(default=True, description="Prepend a newline before appended text")


class DocsDeleteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    document_id: str = Field(..., description="Document ID to delete permanently", min_length=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_plain_text(body: dict) -> str:
    lines: list[str] = []
    for element in body.get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        line_parts: list[str] = []
        for pe in paragraph.get("elements", []):
            text_run = pe.get("textRun")
            if text_run:
                line_parts.append(text_run.get("content", ""))
        lines.append("".join(line_parts))
    return "".join(lines)


# ---------------------------------------------------------------------------
# Tool registration factory
# ---------------------------------------------------------------------------

def register_docs_atomic_tools(mcp) -> None:
    """Register all basic Docs tools onto the FastMCP instance."""

    # ------------------------------------------------------------------
    # gws_docs_create
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_docs_create",
        annotations={"title": "Create Document", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_docs_create(params: DocsCreateInput, ctx: Context) -> str:
        """
        Create a new empty Google Document.

        Args:
            params.title: Document display name.

        Returns:
            str: JSON with document ID and URL.
        """
        clients = get_current_clients()
        if not clients.get("docs"):
            return _NOT_AUTHORIZED
        try:
            docs_api = clients["docs"].documents()
            result = docs_api.create(body={"title": params.title}).execute()
            did = result["documentId"]
            url = f"https://docs.google.com/document/d/{did}/edit"

            await ctx.log_info("Created document", {"id": did, "title": params.title})
            return to_json({"document_id": did, "title": params.title, "url": url})
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_docs_get
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_docs_get",
        annotations={"title": "Get Document Content", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_docs_get(params: DocsGetInput, ctx: Context) -> str:
        """
        Retrieve a document's title and text content.

        Args:
            params.document_id: Document ID.
            params.response_format: 'markdown' or 'json'.

        Returns:
            str: Document title and plain-text content.
        """
        clients = get_current_clients()
        if not clients.get("docs"):
            return _NOT_AUTHORIZED
        try:
            docs_api = clients["docs"].documents()
            result = docs_api.get(documentId=params.document_id).execute()
            title = result.get("title", "Untitled")
            did   = result["documentId"]
            url   = f"https://docs.google.com/document/d/{did}/edit"
            text  = _extract_plain_text(result.get("body", {}))

            if params.response_format == ResponseFormat.JSON:
                return to_json({"document_id": did, "title": title, "url": url, "text": text})

            return f"## {title}\n**ID:** `{did}`\n**URL:** {url}\n\n---\n\n{text}"
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_docs_list
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_docs_list",
        annotations={"title": "List Documents", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_docs_list(params: DocsListInput, ctx: Context) -> str:
        """
        List all Google Documents in your Drive (owned, shared, and team drives).

        Args:
            params.query: Optional name filter (partial match).
            params.limit: Max results (1–100, default 20).
            params.response_format: 'markdown' or 'json'.

        Returns:
            str: List of documents with IDs and URLs.
        """
        clients = get_current_clients()
        if not clients.get("drive"):
            return _NOT_AUTHORIZED
        try:
            drive_api = clients["drive"].files()
            q = "mimeType='application/vnd.google-apps.document' and trashed=false"
            if params.query:
                q += f" and name contains '{params.query}'"

            result = drive_api.list(
                q=q,
                pageSize=params.limit,
                fields="files(id,name,mimeType,modifiedTime,ownedByMe)",
                orderBy="modifiedTime desc",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                corpora="allDrives",
            ).execute()

            files = result.get("files", [])

            if params.response_format == ResponseFormat.JSON:
                return to_json({"total": len(files), "files": files})

            return format_file_list(files, "Documents")
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_docs_append_text
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_docs_append_text",
        annotations={"title": "Append Text to Document", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_docs_append_text(params: DocsAppendTextInput, ctx: Context) -> str:
        """
        Append plain text to the end of a Google Document.

        Args:
            params.document_id: Document ID.
            params.text: Text content to append.
            params.add_newline: Prepend a newline separator (default true).

        Returns:
            str: JSON confirming the append operation.
        """
        clients = get_current_clients()
        if not clients.get("docs"):
            return _NOT_AUTHORIZED
        try:
            docs_api = clients["docs"].documents()
            content = ("\n" + params.text) if params.add_newline else params.text

            docs_api.batchUpdate(
                documentId=params.document_id,
                body={
                    "requests": [{
                        "insertText": {
                            "location": {"index": 1},
                            "text": content,
                        }
                    }]
                },
            ).execute()

            return to_json({
                "appended": True,
                "document_id": params.document_id,
                "characters_added": len(content),
            })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_docs_delete
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_docs_delete",
        annotations={"title": "Delete Document", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_docs_delete(params: DocsDeleteInput, ctx: Context) -> str:
        """
        Delete a Google Document. Permanently deletes if you own the file,
        otherwise moves to trash (Drive restriction: only owners can permanently delete).

        Args:
            params.document_id: Document ID to delete.

        Returns:
            str: JSON with action taken ('deleted' or 'trashed').
        """
        clients = get_current_clients()
        if not clients.get("drive"):
            return _NOT_AUTHORIZED
        try:
            drive_api = clients["drive"].files()
            meta = drive_api.get(
                fileId=params.document_id,
                fields="ownedByMe",
                supportsAllDrives=True,
            ).execute()

            if meta.get("ownedByMe", False):
                drive_api.delete(
                    fileId=params.document_id,
                    supportsAllDrives=True,
                ).execute()
                await ctx.log_info("Deleted document", {"id": params.document_id})
                return to_json({"action": "deleted", "document_id": params.document_id})
            else:
                drive_api.update(
                    fileId=params.document_id,
                    body={"trashed": True},
                    supportsAllDrives=True,
                ).execute()
                await ctx.log_info("Trashed document (not owner)", {"id": params.document_id})
                return to_json({
                    "action":      "trashed",
                    "document_id": params.document_id,
                    "reason":      "You are not the owner. File moved to trash instead of permanent delete.",
                })
        except Exception as e:
            return handle_google_error(e)
