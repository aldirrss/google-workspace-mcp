#!/bin/bash

set -e

# Support Docker secrets — load client secret JSON from file if path is given
if [ -n "$GOOGLE_OAUTH_CLIENT_SECRET_FILE" ] && [ -f "$GOOGLE_OAUTH_CLIENT_SECRET_FILE" ]; then
    echo "Loading OAuth2 client secret from file: $GOOGLE_OAUTH_CLIENT_SECRET_FILE"
    export GOOGLE_OAUTH_CLIENT_SECRET_JSON="$(cat "$GOOGLE_OAUTH_CLIENT_SECRET_FILE")"
fi

# Validate that OAuth2 client secret is available before starting.
# Trim whitespace and surrounding shell quotes (common docker-compose .env mistake).
_secret_trimmed="$(echo "${GOOGLE_OAUTH_CLIENT_SECRET_JSON}" | tr -d '[:space:]' | sed "s/^['\"]//;s/['\"]$//")"
if [ -z "$_secret_trimmed" ]; then
    echo "ERROR: OAuth2 client secret not found or empty."
    echo "  Set GOOGLE_OAUTH_CLIENT_SECRET_JSON to the contents of client_secret.json"
    echo "  (do NOT wrap the value in single or double quotes in the .env file)"
    echo "  or set GOOGLE_OAUTH_CLIENT_SECRET_FILE to the path of client_secret.json"
    exit 1
fi
# Quick sanity check — value must look like a JSON object
if [ "$(echo "$_secret_trimmed" | cut -c1)" != "{" ]; then
    echo "ERROR: GOOGLE_OAUTH_CLIENT_SECRET_JSON does not look like JSON (must start with '{')."
    echo "  Make sure you pasted the full client_secret.json content."
    exit 1
fi
unset _secret_trimmed

TRANSPORT="${TRANSPORT:-http}"
PORT="${SERVER_PORT:-8347}"
HOST="${SERVER_HOST:-0.0.0.0}"

case "$1" in
    stdio)
        echo "Starting MCP server — transport: stdio"
        exec python server.py --transport stdio
        ;;
    http)
        echo "Starting MCP server — transport: HTTP on $HOST:$PORT"
        exec python server.py --transport http --host "$HOST" --port "$PORT"
        ;;
    --)
        shift
        exec python server.py "$@"
        ;;
    "")
        if [ "$TRANSPORT" = "stdio" ]; then
            echo "Starting MCP server — transport: stdio"
            exec python server.py --transport stdio
        else
            echo "Starting MCP server — transport: HTTP on $HOST:$PORT"
            exec python server.py --transport http --host "$HOST" --port "$PORT"
        fi
        ;;
    *)
        exec "$@"
        ;;
esac
