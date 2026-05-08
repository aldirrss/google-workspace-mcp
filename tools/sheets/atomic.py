"""
Google Sheets atomic tools — CRUD operations on spreadsheets, sheets, and cell ranges.
"""

from typing import Any, Optional

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field, field_validator

from utils import ResponseFormat, format_file_list, format_spreadsheet_values, handle_google_error, to_json


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class SheetsCreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(..., description="Spreadsheet title (e.g. 'Sales Report 2026')", min_length=1, max_length=200)
    sheet_names: Optional[list[str]] = Field(
        default=None,
        description="Initial sheet tab names. Defaults to a single 'Sheet1' if omitted.",
    )


class SheetsGetInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID from the URL (e.g. '1BxiM...')", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SheetsDeleteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID to delete permanently", min_length=1)


class SheetsListInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: Optional[str] = Field(default=None, description="Filter by name (partial match)")
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SheetsReadRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    range: str = Field(..., description="A1 notation range (e.g. 'Sheet1!A1:D10' or 'A:Z')", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SheetsWriteRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    range: str = Field(..., description="A1 notation range where writing starts (e.g. 'Sheet1!A1')", min_length=1)
    values: list[list[Any]] = Field(..., description="2D array of values to write. Each inner list = one row.")
    value_input_option: str = Field(
        default="USER_ENTERED",
        description="'USER_ENTERED' (parse formulas/dates) or 'RAW' (store as-is)",
    )

    @field_validator("values")
    @classmethod
    def validate_values_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("values must not be empty")
        return v


class SheetsUpdateRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    range: str = Field(..., description="A1 notation range to update (e.g. 'Sheet1!B2:C5')", min_length=1)
    values: list[list[Any]] = Field(..., description="2D array of new values")
    value_input_option: str = Field(default="USER_ENTERED")


class SheetsClearRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    range: str = Field(..., description="A1 notation range to clear (e.g. 'Sheet1!A1:Z100')", min_length=1)


class SheetsAppendRowsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    range: str = Field(..., description="Range to append after (e.g. 'Sheet1!A:A')", min_length=1)
    values: list[list[Any]] = Field(..., description="Rows to append")
    value_input_option: str = Field(default="USER_ENTERED")


class SheetsAddSheetInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    title: str = Field(..., description="New sheet tab name", min_length=1, max_length=100)
    index: Optional[int] = Field(default=None, description="Position (0-based). Appended last if omitted.", ge=0)


class SheetsDeleteSheetInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    sheet_id: int = Field(..., description="Numeric sheet ID (from gws_sheets_get)", ge=0)


class SheetsListSheetsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SheetsFormatRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    sheet_id: int = Field(..., description="Numeric sheet ID", ge=0)
    start_row: int = Field(..., description="Start row index (0-based, inclusive)", ge=0)
    end_row: int = Field(..., description="End row index (0-based, exclusive)", ge=1)
    start_col: int = Field(..., description="Start column index (0-based, inclusive)", ge=0)
    end_col: int = Field(..., description="End column index (0-based, exclusive)", ge=1)
    bold: Optional[bool] = Field(default=None, description="Set bold text")
    italic: Optional[bool] = Field(default=None, description="Set italic text")
    font_size: Optional[int] = Field(default=None, description="Font size in points", ge=6, le=72)
    background_color: Optional[dict] = Field(
        default=None,
        description='RGBA background color, e.g. {"red": 1.0, "green": 0.9, "blue": 0.0, "alpha": 1.0}',
    )
    text_color: Optional[dict] = Field(
        default=None,
        description='RGBA text color, e.g. {"red": 0.0, "green": 0.0, "blue": 0.0, "alpha": 1.0}',
    )
    horizontal_alignment: Optional[str] = Field(
        default=None,
        description="'LEFT', 'CENTER', or 'RIGHT'",
    )


# ---------------------------------------------------------------------------
# Tool registration factory
# ---------------------------------------------------------------------------

def register_sheets_atomic_tools(mcp, clients: dict) -> None:
    """Register all atomic Sheets tools onto the FastMCP instance."""

    sheets_api = clients["sheets"].spreadsheets()
    drive_api  = clients["drive"].files()

    # ------------------------------------------------------------------
    # gws_sheets_create
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_create",
        annotations={"title": "Create Spreadsheet", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_sheets_create(params: SheetsCreateInput, ctx: Context) -> str:
        """
        Create a new Google Spreadsheet with optional initial sheet tabs.

        Args:
            params.title: Spreadsheet display name.
            params.sheet_names: Optional list of sheet tab names to create.

        Returns:
            str: Markdown or JSON with spreadsheet ID and URL.
        """
        try:
            sheets_body: dict = {"properties": {"title": params.title}}
            if params.sheet_names:
                sheets_body["sheets"] = [
                    {"properties": {"title": name}} for name in params.sheet_names
                ]

            result = sheets_api.create(body=sheets_body).execute()
            sid = result["spreadsheetId"]
            url = f"https://docs.google.com/spreadsheets/d/{sid}/edit"

            await ctx.log_info("Created spreadsheet", {"id": sid, "title": params.title})
            return to_json({"spreadsheet_id": sid, "title": params.title, "url": url})
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_get
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_get",
        annotations={"title": "Get Spreadsheet Metadata", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_get(params: SheetsGetInput, ctx: Context) -> str:
        """
        Get metadata for a spreadsheet: title, sheets, and URL.

        Args:
            params.spreadsheet_id: The spreadsheet ID.
            params.response_format: 'markdown' or 'json'.

        Returns:
            str: Spreadsheet metadata.
        """
        try:
            result = sheets_api.get(
                spreadsheetId=params.spreadsheet_id,
                fields="spreadsheetId,properties/title,sheets/properties",
            ).execute()

            title   = result["properties"]["title"]
            sid     = result["spreadsheetId"]
            url     = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
            sheets  = [
                {
                    "sheet_id": s["properties"]["sheetId"],
                    "title":    s["properties"]["title"],
                    "index":    s["properties"]["index"],
                }
                for s in result.get("sheets", [])
            ]

            if params.response_format == ResponseFormat.JSON:
                return to_json({"spreadsheet_id": sid, "title": title, "url": url, "sheets": sheets})

            lines = [f"## {title}", f"**ID:** `{sid}`", f"**URL:** {url}", "", "### Sheets"]
            for s in sheets:
                lines.append(f"- **{s['title']}** (id: `{s['sheet_id']}`, index: {s['index']})")
            return "\n".join(lines)
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_delete
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_delete",
        annotations={"title": "Delete Spreadsheet", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_sheets_delete(params: SheetsDeleteInput, ctx: Context) -> str:
        """
        Delete a spreadsheet. If the Service Account owns the file, it is permanently deleted.
        If the file is shared (not owned), it is moved to trash instead — Drive only allows
        owners to permanently delete files.

        Args:
            params.spreadsheet_id: The spreadsheet ID to delete.

        Returns:
            str: JSON with action taken ('deleted' or 'trashed') and reason.
        """
        try:
            meta = drive_api.get(
                fileId=params.spreadsheet_id,
                fields="ownedByMe",
                supportsAllDrives=True,
            ).execute()

            if meta.get("ownedByMe", False):
                drive_api.delete(
                    fileId=params.spreadsheet_id,
                    supportsAllDrives=True,
                ).execute()
                await ctx.log_info("Deleted spreadsheet", {"id": params.spreadsheet_id})
                return to_json({
                    "action":         "deleted",
                    "spreadsheet_id": params.spreadsheet_id,
                })
            else:
                drive_api.update(
                    fileId=params.spreadsheet_id,
                    body={"trashed": True},
                    supportsAllDrives=True,
                ).execute()
                await ctx.log_info("Trashed spreadsheet (not owner)", {"id": params.spreadsheet_id})
                return to_json({
                    "action":         "trashed",
                    "spreadsheet_id": params.spreadsheet_id,
                    "reason":         "Service Account is not the owner. File moved to trash instead of permanent delete.",
                })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_list
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_list",
        annotations={"title": "List Spreadsheets", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_list(params: SheetsListInput, ctx: Context) -> str:
        """
        List all spreadsheets accessible by the Service Account.

        Args:
            params.query: Optional name filter (partial match).
            params.limit: Max results (1–100, default 20).
            params.response_format: 'markdown' or 'json'.

        Returns:
            str: List of spreadsheets with IDs and URLs.
        """
        try:
            q = "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
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

            return format_file_list(files, "Spreadsheets")
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_read_range
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_read_range",
        annotations={"title": "Read Sheet Range", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_read_range(params: SheetsReadRangeInput, ctx: Context) -> str:
        """
        Read cell values from a spreadsheet range.

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.range: A1 notation range (e.g. 'Sheet1!A1:D10').
            params.response_format: 'markdown' or 'json'.

        Returns:
            str: Cell values as a table or JSON array.
        """
        try:
            result = sheets_api.values().get(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
            ).execute()

            values = result.get("values", [])

            if params.response_format == ResponseFormat.JSON:
                return to_json({"range": params.range, "values": values, "row_count": len(values)})

            return format_spreadsheet_values(values, params.range)
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_write_range
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_write_range",
        annotations={"title": "Write to Sheet Range", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_sheets_write_range(params: SheetsWriteRangeInput, ctx: Context) -> str:
        """
        Write values to a spreadsheet range (overwrites existing data).

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.range: Starting cell in A1 notation.
            params.values: 2D array of values.
            params.value_input_option: 'USER_ENTERED' or 'RAW'.

        Returns:
            str: JSON with updated range and cell count.
        """
        try:
            result = sheets_api.values().update(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
                valueInputOption=params.value_input_option,
                body={"values": params.values},
            ).execute()

            return to_json({
                "updated_range":  result.get("updatedRange"),
                "updated_rows":   result.get("updatedRows"),
                "updated_cols":   result.get("updatedColumns"),
                "updated_cells":  result.get("updatedCells"),
            })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_update_range (alias with explicit semantics)
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_update_range",
        annotations={"title": "Update Sheet Range", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_update_range(params: SheetsUpdateRangeInput, ctx: Context) -> str:
        """
        Update specific cell values in a range (idempotent — safe to repeat).

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.range: A1 notation range to update.
            params.values: 2D array of replacement values.

        Returns:
            str: JSON with update summary.
        """
        try:
            result = sheets_api.values().update(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
                valueInputOption=params.value_input_option,
                body={"values": params.values},
            ).execute()

            return to_json({
                "updated_range": result.get("updatedRange"),
                "updated_cells": result.get("updatedCells"),
            })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_clear_range
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_clear_range",
        annotations={"title": "Clear Sheet Range", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_clear_range(params: SheetsClearRangeInput, ctx: Context) -> str:
        """
        Clear all values in a range (cells remain, formatting preserved).

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.range: A1 notation range to clear.

        Returns:
            str: JSON confirming cleared range.
        """
        try:
            result = sheets_api.values().clear(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
            ).execute()

            return to_json({"cleared_range": result.get("clearedRange")})
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_append_rows
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_append_rows",
        annotations={"title": "Append Rows to Sheet", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_sheets_append_rows(params: SheetsAppendRowsInput, ctx: Context) -> str:
        """
        Append rows after the last row with data in a range.

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.range: Range hint for where to append (e.g. 'Sheet1!A:A').
            params.values: Rows to append.

        Returns:
            str: JSON with the range where data was appended.
        """
        try:
            result = sheets_api.values().append(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
                valueInputOption=params.value_input_option,
                insertDataOption="INSERT_ROWS",
                body={"values": params.values},
            ).execute()

            updates = result.get("updates", {})
            return to_json({
                "appended_range": updates.get("updatedRange"),
                "appended_rows":  updates.get("updatedRows"),
                "appended_cells": updates.get("updatedCells"),
            })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_add_sheet
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_add_sheet",
        annotations={"title": "Add Sheet Tab", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_sheets_add_sheet(params: SheetsAddSheetInput, ctx: Context) -> str:
        """
        Add a new sheet tab to an existing spreadsheet.

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.title: New sheet tab name.
            params.index: Position (0-based). Appended at end if omitted.

        Returns:
            str: JSON with new sheet ID and title.
        """
        try:
            props: dict = {"title": params.title}
            if params.index is not None:
                props["index"] = params.index

            body = {"requests": [{"addSheet": {"properties": props}}]}
            result = sheets_api.batchUpdate(
                spreadsheetId=params.spreadsheet_id,
                body=body,
            ).execute()

            reply = result["replies"][0]["addSheet"]["properties"]
            return to_json({
                "sheet_id": reply["sheetId"],
                "title":    reply["title"],
                "index":    reply["index"],
            })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_delete_sheet
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_delete_sheet",
        annotations={"title": "Delete Sheet Tab", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_sheets_delete_sheet(params: SheetsDeleteSheetInput, ctx: Context) -> str:
        """
        Permanently delete a sheet tab from a spreadsheet.

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.sheet_id: Numeric sheet ID (from gws_sheets_get or gws_sheets_list_sheets).

        Returns:
            str: Confirmation JSON.
        """
        try:
            body = {"requests": [{"deleteSheet": {"sheetId": params.sheet_id}}]}
            sheets_api.batchUpdate(
                spreadsheetId=params.spreadsheet_id,
                body=body,
            ).execute()

            return to_json({"deleted": True, "sheet_id": params.sheet_id})
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_list_sheets
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_list_sheets",
        annotations={"title": "List Sheet Tabs", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_list_sheets(params: SheetsListSheetsInput, ctx: Context) -> str:
        """
        List all sheet tabs in a spreadsheet with their IDs and indices.

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.response_format: 'markdown' or 'json'.

        Returns:
            str: List of sheet tabs.
        """
        try:
            result = sheets_api.get(
                spreadsheetId=params.spreadsheet_id,
                fields="properties/title,sheets/properties(sheetId,title,index,sheetType)",
            ).execute()

            title  = result["properties"]["title"]
            sheets = [
                {
                    "sheet_id":   s["properties"]["sheetId"],
                    "title":      s["properties"]["title"],
                    "index":      s["properties"]["index"],
                    "sheet_type": s["properties"].get("sheetType", "GRID"),
                }
                for s in result.get("sheets", [])
            ]

            if params.response_format == ResponseFormat.JSON:
                return to_json({"spreadsheet_title": title, "sheets": sheets})

            lines = [f"## Sheets in '{title}'", ""]
            for s in sheets:
                lines.append(f"- **{s['title']}** — id: `{s['sheet_id']}`, index: {s['index']}")
            return "\n".join(lines)
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_format_range
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_format_range",
        annotations={"title": "Format Sheet Range", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_format_range(params: SheetsFormatRangeInput, ctx: Context) -> str:
        """
        Apply formatting (bold, italic, font size, colors, alignment) to a cell range.

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.sheet_id: Numeric sheet ID.
            params.start_row / end_row: Row range (0-based, end exclusive).
            params.start_col / end_col: Column range (0-based, end exclusive).
            params.bold / italic / font_size / background_color / text_color / horizontal_alignment:
                Formatting properties to apply.

        Returns:
            str: Confirmation JSON.
        """
        try:
            cell_format: dict = {}
            fields_list: list[str] = []

            if params.bold is not None:
                cell_format.setdefault("textFormat", {})["bold"] = params.bold
                fields_list.append("userEnteredFormat.textFormat.bold")

            if params.italic is not None:
                cell_format.setdefault("textFormat", {})["italic"] = params.italic
                fields_list.append("userEnteredFormat.textFormat.italic")

            if params.font_size is not None:
                cell_format.setdefault("textFormat", {})["fontSize"] = params.font_size
                fields_list.append("userEnteredFormat.textFormat.fontSize")

            if params.background_color is not None:
                cell_format["backgroundColor"] = params.background_color
                fields_list.append("userEnteredFormat.backgroundColor")

            if params.text_color is not None:
                cell_format.setdefault("textFormat", {})["foregroundColor"] = params.text_color
                fields_list.append("userEnteredFormat.textFormat.foregroundColor")

            if params.horizontal_alignment is not None:
                cell_format["horizontalAlignment"] = params.horizontal_alignment
                fields_list.append("userEnteredFormat.horizontalAlignment")

            if not fields_list:
                return "Error: No formatting properties specified."

            body = {
                "requests": [{
                    "repeatCell": {
                        "range": {
                            "sheetId":          params.sheet_id,
                            "startRowIndex":    params.start_row,
                            "endRowIndex":      params.end_row,
                            "startColumnIndex": params.start_col,
                            "endColumnIndex":   params.end_col,
                        },
                        "cell": {"userEnteredFormat": cell_format},
                        "fields": ",".join(fields_list),
                    }
                }]
            }

            sheets_api.batchUpdate(
                spreadsheetId=params.spreadsheet_id,
                body=body,
            ).execute()

            return to_json({
                "formatted": True,
                "range": {
                    "sheet_id":  params.sheet_id,
                    "start_row": params.start_row,
                    "end_row":   params.end_row,
                    "start_col": params.start_col,
                    "end_col":   params.end_col,
                },
                "applied_fields": fields_list,
            })
        except Exception as e:
            return handle_google_error(e)
