#!/bin/bash

set -e

# Support Docker secrets — load JSON from file if env var points to a path
if [ -n "$GOOGLE_SERVICE_ACCOUNT_FILE" ] && [ -f "$GOOGLE_SERVICE_ACCOUNT_FILE" ]; then
    echo "Loading Service Account credentials from file: $GOOGLE_SERVICE_ACCOUNT_FILE"
    export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat "$GOOGLE_SERVICE_ACCOUNT_FILE")"
fi

# Validate that credentials are available before starting
if [ -z "$GOOGLE_SERVICE_ACCOUNT_JSON" ]; then
    echo "ERROR: Google Service Account credentials not found."
    echo "  Set GOOGLE_SERVICE_ACCOUNT_JSON (inline JSON string)"
    echo "  or GOOGLE_SERVICE_ACCOUNT_FILE (path to JSON key file / Docker secret)"
    exit 1
fi

# Default transport and port from env, fallback to HTTP for Docker
TRANSPORT="${TRANSPORT:-http}"
PORT="${SERVER_PORT:-8080}"
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
        # No argument — use TRANSPORT env var
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
