import base64
import hashlib
import json
import socket
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests

from plexus.auth.cognito import (
    ApplicationAuthenticationRequired,
    CognitoAuthConfig,
    CognitoAuthService,
    KeyringRefreshTokenStore,
    LoopbackCallbackError,
    MissingApplicationSession,
    RefreshCredentialRejected,
    RefreshTransportFailure,
    TokenSet,
)


def _jwt(payload):
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"header.{encoded}.signature"


def _oauth_error_response(status_code, *, payload=None, body=None):
    response = requests.Response()
    response.status_code = status_code
    if payload is not None:
        response._content = json.dumps(payload).encode()
        response.headers["Content-Type"] = "application/json"
    else:
        response._content = (body or "").encode()
    return response


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


def test_loopback_callback_does_not_wait_for_reverse_dns(config, monkeypatch):
    service = CognitoAuthService(config=config, credential_store=Mock())
    monkeypatch.setattr(
        socket,
        "getfqdn",
        Mock(side_effect=AssertionError("loopback login must not perform reverse DNS")),
    )

    listener = service._bind_loopback_callback("state")

    listener.close()


def test_login_binds_loopback_listener_before_opening_browser(config):
    listener = Mock()
    listener.wait.return_value = "authorization-code"
    calls = []
    service = CognitoAuthService(
        config=config,
        credential_store=Mock(),
        browser_opener=lambda _url: calls.append("browser") or True,
    )
    service._bind_loopback_callback = Mock(side_effect=lambda _state: calls.append("listener") or listener)
    service.complete_authorization = Mock(return_value="person@example.test")

    assert service.login() == "person@example.test"

    assert calls == ["listener", "browser"]
    listener.wait.assert_called_once()
    listener.close.assert_called_once()


def test_login_keeps_listener_open_when_browser_does_not_launch(config, capsys):
    listener = Mock()
    listener.wait.return_value = "authorization-code"
    service = CognitoAuthService(
        config=config,
        credential_store=Mock(),
        browser_opener=lambda _url: False,
    )
    service._bind_loopback_callback = Mock(return_value=listener)
    service.complete_authorization = Mock(return_value="person@example.test")

    assert service.login() == "person@example.test"

    assert "Open this URL to continue login" in capsys.readouterr().err
    listener.wait.assert_called_once()
    listener.close.assert_called_once()


def test_configuration_discovery_uses_the_hosted_domain_client_and_region(monkeypatch):
    monkeypatch.setenv("PLEXUS_COGNITO_DOMAIN", "https://tenant.auth.us-east-1.amazoncognito.com")
    monkeypatch.setenv("PLEXUS_COGNITO_CLIENT_ID", "user-pool-client")
    monkeypatch.setenv("PLEXUS_COGNITO_REGION", "us-east-1")

    discovered = CognitoAuthConfig.from_environment()

    assert discovered.domain == "https://tenant.auth.us-east-1.amazoncognito.com"
    assert discovered.client_id == "user-pool-client"
    assert discovered.region == "us-east-1"
    assert discovered.redirect_uri == "http://127.0.0.1:8765/callback"


def test_configuration_discovers_hosted_authorization_from_amplify_output(tmp_path, monkeypatch):
    output = tmp_path / "dashboard" / "amplify_outputs.json"
    output.parent.mkdir()
    output.write_text(json.dumps({"auth": {"user_pool_client_id": "output-client-id", "aws_region": "us-west-2", "oauth": {"domain": "tenant.auth.us-west-2.amazoncognito.com"}}}))
    monkeypatch.delenv("PLEXUS_COGNITO_DOMAIN", raising=False)
    monkeypatch.delenv("PLEXUS_COGNITO_CLIENT_ID", raising=False)
    monkeypatch.delenv("PLEXUS_COGNITO_REGION", raising=False)
    monkeypatch.setattr(CognitoAuthConfig, "_output_paths", classmethod(lambda cls: (output,)))

    discovered = CognitoAuthConfig.from_environment()

    assert discovered.domain == "https://tenant.auth.us-west-2.amazoncognito.com"
    assert discovered.client_id == "output-client-id"
    assert discovered.region == "us-west-2"


