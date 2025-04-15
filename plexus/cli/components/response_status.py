"""
Plexus response status widget for the Textual UI.

This widget shows a visual indicator when the AI is responding,
with a loading animation and status text.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, LoadingIndicator


class ResponseStatus(Horizontal):
    """Widget that displays the current response status."""

    def __init__(self):
        """Initialize a new response status widget."""
        super().__init__()
        self.add_class("response-status")
        self.visible = False

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield LoadingIndicator()
        yield Static("Plexus is responding...", classes="status-text")

    def show_responding(self):
        """Show the responding indicator."""
        self.visible = True
        self.add_class("is-responding")

    def hide_responding(self):
        """Hide the responding indicator."""
        self.visible = False
        self.remove_class("is-responding") 