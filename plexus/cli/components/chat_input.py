"""
Plexus chat input widget for the Textual UI.

This widget provides a text area for user input with a send button.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import TextArea, Button
from textual.binding import Binding
from textual import events


class ChatInput(Horizontal):
    """Widget for chat input with text area and send button."""
    
    BINDINGS = [
        Binding("ctrl+enter", "submit", "Send Message", show=True),
    ]
    
    DEFAULT_CSS = """
    ChatInput {
        layout: horizontal;
        width: 100%;
        height: auto;
        padding: 0 2;
    }
    
    #message-input {
        width: 9fr;
        margin-right: 1;
    }
    
    #send-button {
        width: 1fr;
        height: 3;
        background: #5521b5;
        color: white;
        border: none;
    }
    """
    
    def __init__(self):
        """Initialize a new chat input widget."""
        super().__init__()
        self.add_class("chat-input")
    
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Create a multiline text area for input
        text_area = TextArea(
            text="", 
            id="message-input",
            classes="message-input"
        )
        yield text_area
        
        # Add a send button
        yield Button("Send", variant="primary", id="send-button")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "send-button":
            await self.action_submit()
    
    async def action_submit(self) -> None:
        """Submit the current message."""
        text_area = self.query_one("#message-input", TextArea)
        message = text_area.text
        
        if message.strip():
            # Post a message event that the parent app can handle
            self.post_message(self.SubmitMessage(message))
            text_area.clear()
    
    class SubmitMessage(events.Message):
        """Event sent when a message is submitted."""
        
        def __init__(self, message: str) -> None:
            """Initialize the event with the message text.
            
            Args:
                message: The message text that was submitted
            """
            super().__init__()
            self.message = message 