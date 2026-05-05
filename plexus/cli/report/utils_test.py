from unittest.mock import MagicMock

import click
import pytest

from plexus.cli.report.utils import resolve_account_id_for_command


def test_resolve_account_id_for_command_accepts_account_id(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "plexus.cli.report.utils.Account.get_by_id",
        lambda _id, _client: MagicMock(id="acct-id"),
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.Account.get_by_key",
        lambda _key, _client: (_ for _ in ()).throw(AssertionError("key lookup should not run")),
    )

    result = resolve_account_id_for_command(client, "acct-id")

    assert result == "acct-id"


def test_resolve_account_id_for_command_accepts_account_key(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "plexus.cli.report.utils.Account.get_by_id",
        lambda _id, _client: (_ for _ in ()).throw(Exception("not an id")),
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.Account.get_by_key",
        lambda _key, _client: MagicMock(id="acct-by-key"),
    )

    result = resolve_account_id_for_command(client, "call-criteria")

    assert result == "acct-by-key"


def test_resolve_account_id_for_command_raises_abort_for_unknown_identifier(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "plexus.cli.report.utils.Account.get_by_id",
        lambda _id, _client: (_ for _ in ()).throw(Exception("not found")),
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.Account.get_by_key",
        lambda _key, _client: None,
    )

    with pytest.raises(click.Abort):
        resolve_account_id_for_command(client, "missing-account")


def test_resolve_account_id_for_command_unknown_identifier_prints_actionable_error(
    monkeypatch, capsys
):
    client = MagicMock()
    monkeypatch.setattr(
        "plexus.cli.report.utils.Account.get_by_id",
        lambda _id, _client: (_ for _ in ()).throw(Exception("not found")),
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.Account.get_by_key",
        lambda _key, _client: None,
    )

    with pytest.raises(click.Abort):
        resolve_account_id_for_command(client, "missing-account")

    output = capsys.readouterr().out
    assert "Could not resolve account identifier 'missing-account' as key or ID" in output


def test_resolve_account_id_for_command_uses_default_context_when_identifier_missing():
    client = MagicMock()
    client._resolve_account_id.return_value = "acct-default"

    result = resolve_account_id_for_command(client, None)

    assert result == "acct-default"
    client._resolve_account_id.assert_called_once_with()
