"""
Plexus tool output widget for the Textual UI.

This widget displays the input and output of tool executions with proper formatting.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Label, Pretty
from textual.reactive import reactive
import json


class ToolOutput(Vertical):
    """Widget for displaying tool outputs."""
    
    DEFAULT_CSS = """
    ToolOutput {
        margin: 1;
        width: 90%;
    }
    
    .tool-output-header {
        background: #333333;
        color: white;
        padding: 0 1;
    }
    
    .tool-output-content {
        background: #222222;
        color: #888888;
        padding: 1;
        height: auto;
        overflow: auto;
    }
    """
    
    def __init__(self):
        """Initialize a new tool output widget."""
        super().__init__()
        self.add_class("tool-output")
        self.display = False
    
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield Static("Tool", classes="tool-output-header")
            yield Static("", classes="tool-output-content")
    
    def update_output(self, tool_name: str, input_str: str, output: str = None):
        """Update the tool output display.
        
        Args:
            tool_name: The name of the tool
            input_str: The input to the tool
            output: The output from the tool (if available)
        """
        # Display the widget
        self.display = True
        
        # Update the header
        try:
            header = self.query("Static.tool-output-header").first()
            header.update(f"Tool: {tool_name}")
        except Exception as e:
            print(f"Error updating header: {e}")
        
        # Format the input data nicely
        if isinstance(input_str, dict):
            input_text = "\n".join(f"  {k}: {v}" for k, v in input_str.items())
        else:
            input_text = str(input_str)
        
        # Escape any markup that might cause parsing errors
        def escape_markup(text: str) -> str:
            """Escape any markup characters that might cause parsing errors."""
            if text is None:
                return ""
            # Escape markup characters by replacing them with their escaped equivalents
            return text.replace("[", "\\[").replace("]", "\\]")
        
        # Apply the escaping to input and output
        input_text = escape_markup(input_text)
        escaped_output = escape_markup(output) if output else None
        
        # Create the content
        content = f"Input:\n{input_text}"
        if escaped_output:
            content += f"\n\nOutput:\n{escaped_output}"
        
        # Update the content
        try:
            content_widget = self.query("Static.tool-output-content").first()
            content_widget.update(content)
        except Exception as e:
            print(f"Error updating content: {e}")
    
    def set_output(self, output: str):
        """Add the output from a tool.
        
        Args:
            output: The output from the tool
        """
        if not self.display:
            return
        
        # Escape any markup that might cause parsing errors
        def escape_markup(text: str) -> str:
            """Escape any markup characters that might cause parsing errors."""
            if text is None:
                return ""
            # Escape markup characters by replacing them with their escaped equivalents
            return text.replace("[", "\\[").replace("]", "\\]")
        
        # Apply the escaping to output
        escaped_output = escape_markup(output)
        
        # Get the current content
        try:
            content_widget = self.query("Static.tool-output-content").first()
            
            # Add the output to the existing content
            current_content = content_widget.render()
            if "Output:" in current_content:
                # There's already output, update it
                parts = current_content.split("Output:")
                content_widget.update(f"{parts[0]}Output:\n{escaped_output}")
            else:
                # No output yet, add it
                content_widget.update(f"{current_content}\n\nOutput:\n{escaped_output}")
        except Exception as e:
            print(f"Error setting output: {e}")
    
    def clear(self):
        """Clear the tool output display."""
        self.display = False
        
        # Clear the header and content
        try:
            header = self.query("Static.tool-output-header").first()
            header.update("Tool")
            
            content_widget = self.query("Static.tool-output-content").first()
            content_widget.update("")
        except Exception as e:
            print(f"Error clearing tool output: {e}") 