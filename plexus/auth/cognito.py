"""Cognito hosted-authorization support for interactive Plexus CLI users."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping, Optional, Protocol
from urllib.parse import parse_qs, urlencode, urlparse

import requests


KEYRING_SERVICE = "plexus"
KEYRING_USERNAME = "cognito-refresh-token"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"


class ApplicationAuthenticationRequired(ValueError):
    """Raised when a user must sign in again before using the application API."""


class LoopbackCallbackError(ApplicationAuthenticationRequired):
    """Raised for an invalid hosted-authorization callback."""


class RefreshTokenStore(Protocol):
    def get(self) -> Optional[str]: ...

    def set(self, refresh_token: str) -> None: ...

    def delete(self) -> None: ...


@dataclass(frozen=True)
class CognitoAuthConfig:
    """Stable deployment-to-CLI discovery contract for hosted authorization."""

    domain: str
    client_id: str
    region: Optional[str] = None
    redirect_uri: str = DEFAULT_REDIRECT_URI
    scopes: tuple[str, ...] = ("openid", "email", "profile")

    @classmethod
    def from_environment(cls) -> "CognitoAuthConfig":
        domain = os.getenv("PLEXUS_COGNITO_DOMAIN", "").strip().rstrip("/")
        client_id = os.getenv("PLEXUS_COGNITO_CLIENT_ID", "").strip()
        region = os.getenv("PLEXUS_COGNITO_REGION", "").strip() or None
        redirect_uri = os.getenv("PLEXUS_COGNITO_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()
        if not domain or not client_id:
            raise ApplicationAuthenticationRequired(
                "Cognito application authentication is not configured. "
                "Set PLEXUS_COGNITO_DOMAIN and PLEXUS_COGNITO_CLIENT_ID, then run `plexus login`."
            )
        if not domain.startswith("https://"):
            raise ApplicationAuthenticationRequired(
                "PLEXUS_COGNITO_DOMAIN must be an HTTPS hosted-authorization URL. Run `plexus login` after fixing it."
            )
        if redirect_uri != DEFAULT_REDIRECT_URI:
            raise ApplicationAuthenticationRequired(
                f"PLEXUS_COGNITO_REDIRECT_URI must be {DEFAULT_REDIRECT_URI}. Run `plexus login` after fixing it."
            )
        scopes = tuple(filter(None, os.getenv("PLEXUS_COGNITO_SCOPES", "openid email profile").split()))
        return cls(
            domain=domain,
            client_id=client_id,
            region=region,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )


@dataclass(frozen=True)
class AuthorizationRequest:
    url: str
    state: str
    code_verifier: str


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    id_token: Optional[str]
    expires_at: datetime


class KeyringRefreshTokenStore:
    """Stores the long-lived refresh credential in the operating-system keychain."""

    def __init__(self, keyring_module: Any = None):
        if keyring_module is None:
            try:
                import keyring as keyring_module
            except ImportError as exc:  # pragma: no cover - dependency packaging guard
                raise ApplicationAuthenticationRequired(
                    "The operating-system keychain integration is unavailable. Run `plexus login` after installing Plexus authentication support."
                ) from exc
        self._keyring = keyring_module

    def get(self) -> Optional[str]:
        return self._keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)

    def set(self, refresh_token: str) -> None:
        self._keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, refresh_token)

    def delete(self) -> None:
        try:
            self._keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except Exception:
            # Absence is an already-signed-out state. Keyring implementations do
            # not consistently expose a shared "not found" exception class.
            return


class CognitoAuthService:
    """Performs authorization-code login and supplies current bearer tokens."""

    def __init__(
        self,
        config: Optional[CognitoAuthConfig] = None,
        credential_store: Optional[RefreshTokenStore] = None,
        http: Any = requests,
        browser_opener: Callable[[str], bool] = webbrowser.open,
    ):
        self.config = config or CognitoAuthConfig.from_environment()
        self.credential_store = credential_store or KeyringRefreshTokenStore()
        self.http = http
        self.browser_opener = browser_opener

    @staticmethod
    def _new_state() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _new_code_verifier() -> str:
        return secrets.token_urlsafe(64)

    @staticmethod
    def _code_challenge(code_verifier: str) -> str:
        return base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")

    def create_authorization_request(
        self,
        state: Optional[str] = None,
        code_verifier: Optional[str] = None,
    ) -> AuthorizationRequest:
        state = state or self._new_state()
        code_verifier = code_verifier or self._new_code_verifier()
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.config.client_id,
                "redirect_uri": self.config.redirect_uri,
                "scope": " ".join(self.config.scopes),
                "state": state,
                "code_challenge": self._code_challenge(code_verifier),
                "code_challenge_method": "S256",
            }
        )
        return AuthorizationRequest(
            url=f"{self.config.domain}/oauth2/authorize?{query}",
            state=state,
            code_verifier=code_verifier,
        )

    @staticmethod
    def validate_callback(query: Mapping[str, str], expected_state: str) -> str:
        if not hmac.compare_digest(query.get("state", ""), expected_state):
            raise LoopbackCallbackError("The login callback state did not match. Run `plexus login` again.")
        if query.get("error"):
            raise LoopbackCallbackError(
                f"Cognito authorization failed: {query['error']}. Run `plexus login` again."
            )
        code = query.get("code")
        if not code:
            raise LoopbackCallbackError("The login callback did not include an authorization code. Run `plexus login` again.")
        return code

    def _receive_loopback_callback(self, expected_state: str, timeout_seconds: int = 300) -> str:
        redirect = urlparse(self.config.redirect_uri)
        result: dict[str, Any] = {}
        completed = threading.Event()
        service = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                query = {key: values[0] for key, values in parse_qs(urlparse(self.path).query).items()}
                if urlparse(self.path).path != redirect.path:
                    self.send_error(404)
                    return
                try:
                    result["code"] = service.validate_callback(query, expected_state)
                except LoopbackCallbackError as exc:
                    result["error"] = exc
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Plexus could not validate this login callback. You can close this page.")
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Plexus login complete. You can close this page.")
                completed.set()

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        try:
            server = ThreadingHTTPServer((redirect.hostname or "127.0.0.1", redirect.port or 8765), CallbackHandler)
        except OSError as exc:
            raise LoopbackCallbackError(
                f"The configured Plexus login callback port {redirect.port} is unavailable. "
                "Free the port and run `plexus login` again."
            ) from exc
        server.timeout = 0.25
        deadline = time.monotonic() + timeout_seconds
        try:
            while not completed.wait(timeout=server.timeout):
                server.handle_request()
                if time.monotonic() >= deadline:
                    raise LoopbackCallbackError("Timed out waiting for the Cognito login callback. Run `plexus login` again.")
        finally:
            server.server_close()
        if "error" in result:
            raise result["error"]
        return result["code"]

    def login(self) -> str:
        authorization = self.create_authorization_request()
        if not self.browser_opener(authorization.url):
            raise ApplicationAuthenticationRequired(
                f"Could not open a browser. Open {authorization.url} and then return to this terminal."
            )
        code = self._receive_loopback_callback(authorization.state)
        return self.complete_authorization(code, authorization.code_verifier)

    def complete_authorization(self, code: str, code_verifier: str) -> str:
        response = self.http.post(
            f"{self.config.domain}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self.config.client_id,
                "code": code,
                "redirect_uri": self.config.redirect_uri,
                "code_verifier": code_verifier,
            },
            timeout=15,
        )
        response.raise_for_status()
        tokens = self._tokens_from_response(response.json())
        refresh_token = response.json().get("refresh_token")
        if not refresh_token:
            raise ApplicationAuthenticationRequired("Cognito did not issue a refresh credential. Run `plexus login` again.")
        self.credential_store.set(refresh_token)
        return self._identity_from_tokens(tokens)

    def _refresh_tokens(self) -> TokenSet:
        refresh_token = self.credential_store.get()
        if not refresh_token:
            raise ApplicationAuthenticationRequired("No Plexus application session is available. Run `plexus login` to authenticate.")
        try:
            response = self.http.post(
                f"{self.config.domain}/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.config.client_id,
                    "refresh_token": refresh_token,
                },
                timeout=15,
            )
            response.raise_for_status()
            return self._tokens_from_response(response.json())
        except Exception as exc:
            self.credential_store.delete()
            raise ApplicationAuthenticationRequired(
                "The Plexus application session expired or was revoked. Run `plexus login` to authenticate."
            ) from exc

    @staticmethod
    def _tokens_from_response(payload: Mapping[str, Any]) -> TokenSet:
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ApplicationAuthenticationRequired("Cognito did not return an access token. Run `plexus login` again.")
        expires_in = payload.get("expires_in", 3600)
        try:
            expires_in = int(expires_in)
        except (TypeError, ValueError):
            expires_in = 3600
        return TokenSet(
            access_token=access_token,
            id_token=payload.get("id_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )

    def get_access_token(self) -> str:
        return self._refresh_tokens().access_token

    @staticmethod
    def _jwt_claims(token: Optional[str]) -> Mapping[str, Any]:
        if not token:
            return {}
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        try:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            value = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    def _identity_from_tokens(self, tokens: TokenSet) -> str:
        claims = self._jwt_claims(tokens.id_token) or self._jwt_claims(tokens.access_token)
        for key in ("email", "cognito:username", "username", "sub"):
            value = claims.get(key)
            if isinstance(value, str) and value:
                return value
        return "authenticated user"

    def whoami(self) -> str:
        return self._identity_from_tokens(self._refresh_tokens())

    def logout(self) -> None:
        refresh_token = self.credential_store.get()
        try:
            if refresh_token:
                response = self.http.post(
                    f"{self.config.domain}/oauth2/revoke",
                    data={"client_id": self.config.client_id, "token": refresh_token},
                    timeout=15,
                )
                response.raise_for_status()
        finally:
            self.credential_store.delete()