def test_environment_configuration_overrides_amplify_output(tmp_path, monkeypatch):
    output = tmp_path / "amplify_outputs.json"
    output.write_text(json.dumps({"auth": {"user_pool_client_id": "output-client-id", "oauth": {"domain": "output.example.test"}}}))
    monkeypatch.setenv("PLEXUS_COGNITO_DOMAIN", "https://env.example.test")
    monkeypatch.setenv("PLEXUS_COGNITO_CLIENT_ID", "env-client-id")
    monkeypatch.setattr(CognitoAuthConfig, "_output_paths", classmethod(lambda cls: (output,)))

    discovered = CognitoAuthConfig.from_environment()

    assert discovered.domain == "https://env.example.test"
    assert discovered.client_id == "env-client-id"


def test_configuration_explains_when_amplify_has_no_hosted_authorization_output(tmp_path, monkeypatch):
    output = tmp_path / "amplify_outputs.json"
    output.write_text(json.dumps({"auth": {"user_pool_client_id": "client", "aws_region": "us-east-1"}}))
    monkeypatch.delenv("PLEXUS_COGNITO_DOMAIN", raising=False)
    monkeypatch.delenv("PLEXUS_COGNITO_CLIENT_ID", raising=False)
    monkeypatch.setattr(CognitoAuthConfig, "_output_paths", classmethod(lambda cls: (output,)))

    with pytest.raises(ApplicationAuthenticationRequired, match="hosted authorization"):
        CognitoAuthConfig.from_environment()


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


def test_token_exchange_failure_returns_actionable_login_guidance(config):
    response = Mock()
    response.raise_for_status.side_effect = RuntimeError("401 unauthorized")
    service = CognitoAuthService(
        config=config,
        credential_store=Mock(),
        http=Mock(post=Mock(return_value=response)),
    )

    with pytest.raises(ApplicationAuthenticationRequired, match="hosted authorization deployment"):
        service.complete_authorization(code="code", code_verifier="verifier")


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


def test_access_token_is_cached_in_memory_until_near_expiry(config):
    store = Mock(get=Mock(return_value="refresh-token"))
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"access_token": "new-access-token", "expires_in": 3600}
    http = Mock(post=Mock(return_value=response))
    service = CognitoAuthService(config=config, credential_store=store, http=http)

    assert service.get_access_token() == "new-access-token"
    assert service.get_access_token() == "new-access-token"

    assert http.post.call_count == 1


def test_access_token_is_refreshed_when_it_is_within_the_pre_expiry_window(config):
    store = Mock(get=Mock(return_value="refresh-token"))
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = [
        {"access_token": "first-token", "expires_in": 30},
        {"access_token": "second-token", "expires_in": 3600},
    ]
    http = Mock(post=Mock(return_value=response))
    service = CognitoAuthService(config=config, credential_store=store, http=http)

    assert service.get_access_token() == "first-token"
    assert service.get_access_token() == "second-token"

    assert http.post.call_count == 2


def test_missing_refresh_credential_requires_login_without_a_network_refresh(config):
    store = Mock(get=Mock(return_value=None))
    http = Mock()
    service = CognitoAuthService(config=config, credential_store=store, http=http)

    with pytest.raises(MissingApplicationSession, match="No Plexus application session"):
        service.get_access_token()

    http.post.assert_not_called()
    store.delete.assert_not_called()


def test_confirmed_invalid_grant_removes_refresh_credential_and_requires_login(config):
    store = Mock()
    store.get.return_value = "revoked-refresh-token"
    response = Mock()
    response.status_code = 400
    response.json.return_value = {"error": "invalid_grant"}
    response.raise_for_status.side_effect = requests.HTTPError(
        "400 invalid_grant", response=response,
    )
    http = Mock(post=Mock(return_value=response))
    sleeper = Mock()
    service = CognitoAuthService(
        config=config,
        credential_store=store,
        http=http,
        sleeper=sleeper,
    )

    with pytest.raises(RefreshCredentialRejected, match="expired or was revoked"):
        service.get_access_token()

    store.delete.assert_called_once()
    http.post.assert_called_once()
    sleeper.assert_not_called()


