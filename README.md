# google-workspace-mcp

MCP server for Google Workspace — create, read, update, and delete Google Sheets, Docs, and Slides using your own Google account via OAuth2.

## Features

- **Google Sheets** — full-featured: CRUD on spreadsheets, sheet tabs, cell ranges, formatting, and workflow tools
- **Google Docs** — basic CRUD: create, read, list, append text, delete
- **Google Slides** — basic CRUD: create, read, list, add slides, delete
- **Hybrid transport** — runs as `stdio` (Claude Desktop / Claude Code) or `HTTP` (Docker / remote)
- **OAuth2 multi-user auth** — each user authenticates with their own Google account; access all files in their Drive without manual sharing

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

## For End Users

If someone has already deployed this server, all you need to do is:

1. Open [claude.ai](https://claude.ai) → profile avatar → **Settings** → **Integrations** → **Add more**
2. Enter the server URL provided by your admin, e.g. `https://your-domain.com/mcp`
3. Click **Connect** → you will be redirected to Google to sign in
4. Sign in with your Google account → done, all your Drive files are accessible

No configuration, no credentials, no file sharing required.

---

## For Server Admins

The sections below are for whoever is **deploying and hosting** this server.

## Requirements

- Python 3.12+
- A Google Cloud project with Sheets, Docs, Drive, and Slides APIs enabled
- An OAuth2 **Web Application** client ID and secret

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

### 2. Create an OAuth2 Client ID

1. Go to **APIs & Services → [Credentials](https://console.cloud.google.com/apis/credentials)**
2. Click **+ Create Credentials → OAuth client ID**
3. If prompted, configure the **OAuth consent screen** first:
   - User type: **External** (or Internal if using Google Workspace org)
   - Fill in App name and support email
   - Add scopes: `../auth/drive`, `../auth/spreadsheets`, `../auth/documents`, `../auth/presentations`
   - Add your email(s) as test users
4. Back in **Create OAuth client ID**:
   - Application type: **Web application**
   - Name: e.g. `google-workspace-mcp`
   - **Authorized redirect URIs**: add `https://your-domain.com/google/callback`
     (for local testing add `http://localhost:8347/google/callback` as well)
5. Click **Create** — download the JSON file (`client_secret_*.json`)

### 3. Choose how you want to run the server

There are two ways to run this server. **Pick one** — you don't need both.

---

#### Option A — Local (stdio, for Claude Desktop / Claude Code)

Use this if you want to connect directly from Claude Desktop or Claude Code on your machine.
The server runs as a subprocess — no network port needed.

**Requires:** Python 3.12+ and a virtual environment.

```bash
# Create and activate a venv
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set credentials
cp .env.example .env
# Edit .env — set GOOGLE_OAUTH_CLIENT_SECRET_JSON or GOOGLE_OAUTH_CLIENT_SECRET_FILE
#              and SERVER_BASE_URL=http://localhost:8347

# Run
python server.py
```

---

#### Option B — Docker (HTTP, for remote / multi-user access)

Use this if you want to deploy the server on a VPS and connect from Claude Web or multiple users.
Docker handles all isolation — **no venv needed**.

**Requires:** Docker and Docker Compose.

```bash
# Set credentials
cp .env.example .env
# Edit .env — set GOOGLE_OAUTH_CLIENT_SECRET_JSON or GOOGLE_OAUTH_CLIENT_SECRET_FILE
#              and SERVER_BASE_URL=https://your-domain.com

# Build image and start
docker compose up -d --build
```

The container uses `entrypoint.sh` which validates that the OAuth2 client secret is present before starting, then routes transport based on the `TRANSPORT` env var.

**Using Docker secrets (more secure):**

```yaml
# docker-compose.yml
services:
  google-workspace-mcp:
    environment:
      - GOOGLE_OAUTH_CLIENT_SECRET_FILE=/run/secrets/client_secret
    secrets:
      - client_secret

secrets:
  client_secret:
    file: ./secrets/client_secret.json
```

---

### 4. Deploy Nginx reverse proxy (HTTP mode only)

Copy the provided [nginx.conf](nginx.conf) to your server:

```bash
sudo cp nginx.conf /etc/nginx/sites-available/google-workspace-mcp
sudo ln -s /etc/nginx/sites-available/google-workspace-mcp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# SSL (required for Claude Web)
sudo certbot --nginx -d your-domain.com
```

## Running

| Mode | Command | Use case |
|------|---------|----------|
| Local stdio | `python server.py` | Claude Desktop / Claude Code (requires venv) |
| Local HTTP | `python server.py --transport http --port 8347` | Testing HTTP locally |
| Docker (first run) | `docker compose up -d --build` | Remote / production |
| Docker (config change only) | `docker compose up -d` | After changing `.env` or `docker-compose.yml` |

## Connecting to Claude

| Client | Transport | Requires |
|--------|-----------|----------|
| Claude Web (claude.ai) | HTTP remote | Deployed server with public HTTPS URL |
| Claude Desktop | stdio or HTTP | Local venv or deployed server |
| Claude Code (CLI) | stdio or HTTP | Local venv or deployed server |

---

### Claude Web (claude.ai)

The server must be publicly accessible over HTTPS. When you add the server URL and click **Connect**, you will be redirected to Google to sign in — no manual file sharing required.

1. Go to [claude.ai](https://claude.ai) → profile avatar → **Settings** → **Integrations** → **Add more**
2. Enter the server URL: `https://your-domain.com/mcp`
3. Click **Connect** → you will be redirected to Google login
4. Sign in with your Google account → all your Drive files are immediately accessible

> Each user connects with their own Google account. Multiple people can use the same deployed server independently.

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
        "GOOGLE_OAUTH_CLIENT_SECRET_JSON": "{...}",
        "SERVER_BASE_URL": "http://localhost:8347"
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
        "GOOGLE_OAUTH_CLIENT_SECRET_JSON": "{...}",
        "SERVER_BASE_URL": "http://localhost:8347"
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
│   ├── mcp_provider.py         # MCP OAuth2 Authorization Server (delegates to Google)
│   ├── oauth2.py               # Google OAuth2 flow helpers and API client builder
│   └── session.py              # Per-user clients store (keyed by Google account)
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
├── nginx.conf                  # Nginx reverse proxy config (VPS deployment)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_OAUTH_CLIENT_SECRET_JSON` | Yes* | Full `client_secret.json` content as a string |
| `GOOGLE_OAUTH_CLIENT_SECRET_FILE` | Yes* | Path to `client_secret.json` file |
| `SERVER_BASE_URL` | Yes | Public base URL, e.g. `https://your-domain.com` |
| `SERVER_PORT` | No | HTTP port (default: `8347`) |
| `SERVER_HOST` | No | HTTP bind host (default: `0.0.0.0`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

\* One of `GOOGLE_OAUTH_CLIENT_SECRET_JSON` or `GOOGLE_OAUTH_CLIENT_SECRET_FILE` is required.

## File Access

Each user can access all files in their own Google Drive — personal files, Shared Drives, and files shared with them by others. No manual sharing with a Service Account email is needed.

### Permission levels

| Role | list | read | write / format | delete |
|------|------|------|---------------|--------|
| **Viewer** | ✅ | ✅ | ❌ | ❌ |
| **Commenter** | ✅ | ✅ | ❌ | ❌ |
| **Editor** | ✅ | ✅ | ✅ | trash only¹ |
| **Owner** | ✅ | ✅ | ✅ | ✅ permanent |

¹ Drive restricts permanent deletion to the file owner. When the authenticated user is not the owner,
`gws_sheets_delete` / `gws_docs_delete` / `gws_slides_delete` will **move the file to trash** instead
and return `"action": "trashed"` in the response.

## Response Formats

All list and read tools support a `response_format` parameter:

- `markdown` (default) — human-readable tables and headers, ideal for chat
- `json` — structured data for programmatic use

## Error Handling

All tools return actionable error strings on failure:

| HTTP Status | Message |
|-------------|---------|
| 401 | Not authorized — visit the server URL and connect your Google account |
| 403 | Permission denied — you do not have access to this file |
| 404 | Resource not found — check the ID |
| 429 | Rate limit exceeded — wait and retry |
| 5xx | Google API server error — retry later |
