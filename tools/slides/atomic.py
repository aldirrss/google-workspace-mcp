"""
Google Slides atomic tools — basic CRUD operations on presentations.
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

class SlidesCreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(..., description="Presentation title", min_length=1, max_length=200)


class SlidesGetInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    presentation_id: str = Field(..., description="Presentation ID from the URL", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SlidesListInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: Optional[str] = Field(default=None, description="Filter by presentation name (partial match)")
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SlidesAddSlideInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    presentation_id: str = Field(..., description="Presentation ID", min_length=1)
    title: Optional[str] = Field(default=None, description="Slide title text (added as a title shape)")
    body: Optional[str] = Field(default=None, description="Slide body/content text")
    layout: str = Field(
        default="TITLE_AND_BODY",
        description=(
            "Predefined layout: 'BLANK', 'TITLE_AND_BODY', 'TITLE_ONLY', "
            "'SECTION_HEADER', 'TWO_COLUMNS_TEXT', 'MAIN_POINT'"
        ),
    )
    insertion_index: Optional[int] = Field(
        default=None,
        description="0-based position to insert the slide. Appended at end if omitted.",
        ge=0,
    )


class SlidesDeleteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    presentation_id: str = Field(..., description="Presentation ID to delete permanently", min_length=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_slide_summary(slide: dict, index: int) -> dict:
    texts: list[str] = []
    for element in slide.get("pageElements", []):
        shape = element.get("shape", {})
        text_content = shape.get("text", {})
        for text_elem in text_content.get("textElements", []):
            text_run = text_elem.get("textRun")
            if text_run and text_run.get("content", "").strip():
                texts.append(text_run["content"].strip())

    return {
        "index":    index,
        "slide_id": slide.get("objectId", ""),
        "texts":    texts,
    }


# ---------------------------------------------------------------------------
# Tool registration factory
# ---------------------------------------------------------------------------

def register_slides_atomic_tools(mcp) -> None:
    """Register all basic Slides tools onto the FastMCP instance."""

    # ------------------------------------------------------------------
    # gws_slides_create
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_slides_create",
        annotations={"title": "Create Presentation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_slides_create(params: SlidesCreateInput, ctx: Context) -> str:
        """
        Create a new empty Google Slides presentation.

        Args:
            params.title: Presentation display name.

        Returns:
            str: JSON with presentation ID and URL.
        """
        clients = get_current_clients()
        if not clients.get("slides"):
            return _NOT_AUTHORIZED
        try:
            slides_api = clients["slides"].presentations()
            result = slides_api.create(body={"title": params.title}).execute()
            pid = result["presentationId"]
            url = f"https://docs.google.com/presentation/d/{pid}/edit"

            await ctx.log_info("Created presentation", {"id": pid, "title": params.title})
            return to_json({"presentation_id": pid, "title": params.title, "url": url})
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_slides_get
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_slides_get",
        annotations={"title": "Get Presentation", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_slides_get(params: SlidesGetInput, ctx: Context) -> str:
        """
        Get metadata and a text summary of all slides in a presentation.

        Args:
            params.presentation_id: Presentation ID.
            params.response_format: 'markdown' or 'json'.

        Returns:
            str: Presentation title, URL, slide count, and per-slide text.
        """
        clients = get_current_clients()
        if not clients.get("slides"):
            return _NOT_AUTHORIZED
        try:
            slides_api = clients["slides"].presentations()
            result = slides_api.get(presentationId=params.presentation_id).execute()
            title  = result.get("title", "Untitled")
            pid    = result["presentationId"]
            url    = f"https://docs.google.com/presentation/d/{pid}/edit"
            slides = [
                _extract_slide_summary(s, i)
                for i, s in enumerate(result.get("slides", []))
            ]

            if params.response_format == ResponseFormat.JSON:
                return to_json({
                    "presentation_id": pid,
                    "title":           title,
                    "url":             url,
                    "slide_count":     len(slides),
                    "slides":          slides,
                })

            lines = [
                f"## {title}",
                f"**ID:** `{pid}`",
                f"**URL:** {url}",
                f"**Slides:** {len(slides)}",
                "",
            ]
            for s in slides:
                text_preview = " / ".join(s["texts"][:2]) if s["texts"] else "(empty)"
                lines.append(f"- Slide {s['index'] + 1} (`{s['slide_id']}`): {text_preview}")
            return "\n".join(lines)
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_slides_list
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_slides_list",
        annotations={"title": "List Presentations", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_slides_list(params: SlidesListInput, ctx: Context) -> str:
        """
        List all Google Slides presentations in your Drive (owned, shared, and team drives).

        Args:
            params.query: Optional name filter (partial match).
            params.limit: Max results (1–100, default 20).
            params.response_format: 'markdown' or 'json'.

        Returns:
            str: List of presentations with IDs and URLs.
        """
        clients = get_current_clients()
        if not clients.get("drive"):
            return _NOT_AUTHORIZED
        try:
            drive_api = clients["drive"].files()
            q = "mimeType='application/vnd.google-apps.presentation' and trashed=false"
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

            return format_file_list(files, "Presentations")
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_slides_add_slide
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_slides_add_slide",
        annotations={"title": "Add Slide", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_slides_add_slide(params: SlidesAddSlideInput, ctx: Context) -> str:
        """
        Add a new slide to a presentation with optional title/body text and a predefined layout.

        Args:
            params.presentation_id: Presentation ID.
            params.title: Optional slide title text.
            params.body: Optional slide body text.
            params.layout: Predefined layout name (default 'TITLE_AND_BODY').
            params.insertion_index: 0-based position. Appended at end if omitted.

        Returns:
            str: JSON with new slide ID and position.
        """
        clients = get_current_clients()
        if not clients.get("slides"):
            return _NOT_AUTHORIZED
        try:
            import uuid
            slides_api = clients["slides"].presentations()
            slide_id = f"slide_{uuid.uuid4().hex[:8]}"

            requests: list[dict] = [{
                "createSlide": {
                    "objectId":             slide_id,
                    "slideLayoutReference": {"predefinedLayout": params.layout},
                    **({"insertionIndex": params.insertion_index} if params.insertion_index is not None else {}),
                }
            }]

            if params.title:
                requests.append({
                    "insertText": {
                        "objectId": f"{slide_id}_title",
                        "text":     params.title,
                    }
                })

            if params.body:
                requests.append({
                    "insertText": {
                        "objectId": f"{slide_id}_body",
                        "text":     params.body,
                    }
                })

            slides_api.batchUpdate(
                presentationId=params.presentation_id,
                body={"requests": requests},
            ).execute()

            return to_json({
                "slide_id":        slide_id,
                "presentation_id": params.presentation_id,
                "layout":          params.layout,
                "insertion_index": params.insertion_index,
            })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_slides_delete
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_slides_delete",
        annotations={"title": "Delete Presentation", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_slides_delete(params: SlidesDeleteInput, ctx: Context) -> str:
        """
        Delete a Google Slides presentation. Permanently deletes if you own the file,
        otherwise moves to trash (Drive restriction: only owners can permanently delete).

        Args:
            params.presentation_id: Presentation ID to delete.

        Returns:
            str: JSON with action taken ('deleted' or 'trashed').
        """
        clients = get_current_clients()
        if not clients.get("drive"):
            return _NOT_AUTHORIZED
        try:
            drive_api = clients["drive"].files()
            meta = drive_api.get(
                fileId=params.presentation_id,
                fields="ownedByMe",
                supportsAllDrives=True,
            ).execute()

            if meta.get("ownedByMe", False):
                drive_api.delete(
                    fileId=params.presentation_id,
                    supportsAllDrives=True,
                ).execute()
                await ctx.log_info("Deleted presentation", {"id": params.presentation_id})
                return to_json({"action": "deleted", "presentation_id": params.presentation_id})
            else:
                drive_api.update(
                    fileId=params.presentation_id,
                    body={"trashed": True},
                    supportsAllDrives=True,
                ).execute()
                await ctx.log_info("Trashed presentation (not owner)", {"id": params.presentation_id})
                return to_json({
                    "action":          "trashed",
                    "presentation_id": params.presentation_id,
                    "reason":          "You are not the owner. File moved to trash instead of permanent delete.",
                })
        except Exception as e:
            return handle_google_error(e)
