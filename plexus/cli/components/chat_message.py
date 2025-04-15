"""
Plexus chat message widget for the Textual UI.

This widget displays a single chat message with styling for user or assistant messages.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Label
from rich.markdown import Markdown
from rich.text import Text


class ChatMessage(Vertical):
    """A widget that displays a single chat message."""

    def __init__(self, sender: str, content: str, is_user: bool = False):
        """Initialize a new chat message.
        
        Args:
            sender: The name of the message sender
            content: The message content
            is_user: Whether this is a user message
        """
        super().__init__()
        self.sender = sender
        self.content = content
        self.is_user = is_user

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Add the appropriate CSS class based on the sender
        if self.is_user:
            self.add_class("user-message")
            border_title = "You"
        else:
            self.add_class("assistant-message")
            border_title = "Plexus"
        
        # For assistant messages, use rich markdown rendering
        # For user messages, we don't need markdown formatting
        if self.is_user:
            message_content = self.content
        else:
            # For assistant messages, use rich markdown rendering
            message_content = Markdown(self.content)
        
        # Create the message content with appropriate styling
        # Use the border title to show the sender name
        message = Static(message_content, classes="message-content")
        message.border_title = border_title
        message.expand = True  # Allow static to expand to show full content
        
        # Add a subtle sender label above the message
        yield Label(self.sender, classes="sender-label")
        yield message 