def test_invalid_grant_raised_directly_by_post_removes_refresh_credential(config):
    store = Mock(get=Mock(return_value="revoked-refresh-token"))
    response = _oauth_error_response(400, payload={"error": "invalid_grant"})
    rejected = requests.HTTPError("400 invalid_grant", response=response)
    service = CognitoAuthService(
        config=config,
        credential_store=store,
        http=Mock(post=Mock(side_effect=rejected)),
    )

    with pytest.raises(RefreshCredentialRejected) as captured:
        service.get_access_token()

    store.delete.assert_called_once()
    assert captured.value.__cause__ is rejected


def test_transient_refresh_failure_is_retried_before_the_command_fails(config):
    store = Mock(get=Mock(return_value="refresh-token"))
    first_response = Mock()
    first_response.raise_for_status.side_effect = requests.Timeout("temporary timeout")
    second_response = Mock()
    second_response.raise_for_status.return_value = None
    second_response.json.return_value = {"access_token": "recovered-token", "expires_in": 3600}
    http = Mock(post=Mock(side_effect=[first_response, second_response]))
    sleeper = Mock()
    service = CognitoAuthService(
        config=config,
        credential_store=store,
        http=http,
        sleeper=sleeper,
    )

    assert service.get_access_token() == "recovered-token"
    assert http.post.call_count == 2
    sleeper.assert_called_once()
    store.delete.assert_not_called()


def test_repeated_transient_refresh_failures_stop_after_the_bounded_retry(config):
    store = Mock(get=Mock(return_value="refresh-token"))
    response = Mock()
    response.raise_for_status.side_effect = requests.Timeout("temporary timeout")
    sleeper = Mock()
    service = CognitoAuthService(
        config=config,
        credential_store=store,
        http=Mock(post=Mock(return_value=response)),
        sleeper=sleeper,
    )

    with pytest.raises(RefreshTransportFailure, match="temporarily unavailable"):
        service.get_access_token()

    assert service.http.post.call_count == 3
    assert sleeper.call_count == 2
    store.delete.assert_not_called()


@pytest.mark.parametrize(
    ("response", "case"),
    [
        (_oauth_error_response(503, payload={"error": "server_error"}), "server failure"),
        (_oauth_error_response(400, body="not json"), "malformed body"),
        (_oauth_error_response(400, payload={"error": "invalid_request"}), "other OAuth error"),
    ],
)
def test_unproven_refresh_rejections_preserve_credential(config, response, case):
    store = Mock(get=Mock(return_value="refresh-token"))
    transport_error = requests.HTTPError(case, response=response)
    response.raise_for_status = Mock(side_effect=transport_error)
    service = CognitoAuthService(
        config=config,
        credential_store=store,
        http=Mock(post=Mock(return_value=response)),
    )

    with pytest.raises(RefreshTransportFailure) as captured:
        service.get_access_token()

    store.delete.assert_not_called()
    assert captured.value.__cause__ is transport_error


def test_typed_refresh_failures_remain_compatible_with_authentication_callers():
    assert issubclass(MissingApplicationSession, ApplicationAuthenticationRequired)
    assert issubclass(RefreshCredentialRejected, ApplicationAuthenticationRequired)
    assert issubclass(RefreshTransportFailure, ApplicationAuthenticationRequired)


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


def test_keyring_store_only_suppresses_the_keyring_not_found_error():
    class MissingCredential(Exception):
        pass

    keyring = Mock()
    keyring.errors = Mock(PasswordDeleteError=MissingCredential)
    keyring.delete_password.side_effect = MissingCredential()
    store = KeyringRefreshTokenStore(keyring_module=keyring)

    store.delete()


def test_keyring_store_reports_a_real_delete_failure():
    keyring = Mock()
    keyring.errors = Mock(PasswordDeleteError=RuntimeError)
    keyring.delete_password.side_effect = OSError("keychain unavailable")
    store = KeyringRefreshTokenStore(keyring_module=keyring)

    with pytest.raises(ApplicationAuthenticationRequired, match="keychain"):
        store.delete()
