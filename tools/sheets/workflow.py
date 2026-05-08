"""
Google Sheets workflow tools — composite operations that combine multiple API calls.
"""

from typing import Any, Optional

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field, field_validator

from utils import ResponseFormat, handle_google_error, to_json


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class SheetsCreateWithDataInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(..., description="Spreadsheet title", min_length=1, max_length=200)
    sheet_name: str = Field(default="Sheet1", description="First sheet tab name")
    headers: list[str] = Field(..., description="Column headers for row 1 (e.g. ['Name', 'Email', 'Amount'])")
    rows: Optional[list[list[Any]]] = Field(
        default=None,
        description="Data rows to write below headers. Each inner list = one row.",
    )
    bold_headers: bool = Field(default=True, description="Apply bold formatting to the header row")

    @field_validator("headers")
    @classmethod
    def validate_headers_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("headers must not be empty")
        return v


class SheetsBulkUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID", min_length=1)
    updates: list[dict] = Field(
        ...,
        description=(
            'List of update operations. Each item: {"range": "Sheet1!A1", "values": [[...]]}. '
            "All updates are applied atomically in a single API call."
        ),
    )
    value_input_option: str = Field(default="USER_ENTERED")

    @field_validator("updates")
    @classmethod
    def validate_updates_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("updates list must not be empty")
        for item in v:
            if "range" not in item or "values" not in item:
                raise ValueError("Each update must have 'range' and 'values' keys")
        return v


class SheetsExportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    spreadsheet_id: str = Field(..., description="Spreadsheet ID to export", min_length=1)
    export_format: str = Field(
        default="xlsx",
        description="Export format: 'xlsx' (Excel), 'pdf', 'csv', 'ods'",
    )
    sheet_id: Optional[int] = Field(
        default=None,
        description="Export a specific sheet only (numeric sheet ID). Exports all sheets if omitted.",
    )

    @field_validator("export_format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        allowed = {"xlsx", "pdf", "csv", "ods"}
        if v.lower() not in allowed:
            raise ValueError(f"export_format must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


# ---------------------------------------------------------------------------
# MIME type map for export
# ---------------------------------------------------------------------------

_EXPORT_MIME: dict[str, str] = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf":  "application/pdf",
    "csv":  "text/csv",
    "ods":  "application/x-vnd.oasis.opendocument.spreadsheet",
}


# ---------------------------------------------------------------------------
# Tool registration factory
# ---------------------------------------------------------------------------

def register_sheets_workflow_tools(mcp, clients: dict) -> None:
    """Register composite Sheets workflow tools onto the FastMCP instance."""

    sheets_api = clients["sheets"].spreadsheets()
    drive_api  = clients["drive"].files()

    # ------------------------------------------------------------------
    # gws_sheets_create_with_data
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_create_with_data",
        annotations={"title": "Create Spreadsheet with Data", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def gws_sheets_create_with_data(params: SheetsCreateWithDataInput, ctx: Context) -> str:
        """
        Create a new spreadsheet, write headers and optional data rows, and optionally bold the headers —
        all in one operation.

        Args:
            params.title: Spreadsheet display name.
            params.sheet_name: First tab name (default 'Sheet1').
            params.headers: Column header strings for row 1.
            params.rows: Optional data rows (each = one row).
            params.bold_headers: Whether to bold the header row (default true).

        Returns:
            str: JSON with spreadsheet ID, URL, rows written, and sheet ID.
        """
        try:
            await ctx.report_progress(0.1, "Creating spreadsheet...")

            # Step 1: Create spreadsheet with named sheet
            create_result = sheets_api.create(body={
                "properties": {"title": params.title},
                "sheets": [{"properties": {"title": params.sheet_name}}],
            }).execute()

            sid      = create_result["spreadsheetId"]
            sheet_id = create_result["sheets"][0]["properties"]["sheetId"]
            url      = f"https://docs.google.com/spreadsheets/d/{sid}/edit"

            await ctx.report_progress(0.4, "Writing data...")

            # Step 2: Write headers + rows in one call
            all_values: list[list[Any]] = [params.headers]
            if params.rows:
                all_values.extend(params.rows)

            sheets_api.values().update(
                spreadsheetId=sid,
                range=f"{params.sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": all_values},
            ).execute()

            # Step 3: Bold headers if requested
            if params.bold_headers:
                await ctx.report_progress(0.7, "Applying header formatting...")
                sheets_api.batchUpdate(
                    spreadsheetId=sid,
                    body={"requests": [{
                        "repeatCell": {
                            "range": {
                                "sheetId":          sheet_id,
                                "startRowIndex":    0,
                                "endRowIndex":      1,
                                "startColumnIndex": 0,
                                "endColumnIndex":   len(params.headers),
                            },
                            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                            "fields": "userEnteredFormat.textFormat.bold",
                        }
                    }]},
                ).execute()

            await ctx.report_progress(1.0, "Done.")
            return to_json({
                "spreadsheet_id": sid,
                "title":          params.title,
                "url":            url,
                "sheet_id":       sheet_id,
                "headers":        params.headers,
                "data_rows":      len(params.rows) if params.rows else 0,
            })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_bulk_update
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_bulk_update",
        annotations={"title": "Bulk Update Sheet Ranges", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_bulk_update(params: SheetsBulkUpdateInput, ctx: Context) -> str:
        """
        Update multiple non-contiguous ranges in a single atomic API call.
        More efficient than calling gws_sheets_update_range repeatedly.

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.updates: List of {"range": "...", "values": [[...]]} dicts.
            params.value_input_option: 'USER_ENTERED' or 'RAW'.

        Returns:
            str: JSON summary of all updated ranges.
        """
        try:
            data = [
                {"range": u["range"], "values": u["values"]}
                for u in params.updates
            ]

            result = sheets_api.values().batchUpdate(
                spreadsheetId=params.spreadsheet_id,
                body={
                    "valueInputOption": params.value_input_option,
                    "data": data,
                },
            ).execute()

            responses = result.get("responses", [])
            summary = [
                {
                    "range":         r.get("updatedRange"),
                    "updated_cells": r.get("updatedCells"),
                    "updated_rows":  r.get("updatedRows"),
                }
                for r in responses
            ]

            return to_json({
                "total_ranges_updated": len(summary),
                "updates": summary,
            })
        except Exception as e:
            return handle_google_error(e)

    # ------------------------------------------------------------------
    # gws_sheets_export
    # ------------------------------------------------------------------
    @mcp.tool(
        name="gws_sheets_export",
        annotations={"title": "Export Spreadsheet", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def gws_sheets_export(params: SheetsExportInput, ctx: Context) -> str:
        """
        Generate an export download URL for a spreadsheet in XLSX, PDF, CSV, or ODS format.
        The URL is valid for ~1 hour using the Service Account's access token.

        Args:
            params.spreadsheet_id: Spreadsheet ID.
            params.export_format: 'xlsx', 'pdf', 'csv', or 'ods'.
            params.sheet_id: Optional — export a specific sheet only.

        Returns:
            str: JSON with the export download URL and MIME type.
        """
        try:
            mime_type = _EXPORT_MIME[params.export_format]

            export_params: dict = {"mimeType": mime_type}
            if params.sheet_id is not None:
                export_params["gid"] = str(params.sheet_id)

            # Build the export URL (Drive export endpoint)
            request = drive_api.export_media(
                fileId=params.spreadsheet_id,
                mimeType=mime_type,
            )

            # Return the request URI — caller downloads it with their auth token
            export_url = (
                f"https://docs.google.com/spreadsheets/d/{params.spreadsheet_id}/export"
                f"?format={params.export_format}"
            )
            if params.sheet_id is not None:
                export_url += f"&gid={params.sheet_id}"

            return to_json({
                "export_url":    export_url,
                "format":        params.export_format,
                "mime_type":     mime_type,
                "spreadsheet_id": params.spreadsheet_id,
                "note": "URL requires authentication. Use with Service Account access token.",
            })
        except Exception as e:
            return handle_google_error(e)
