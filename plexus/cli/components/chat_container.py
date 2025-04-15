"""
Plexus chat container widget for the Textual UI.

This widget contains and manages all chat messages, providing proper scrolling behavior.
"""

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, VerticalScroll, Container
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, TextArea, Label

from .chat_message import ChatMessage
from .response_status import ResponseStatus


class ChatContainer(ScrollableContainer):
    """Container for displaying all chat messages with scrollable behavior."""

    DEFAULT_CSS = """
    ChatContainer {
        scrollbar-color: #5521b5;
        scrollbar-background: #272820;
        scrollbar-corner-color: #5521b5;
    }
    """

    def __init__(self):
        """Initialize a new chat container."""
        super().__init__()
        self.messages = []
        self.auto_scroll = True

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # This will be populated with messages
        with Container(id="message-list"):
            pass
        
        # Add the response status indicator
        yield ResponseStatus()

    def add_message(self, sender: str, content: str, is_user: bool = False):
        """Add a new message to the chat.
        
        Args:
            sender: The name of the message sender
            content: The message content
            is_user: Whether this is a user message
        """
        message = ChatMessage(sender, content, is_user)
        self.messages.append(message)
        self.query_one("#message-list").mount(message)
        
        # Scroll to the bottom after adding a message - no animation for immediate effect
        self.scroll_end(animate=False)
        
        # Schedule another scroll after a brief delay to ensure rendering is complete
        self.set_timer(0.1, self.force_scroll)

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        # Add a placeholder message to show how to use the chat
        self.add_message(
            "Plexus", 
            "Welcome to the Plexus Chat REPL! Type your message below and press Enter to send it.", 
            is_user=False
        )
        
        # Watch for screen refresh
        self.watch(self, "render_count", self.handle_render)

    def handle_render(self, render_count) -> None:
        """Called after the widget is rendered.
        
        This ensures scrolling happens after content changes.
        
        Args:
            render_count: The current render count
        """
        # Schedule a scroll after a brief delay to ensure rendering is complete
        self.set_timer(0.05, self.force_scroll)

    def scroll_end(self, animate: bool = False) -> None:
        """Scroll to the end of the container.
        
        Args:
            animate: Whether to animate the scrolling
        """
        if self.auto_scroll:
            # First try scrolling to the last widget
            if self.query_one("#message-list").children:
                last_widget = self.query_one("#message-list").children[-1]
                self.scroll_to_widget(last_widget, top=False, animate=animate)
            
            # Force scroll to the maximum value to ensure we're at the bottom
            self.scroll_y = self.max_scroll_y

    def on_screen_resume(self) -> None:
        """Called when the screen is resumed.
        
        This ensures scrolling happens after screen updates.
        """
        self.force_scroll()
    
    def force_scroll(self) -> None:
        """Force scroll to the bottom of the container.
        
        This is a more aggressive approach to ensure we're at the bottom.
        """
        # Calculate current max scroll position
        max_y = self.max_scroll_y
        
        # Set scroll position to maximum with some extra buffer
        self.scroll_y = max_y + 100  # Adding extra to ensure we get to the bottom