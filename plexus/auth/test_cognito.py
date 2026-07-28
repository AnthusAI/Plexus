import base64
import hashlib
import json
import socket
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from plexus.auth.cognito import (
    ApplicationAuthenticationRequired,
    CognitoAuthConfig,
    CognitoAuthService,
    KeyringRefreshTokenStore,
    LoopbackCallbackError,
    TokenSet,
)


def _jwt(payload):
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"header.{encoded}.signature"


@pytest.fixture
def config():
    return CognitoAuthConfig(
        domain="https://auth.example.test",
        client_id="client-id",
        redirect_uri="http://127.0.0.1:8765/callback",
    )


def test_login_url_uses_state_and_s256_pkce(config):
    service = CognitoAuthService(config=config, credential_store=Mock())

    authorization = service.create_authorization_request(state="state", code_verifier="verifier")

    assert authorization.url.startswith("https://auth.example.test/oauth2/authorize?")
    assert "response_type=code" in authorization.url
    assert "state=state" in authorization.url
    assert "code_challenge_method=S256" in authorization.url
    expected_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(b"verifier").digest()
    ).rstrip(b"=").decode()
    assert f"code_challenge={expected_challenge}" in authorization.url


def test_loopback_callback_rejects_missing_or_mismatched_state(config):
    service = CognitoAuthService(config=config, credential_store=Mock())

    with pytest.raises(LoopbackCallbackError, match="state"):
        service.validate_callback({"code": "code", "state": "wrong"}, expected_state="expected")


def test_loopback_callback_rejects_provider_errors(config):
    service = CognitoAuthService(config=config, credential_store=Mock())

    with pytest.raises(LoopbackCallbackError, match="access_denied"):
        service.validate_callback(
            {"error": "access_denied", "state": "expected"}, expected_state="expected"
        )


def test_loopback_callback_reports_an_occupied_registered_port(config):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 8765))
    listener.listen(1)
    service = CognitoAuthService(config=config, credential_store=Mock())
    try:
        with pytest.raises(LoopbackCallbackError, match="port 8765 is unavailable"):
            service._receive_loopback_callback("state", timeout_seconds=1)
    finally:
        listener.close()


def test_configuration_discovery_uses_the_hosted_domain_client_and_region(monkeypatch):
    monkeypatch.setenv("PLEXUS_COGNITO_DOMAIN", "https://tenant.auth.us-east-1.amazoncognito.com")
    monkeypatch.setenv("PLEXUS_COGNITO_CLIENT_ID", "user-pool-client")
    monkeypatch.setenv("PLEXUS_COGNITO_REGION", "us-east-1")

    discovered = CognitoAuthConfig.from_environment()

    assert discovered.domain == "https://tenant.auth.us-east-1.amazoncognito.com"
    assert discovered.client_id == "user-pool-client"
    assert discovered.region == "us-east-1"
    assert discovered.redirect_uri == "http://127.0.0.1:8765/callback"


def test_configuration_rejects_any_unregistered_loopback_callback(monkeypatch):
    monkeypatch.setenv("PLEXUS_COGNITO_DOMAIN", "https://auth.example.test")
    monkeypatch.setenv("PLEXUS_COGNITO_CLIENT_ID", "client-id")
    monkeypatch.setenv("PLEXUS_COGNITO_REDIRECT_URI", "http://127.0.0.1:8766/callback")

    with pytest.raises(ApplicationAuthenticationRequired, match="127.0.0.1:8765/callback"):
        CognitoAuthConfig.from_environment()


def test_exchange_stores_only_refresh_token(config):
    store = Mock()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "access_token": "access-token",
        "id_token": _jwt({"email": "person@example.test"}),
        "refresh_token": "refresh-token",
        "expires_in": 3600,
    }
    http = Mock(post=Mock(return_value=response))
    service = CognitoAuthService(config=config, credential_store=store, http=http)

    identity = service.complete_authorization(code="code", code_verifier="verifier")

    store.set.assert_called_once_with("refresh-token")
    assert identity == "person@example.test"
    call = http.post.call_args
    assert call.args[0] == "https://auth.example.test/oauth2/token"
    assert call.kwargs["data"]["code_verifier"] == "verifier"
    assert "refresh_token" not in call.kwargs["data"]


def test_access_token_is_refreshed_from_keychain(config):
    store = Mock()
    store.get.return_value = "refresh-token"
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"access_token": "new-access-token", "expires_in": 3600}
    http = Mock(post=Mock(return_value=response))
    service = CognitoAuthService(config=config, credential_store=store, http=http)

    assert service.get_access_token() == "new-access-token"
    assert http.post.call_args.kwargs["data"] == {
        "grant_type": "refresh_token",
        "client_id": "client-id",
        "refresh_token": "refresh-token",
    }


def test_revoked_refresh_token_is_removed_and_requires_login(config):
    store = Mock()
    store.get.return_value = "revoked-refresh-token"
    response = Mock()
    response.raise_for_status.side_effect = RuntimeError("401 unauthorized")
    service = CognitoAuthService(config=config, credential_store=store, http=Mock(post=Mock(return_value=response)))

    with pytest.raises(ApplicationAuthenticationRequired, match="plexus login"):
        service.get_access_token()

    store.delete.assert_called_once()


def test_whoami_uses_non_sensitive_identity_from_current_token(config):
    store = Mock()
    service = CognitoAuthService(config=config, credential_store=store)
    service._refresh_tokens = Mock(
        return_value=TokenSet(
            access_token="access",
            id_token=_jwt({"cognito:username": "a-user", "email": "person@example.test"}),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    store.get.return_value = "refresh-token"

    assert service.whoami() == "person@example.test"


def test_keyring_store_uses_the_os_keychain():
    keyring = Mock()
    store = KeyringRefreshTokenStore(keyring_module=keyring)

    store.set("refresh-token")
    store.get()
    store.delete()

    keyring.set_password.assert_called_once_with("plexus", "cognito-refresh-token", "refresh-token")
    keyring.get_password.assert_called_once_with("plexus", "cognito-refresh-token")
    keyring.delete_password.assert_called_once_with("plexus", "cognito-refresh-token")
