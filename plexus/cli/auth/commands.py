"""Official interactive Cognito login commands."""

import click

from plexus.auth.cognito import ApplicationAuthenticationRequired, CognitoAuthService


def _service() -> CognitoAuthService:
    return CognitoAuthService()


@click.command()
def login() -> None:
    """Sign in through the configured Cognito hosted authorization page."""
    try:
        identity = _service().login()
    except ApplicationAuthenticationRequired as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Signed in as {identity}.")


@click.command()
def whoami() -> None:
    """Display the identity of the current Plexus application session."""
    try:
        identity = _service().whoami()
    except ApplicationAuthenticationRequired as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(identity)


@click.command()
def logout() -> None:
    """Revoke and remove the current Plexus application session."""
    try:
        _service().logout()
    except ApplicationAuthenticationRequired as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("Signed out.")
