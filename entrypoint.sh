#!/bin/bash

set -e

# Support Docker secrets — load client secret JSON from file if path is given
if [ -n "$GOOGLE_OAUTH_CLIENT_SECRET_FILE" ] && [ -f "$GOOGLE_OAUTH_CLIENT_SECRET_FILE" ]; then
    echo "Loading OAuth2 client secret from file: $GOOGLE_OAUTH_CLIENT_SECRET_FILE"
    export GOOGLE_OAUTH_CLIENT_SECRET_JSON="$(cat "$GOOGLE_OAUTH_CLIENT_SECRET_FILE")"
fi

# Validate that OAuth2 client secret is available before starting
if [ -z "$GOOGLE_OAUTH_CLIENT_SECRET_JSON" ]; then
    echo "ERROR: OAuth2 client secret not found."
    echo "  Set GOOGLE_OAUTH_CLIENT_SECRET_JSON (inline JSON string)"
    echo "  or GOOGLE_OAUTH_CLIENT_SECRET_FILE (path to client_secret.json)"
    exit 1
fi

# Token file info
TOKEN_FILE="${GOOGLE_TOKEN_FILE:-/secrets/token.json}"
if [ -f "$TOKEN_FILE" ]; then
    echo "OAuth2 token file found: $TOKEN_FILE"
else
    echo "No OAuth2 token found. Visit ${SERVER_BASE_URL:-http://localhost:8347}/auth/setup to authorize."
fi

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
