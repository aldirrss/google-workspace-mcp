"""
MCP OAuth2 Authorization Server provider — delegates identity to Google OAuth.

Flow:
  1. Claude Web → GET /authorize   → provider.authorize() → redirect to Google
  2. Google     → GET /google/callback → handle_google_callback() → MCP auth code
  3. Claude Web → POST /token       → exchange_authorization_code() → MCP tokens
  4. Tool call  → Bearer token      → load_access_token() → user lookup
"""

import base64
import hashlib
import secrets
import time
from typing import Any

from google.oauth2.credentials import Credentials
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from auth.oauth2 import build_clients, build_flow
from auth.session import set_user_clients


# ---------------------------------------------------------------------------
# Extended token types — add user_id without exposing it in JSON responses
# ---------------------------------------------------------------------------

class GoogleAuthorizationCode(AuthorizationCode):
    user_id: str


class GoogleAccessToken(AccessToken):
    user_id: str


class GoogleRefreshToken(RefreshToken):
    user_id: str


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class GoogleOAuthProvider(
    OAuthAuthorizationServerProvider[
        GoogleAuthorizationCode,
        GoogleRefreshToken,
        GoogleAccessToken,
    ]
):
    def __init__(self, client_config: dict[str, Any], base_url: str) -> None:
        self._client_config = client_config
        self._base_url = base_url.rstrip("/")

        self._mcp_clients:    dict[str, OAuthClientInformationFull] = {}
        self._pending_auths:  dict[str, dict] = {}          # google_state → {mcp_client, mcp_params}
        self._auth_codes:     dict[str, GoogleAuthorizationCode] = {}
        self._access_tokens:  dict[str, GoogleAccessToken] = {}
        self._refresh_tokens: dict[str, GoogleRefreshToken] = {}

    # ── Dynamic client registration ─────────────────────────────────────────

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._mcp_clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._mcp_clients[client_info.client_id] = client_info

    # ── Authorization ────────────────────────────────────────────────────────

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        google_state = secrets.token_urlsafe(32)
        code_verifier, code_challenge = _pkce_pair()

        redirect_uri = f"{self._base_url}/google/callback"
        flow = build_flow(self._client_config, redirect_uri)
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            state=google_state,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )

        self._pending_auths[google_state] = {
            "mcp_client":    client,
            "mcp_params":    params,
            "code_verifier": code_verifier,
        }
        return auth_url

    async def handle_google_callback(
        self,
        code: str,
        state: str,
    ) -> str:
        """Called from /google/callback after Google redirects back.
        Returns the URL to redirect the user to (Claude Web's redirect_uri).
        """
        pending = self._pending_auths.pop(state, None)
        if not pending:
            raise AuthorizeError(
                error="invalid_request",
                error_description="Unknown or expired state parameter.",
            )

        mcp_client: OAuthClientInformationFull = pending["mcp_client"]
        mcp_params: AuthorizationParams        = pending["mcp_params"]

        redirect_uri = f"{self._base_url}/google/callback"
        flow = build_flow(self._client_config, redirect_uri)
        flow.fetch_token(code=code, code_verifier=pending["code_verifier"])
        google_creds: Credentials = flow.credentials

        user_id = _get_google_user_id(google_creds)

        set_user_clients(user_id, build_clients(google_creds))

        mcp_code = secrets.token_urlsafe(40)
        self._auth_codes[mcp_code] = GoogleAuthorizationCode(
            code=mcp_code,
            client_id=mcp_client.client_id,
            scopes=mcp_params.scopes or [],
            expires_at=time.time() + 600,
            code_challenge=mcp_params.code_challenge,
            redirect_uri=mcp_params.redirect_uri,
            redirect_uri_provided_explicitly=mcp_params.redirect_uri_provided_explicitly,
            user_id=user_id,
        )

        return construct_redirect_uri(
            str(mcp_params.redirect_uri),
            code=mcp_code,
            state=mcp_params.state,
        )

    # ── Token exchange ───────────────────────────────────────────────────────

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> GoogleAuthorizationCode | None:
        ac = self._auth_codes.get(authorization_code)
        if ac and ac.client_id == client.client_id:
            return ac
        return None

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: GoogleAuthorizationCode,
    ) -> OAuthToken:
        if time.time() > authorization_code.expires_at:
            raise TokenError(error="invalid_grant", error_description="Authorization code expired.")

        del self._auth_codes[authorization_code.code]

        access_token  = secrets.token_urlsafe(40)
        refresh_token = secrets.token_urlsafe(40)
        expires_in    = 3600

        self._access_tokens[access_token] = GoogleAccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + expires_in,
            user_id=authorization_code.user_id,
        )
        self._refresh_tokens[refresh_token] = GoogleRefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            user_id=authorization_code.user_id,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            refresh_token=refresh_token,
            scope=" ".join(authorization_code.scopes),
        )

    # ── Token loading / refresh ──────────────────────────────────────────────

    async def load_access_token(self, token: str) -> GoogleAccessToken | None:
        at = self._access_tokens.get(token)
        if not at:
            return None
        if at.expires_at and time.time() > at.expires_at:
            del self._access_tokens[token]
            return None
        return at

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> GoogleRefreshToken | None:
        rt = self._refresh_tokens.get(refresh_token)
        if rt and rt.client_id == client.client_id:
            return rt
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: GoogleRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        scopes_to_use = scopes or refresh_token.scopes

        new_access  = secrets.token_urlsafe(40)
        new_refresh = secrets.token_urlsafe(40)
        expires_in  = 3600

        self._access_tokens[new_access] = GoogleAccessToken(
            token=new_access,
            client_id=client.client_id,
            scopes=scopes_to_use,
            expires_at=int(time.time()) + expires_in,
            user_id=refresh_token.user_id,
        )
        self._refresh_tokens[new_refresh] = GoogleRefreshToken(
            token=new_refresh,
            client_id=client.client_id,
            scopes=scopes_to_use,
            user_id=refresh_token.user_id,
        )

        del self._refresh_tokens[refresh_token.token]

        return OAuthToken(
            access_token=new_access,
            token_type="bearer",
            expires_in=expires_in,
            refresh_token=new_refresh,
            scope=" ".join(scopes_to_use),
        )

    # ── Revocation ───────────────────────────────────────────────────────────

    async def revoke_token(
        self,
        token: GoogleAccessToken | GoogleRefreshToken,
    ) -> None:
        if isinstance(token, GoogleAccessToken):
            self._access_tokens.pop(token.token, None)
        else:
            self._refresh_tokens.pop(token.token, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256 method."""
    verifier = secrets.token_urlsafe(96)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _get_google_user_id(creds: Credentials) -> str:
    """Fetch the authenticated Google user's email via the People API."""
    from googleapiclient.discovery import build as build_service
    service = build_service("oauth2", "v2", credentials=creds)
    info = service.userinfo().get().execute()
    return info.get("email") or info["id"]
