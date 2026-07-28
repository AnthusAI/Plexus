from unittest.mock import Mock, patch

from click.testing import CliRunner

from plexus.auth.cognito import ApplicationAuthenticationRequired
from plexus.cli.shared.CommandLineInterface import cli


def test_login_is_a_top_level_command_that_confirms_the_identity():
    service = Mock(login=Mock(return_value="person@example.test"))
    with patch("plexus.cli.auth.commands._service", return_value=service):
        result = CliRunner().invoke(cli, ["login"])

    assert result.exit_code == 0
    assert "Signed in as person@example.test" in result.output


def test_whoami_requires_login_when_no_application_session_exists():
    service = Mock(whoami=Mock(side_effect=ApplicationAuthenticationRequired("Run `plexus login` to authenticate.")))
    with patch("plexus.cli.auth.commands._service", return_value=service):
        result = CliRunner().invoke(cli, ["whoami"])

    assert result.exit_code != 0
    assert "plexus login" in result.output


def test_logout_is_a_top_level_command_that_clears_the_session():
    service = Mock(logout=Mock(return_value=None))
    with patch("plexus.cli.auth.commands._service", return_value=service):
        result = CliRunner().invoke(cli, ["logout"])

    assert result.exit_code == 0
    assert "Signed out" in result.output
