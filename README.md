# google-workspace-mcp

MCP server for Google Workspace — create, read, update, and delete Google Sheets, Docs, and Slides using a Service Account.

## Features

- **Google Sheets** — full-featured: CRUD on spreadsheets, sheet tabs, cell ranges, formatting, and workflow tools
- **Google Docs** — basic CRUD: create, read, list, append text, delete
- **Google Slides** — basic CRUD: create, read, list, add slides, delete
- **Hybrid transport** — runs as `stdio` (Claude Desktop / Claude Code) or `HTTP` (Docker / remote)
- **Service Account auth** — no user login required; single credentials shared across all tools

## Tools (19 total)

### Google Sheets — Atomic (13)

| Tool | Description |
|------|-------------|
| `gws_sheets_create` | Create a new spreadsheet |
| `gws_sheets_get` | Get spreadsheet metadata and sheet list |
| `gws_sheets_delete` | Delete a spreadsheet (permanent if owned, trash if shared) |
| `gws_sheets_list` | List all accessible spreadsheets including Shared Drives |
| `gws_sheets_read_range` | Read cell values from an A1 range |
| `gws_sheets_write_range` | Write values to a range (overwrites) |
| `gws_sheets_update_range` | Update values in a range (idempotent) |
| `gws_sheets_clear_range` | Clear values from a range |
| `gws_sheets_append_rows` | Append rows after the last row with data |
| `gws_sheets_add_sheet` | Add a new sheet tab |
| `gws_sheets_delete_sheet` | Delete a sheet tab |
| `gws_sheets_list_sheets` | List all sheet tabs with IDs |
| `gws_sheets_format_range` | Apply formatting (bold, color, font size, alignment) |

### Google Sheets — Workflow (3)

| Tool | Description |
|------|-------------|
| `gws_sheets_create_with_data` | Create spreadsheet + write headers + data + bold headers in one call |
| `gws_sheets_bulk_update` | Update multiple ranges atomically in a single API call |
| `gws_sheets_export` | Generate an export URL (XLSX, PDF, CSV, ODS) |

### Google Docs (5)

| Tool | Description |
|------|-------------|
| `gws_docs_create` | Create a new empty document |
| `gws_docs_get` | Get document content as plain text |
| `gws_docs_list` | List all accessible documents |
| `gws_docs_append_text` | Append text to the end of a document |
| `gws_docs_delete` | Delete a document (permanent if owned, trash if shared) |

### Google Slides (5)

| Tool | Description |
|------|-------------|
| `gws_slides_create` | Create a new empty presentation |
| `gws_slides_get` | Get presentation metadata and slide text summary |
| `gws_slides_list` | List all accessible presentations |
| `gws_slides_add_slide` | Add a slide with optional title, body, and layout |
| `gws_slides_delete` | Delete a presentation (permanent if owned, trash if shared) |

## Requirements

- Python 3.12+
- A Google Cloud project with Sheets, Docs, Drive, and Slides APIs enabled
- A Service Account with a JSON key file

## Setup

### 1. Create a Google Cloud Project and Enable APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click the project dropdown (top left) → **New Project** → enter a name → **Create**
3. Make sure the new project is selected in the dropdown

**Enable the required APIs** — for each API below:

