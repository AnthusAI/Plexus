import json
from typing import Any, Dict, Optional

import click
import yaml
from rich.table import Table

from plexus.chat.session_ops import (
    get_latest_chat_session,
    list_session_messages,
    resolve_account_id,
    send_chat_message,
)
from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.console import console


@click.group(name="chat")
def chat():
    """Inspect and send chat messages."""
    pass


def _render(data: Dict[str, Any], output: str) -> None:
    if output == "json":
        console.print(json.dumps(data, indent=2))
        return
    if output == "yaml":
        console.print(yaml.safe_dump(data, sort_keys=False))
        return

    table = Table(show_header=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            table.add_row(key, json.dumps(value))
        else:
            table.add_row(key, str(value))
    console.print(table)


def _render_messages(payload: Dict[str, Any], output: str) -> None:
    if output in {"json", "yaml"}:
        _render(payload, output)
        return

    summary = {
        "sessionId": payload.get("sessionId"),
        "offset": payload.get("offset"),
        "limit": payload.get("limit"),
        "count": payload.get("count"),
        "nextToken": payload.get("nextToken"),
    }
    _render(summary, "table")

    table = Table(title="Messages")
    table.add_column("Created", style="green")
    table.add_column("Role", style="magenta", width=10)
    table.add_column("Interaction", style="yellow", width=18)
    table.add_column("Type", style="cyan", width=12)
    table.add_column("ID", style="blue")
    table.add_column("Content", style="white")

    for message in payload.get("items", []):
        content = str(message.get("content") or "")
        content_preview = content if len(content) <= 120 else f"{content[:120]}..."
        table.add_row(
            str(message.get("createdAt") or ""),
            str(message.get("role") or ""),
            str(message.get("humanInteraction") or ""),
            str(message.get("messageType") or ""),
            str(message.get("id") or ""),
            content_preview,
        )
    console.print(table)


@chat.command("last")
@click.option("--account", default=None, help="Account key/name/ID (defaults to PLEXUS_ACCOUNT_KEY).")
@click.option("--procedure-id", default=None, help="Optional procedure filter.")
@click.option("--status", default=None, help="Optional session status filter.")
@click.option("--category", default=None, help="Optional session category filter.")
@click.option("--messages-limit", default=0, type=int, help="Include latest N messages from the selected session.")
@click.option("--include-internal", is_flag=True, help="Include INTERNAL messages when including messages.")
@click.option("--output", type=click.Choice(["table", "json", "yaml"]), default="table")
def chat_last(
    account: Optional[str],
    procedure_id: Optional[str],
    status: Optional[str],
    category: Optional[str],
    messages_limit: int,
    include_internal: bool,
    output: str,
):
    """Get the most recent chat session."""
    client = create_client()
    account_id = resolve_account_id(client, account)

    session = get_latest_chat_session(
        client,
        account_id=account_id,
        procedure_id=procedure_id,
        status=status,
        category=category,
    )
    if not session:
        console.print("[yellow]No chat sessions found for the requested filters.[/yellow]")
        return

    payload: Dict[str, Any] = {"accountId": account_id, "session": session}
    if messages_limit > 0:
        payload["messages"] = list_session_messages(
            client,
            session_id=session["id"],
            limit=messages_limit,
            offset=0,
            include_internal=include_internal,
        )

    if output == "table":
        _render(session, output)
        if "messages" in payload:
            _render_messages(payload["messages"], output)
        return
    _render(payload, output)


@chat.command("messages")
@click.option("--session-id", required=True, help="Chat session ID.")
@click.option("--limit", default=50, type=int, help="Maximum number of messages to return.")
@click.option("--offset", default=0, type=int, help="Offset into visible messages.")
@click.option("--include-internal", is_flag=True, help="Include INTERNAL messages.")
@click.option("--output", type=click.Choice(["table", "json", "yaml"]), default="table")
def chat_messages(
    session_id: str,
    limit: int,
    offset: int,
    include_internal: bool,
    output: str,
):
    """List chat session messages."""
    client = create_client()
    payload = list_session_messages(
        client,
        session_id=session_id,
        limit=limit,
        offset=offset,
        include_internal=include_internal,
    )
    _render_messages(payload, output)


@chat.command("send")
@click.option("--session-id", required=True, help="Chat session ID.")
@click.option("--text", required=True, help="Message content.")
@click.option("--mode", type=click.Choice(["chat", "response"]), default="chat", show_default=True)
@click.option("--parent-message-id", default=None, help="Required when mode=response.")
@click.option("--response-target", default="cloud", show_default=True)
@click.option("--model", default=None, help="Optional model id for mode=chat (stored in metadata.model.id).")
@click.option("--output", type=click.Choice(["table", "json", "yaml"]), default="table")
def chat_send(
    session_id: str,
    text: str,
    mode: str,
    parent_message_id: Optional[str],
    response_target: str,
    model: Optional[str],
    output: str,
):
    """Send a USER chat message or RESPONSE message."""
    if mode == "response" and not parent_message_id:
        raise click.ClickException("--parent-message-id is required when --mode response.")

    client = create_client()
    result = send_chat_message(
        client,
        session_id=session_id,
        text=text,
        mode=mode,
        parent_message_id=parent_message_id,
        response_target=response_target,
        model=model,
    )

    if output == "table":
        _render(result.get("message", {}), output)
        return
    _render(result, output)