- [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)
- [Google Docs API](https://console.cloud.google.com/apis/library/docs.googleapis.com)
- [Google Slides API](https://console.cloud.google.com/apis/library/slides.googleapis.com)
- [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)

Click the link → **Enable** (or search by name in **APIs & Services → Library**)

### 2. Create a Service Account

1. Go to **APIs & Services → [Credentials](https://console.cloud.google.com/apis/credentials)**
2. Click **+ Create Credentials → Service Account**
3. Fill in:
   - **Service account name**: e.g. `google-workspace-mcp`
   - **Service account ID**: auto-filled, e.g. `google-workspace-mcp@your-project.iam.gserviceaccount.com`
   - Description: optional
4. Click **Create and Continue**
5. **Grant this service account access to project** — skip this step (click **Continue**)
6. **Grant users access to this service account** — skip (click **Done**)

### 3. Download the JSON Key File

1. On the **Credentials** page, click the Service Account you just created
2. Go to the **Keys** tab
3. Click **Add Key → Create new key**
4. Select **JSON** → **Create**
5. A `.json` file will be downloaded automatically — **keep this file safe**, it contains your private key

### 4. Share Files with the Service Account

Copy the Service Account email (e.g. `google-workspace-mcp@your-project.iam.gserviceaccount.com`)
from the Credentials page, then share any Drive file or folder with it:

1. Open the file/folder in Google Drive
2. Click **Share**
3. Paste the Service Account email
4. Set role to **Editor**
5. Uncheck **Notify people** (Service Accounts don't read email)
6. Click **Share**

### 5. Choose how you want to run the server

There are two ways to run this server. **Pick one** — you don't need both.

---

#### Option A — Local (stdio, for Claude Desktop / Claude Code)

Use this if you want to connect directly from Claude Desktop or Claude Code on your machine.
The server runs as a subprocess — no network port needed.

**Requires:** Python 3.12+ and a virtual environment.

```bash
# Create and activate a venv (isolates dependencies from your system Python)
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies inside the venv
pip install -r requirements.txt

# Set credentials
cp .env.example .env
# Edit .env — set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE

# Run
python server.py
```

> The venv is required here because `google-api-python-client` and `mcp` have many
> sub-dependencies that can conflict with system-level packages.

---

#### Option B — Docker (HTTP, for remote / multi-client access)

Use this if you want to deploy the server on a machine or server and connect to it over HTTP.
Docker handles all isolation — **no venv needed**.

**Requires:** Docker and Docker Compose.

```bash
# Set credentials
cp .env.example .env
# Edit .env — set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE

# Build image and start (required on first run or after code changes)
docker compose up -d --build
```

The container uses `entrypoint.sh` which runs automatically on start and:
- Validates credentials before starting (exits with a clear error if missing)
- Loads credentials from a file if `GOOGLE_SERVICE_ACCOUNT_FILE` is set (Docker secrets support)
- Routes transport based on the `TRANSPORT` env var

**Optional — use Docker secrets instead of an env var (more secure):**

```yaml
# docker-compose.yml
services:
  google-workspace-mcp:
    environment:
      - GOOGLE_SERVICE_ACCOUNT_FILE=/run/secrets/service_account
    secrets:
      - service_account

secrets:
  service_account:
    file: ./secrets/service_account.json
```

## Running

| Mode | Command | Use case |
|------|---------|----------|
| Local stdio | `python server.py` | Claude Desktop / Claude Code (requires venv) |
| Local HTTP | `python server.py --transport http --port 8347` | Testing HTTP locally |
| Docker (first run) | `docker compose up -d --build` | Remote / production (no venv needed) |
| Docker (config change only) | `docker compose up -d` | After changing `.env` or `docker-compose.yml` |

## Connecting to Claude

There are three clients that can connect to this server. Use the table below to pick the right setup:

| Client | Transport | Requires |
|--------|-----------|----------|
| Claude Web (claude.ai) | HTTP remote | Deployed server with public URL |
| Claude Desktop | stdio or HTTP | Local venv or deployed server |
| Claude Code (CLI) | stdio or HTTP | Local venv or deployed server |

---

### Claude Web (claude.ai)

Claude Web connects to MCP servers over HTTP only — the server must be publicly accessible (e.g. deployed on a VPS behind Nginx with SSL).

1. Go to [claude.ai](https://claude.ai) → click your profile avatar (bottom left) → **Settings**
2. Go to **Integrations** → **Add more**
3. Enter the server URL: `https://your-domain.com/mcp`
4. Click **Add** — Claude Web will verify the connection

```
Server URL: https://your-domain.com/mcp
```

> Claude Web requires HTTPS. Make sure SSL is set up on your server (see [nginx.conf](nginx.conf) + Certbot).

---

### Claude Desktop

**Option A — Local (stdio):**

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "/path/to/google-workspace-mcp/.venv/bin/python",
      "args": ["/path/to/google-workspace-mcp/server.py"],
      "env": {
        "GOOGLE_SERVICE_ACCOUNT_JSON": "{...}"
      }
    }
  }
}
```

> Use the full path to the venv Python binary — not the system `python` — so the installed
> packages are found correctly.

**Option B — Remote server (HTTP):**

```json
{
  "mcpServers": {
    "google-workspace": {
      "type": "http",
      "url": "https://your-domain.com/mcp"
    }
  }
}
```

---

### Claude Code (CLI)

Add to `~/.claude/settings.json` (global) or `.claude/settings.json` (per project):

**Option A — Local (stdio):**

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "/path/to/google-workspace-mcp/.venv/bin/python",
      "args": ["/path/to/google-workspace-mcp/server.py"],
      "env": {
        "GOOGLE_SERVICE_ACCOUNT_JSON": "{...}"
      }
    }
  }
}
```

**Option B — Remote server (HTTP):**

```json
{
  "mcpServers": {
    "google-workspace": {
      "type": "http",
      "url": "https://your-domain.com/mcp"
    }
  }
}
```

## Project Structure

```
google-workspace-mcp/
├── server.py                   # Entry point — stdio + HTTP hybrid transport
├── config.py                   # Environment variable loader
├── auth/
│   └── service_account.py      # Credentials and API client builder
├── tools/
│   ├── sheets/
│   │   ├── atomic.py           # 13 atomic Sheets tools
│   │   └── workflow.py         # 3 composite Sheets tools
│   ├── docs/
│   │   └── atomic.py           # 5 Docs tools
│   └── slides/
│       └── atomic.py           # 5 Slides tools
├── utils/
│   ├── errors.py               # Centralized Google API error handling
│   └── formatters.py           # JSON / Markdown response helpers
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes* | Full service account JSON as a string |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Yes* | Path to service account JSON file |
| `SERVER_PORT` | No | HTTP port (default: `8347`) |
| `SERVER_HOST` | No | HTTP bind host (default: `0.0.0.0`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

\* One of `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_FILE` is required.

## Working with Shared Files

The Service Account can access any file shared with its email address — including files in
personal Drive, Shared Drives, and folders shared by other users.

### Permission levels

| Role | list | read | write / format | delete |
|------|------|------|---------------|--------|
| **Viewer** | ✅ | ✅ | ❌ | ❌ |
| **Commenter** | ✅ | ✅ | ❌ | ❌ |
| **Editor** | ✅ | ✅ | ✅ | trash only¹ |
| **Owner** | ✅ | ✅ | ✅ | ✅ permanent |

¹ Drive restricts permanent deletion to the file owner. When the Service Account is not the owner,
`gws_sheets_delete` / `gws_docs_delete` / `gws_slides_delete` will **move the file to trash** instead
and return `"action": "trashed"` in the response.

### How to share a file

1. Open the file in Google Drive
2. Click **Share**
3. Enter the Service Account email: `your-sa@your-project.iam.gserviceaccount.com`
4. Set role to **Editor**
5. Uncheck "Notify people" (Service Accounts don't read email)
6. Click **Share**

## Response Formats

All list and read tools support a `response_format` parameter:

- `markdown` (default) — human-readable tables and headers, ideal for chat
- `json` — structured data for programmatic use

## Error Handling

All tools return actionable error strings on failure:

| HTTP Status | Message |
|-------------|---------|
| 401 | Authentication failed — check credentials and scopes |
| 403 | Permission denied — share the file with the Service Account |
| 404 | Resource not found — check the ID |
| 429 | Rate limit exceeded — wait and retry |
| 5xx | Google API server error — retry later |
