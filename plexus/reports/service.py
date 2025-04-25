import importlib
import logging
from typing import Any, Dict, List, Optional

# print("[DEBUG] service.py top level print") # DEBUG PRINT

import mistune
import yaml

# Import block classes dynamically or maintain a registry
# For now, let's import the known ones to start. Need a robust way later.
from plexus.reports import blocks

# Configure logging
logger = logging.getLogger(__name__)


# --- Mock Data Loading ---
# In a real implementation, this would fetch from the database
MOCK_CONFIGURATIONS = {
    "config-1": {
        "id": "config-1",
        "name": "Sample Score Report",
        "configuration": """
# Sample Score Report

This report shows detailed information about a specific score.

```block
pythonClass: ScoreInfoBlock
config:
  scoreId: "score-abc-123"
  include_variant: true
```

Here is some concluding text after the block.
"""
    }
}

def _load_report_configuration(config_id: str) -> Optional[Dict[str, Any]]:
    """ Mocks loading a ReportConfiguration by its ID. """
    logger.info(f"Loading mock report configuration: {config_id}")
    # print(f"[DEBUG] Loading mock report configuration: {config_id}") # DEBUG PRINT
    return MOCK_CONFIGURATIONS.get(config_id)
# --- End Mock Data Loading ---


# --- Block Processing Logic ---

# TODO: Implement a more robust block class discovery/registry mechanism
# For now, access loaded modules via plexus.reports.blocks
BLOCK_CLASSES = {
    name: cls for name, cls in blocks.__dict__.items() if isinstance(cls, type) and issubclass(cls, blocks.BaseReportBlock) and cls is not blocks.BaseReportBlock
}

class ReportBlockExtractor(mistune.BaseRenderer):
    # Name is required for BaseRenderer
    name = "report_block_extractor"
    
    def __init__(self):
        # No super().__init__() call needed for BaseRenderer typically
        self.extracted_content = []
        self._current_markdown_buffer = ""
        # Keep track of the state during parsing
        self._parse_state = None 

    def _flush_markdown_buffer(self):
        if self._current_markdown_buffer:
            self.extracted_content.append(
                {"type": "markdown", "content": self._current_markdown_buffer.strip()}
            )
            self._current_markdown_buffer = ""

    # --- Custom Rendering Methods ---
    # Override methods for tokens we want to handle differently

    def text(self, token, state):
        self._current_markdown_buffer += token["raw"]
        return token["raw"]

    def paragraph(self, token, state):
        # Instead of rendering <p>, just accumulate the inner text
        # We might lose some structure here, but it avoids the default HTML
        inner_text = self.render_tokens(token["children"], state)
        # Add paragraph breaks for potentially better formatting later
        self._current_markdown_buffer += inner_text + "\n\n" 
        return inner_text # Return value might not be used if we capture directly

    def block_code(self, token, state):
        lang = token["attrs"].get("info") if token.get("attrs") else None
        lang = lang.strip() if lang else None
        code = token["raw"]

        if lang == "block":
            self._flush_markdown_buffer() # Add preceding Markdown first
            try:
                block_config = yaml.safe_load(code)
                if not isinstance(block_config, dict):
                    raise ValueError("Block YAML must be a dictionary.")
                
                class_name = block_config.get("pythonClass")
                block_params = block_config.get("config", {})

                if not class_name:
                     raise ValueError("`pythonClass` not specified in block YAML.")

                self.extracted_content.append({
                    "type": "block_config",
                    "class_name": class_name,
                    "config": block_params
                })
                # Return empty string as this block shouldn't render HTML
                return ""

            except (yaml.YAMLError, ValueError) as e:
                logger.error(f"Error parsing report block YAML: {e}\nYAML:\n{code}")
                self.extracted_content.append({
                     "type": "error",
                     "message": f"Error parsing block: {e}"
                })
                # Return an error message or empty string
                return "<!-- Error parsing block -->"
        else:
            # For non-'block' code blocks, maybe render as plain text or use default?
            # For now, just add to the markdown buffer.
            rendered_code = f"```{(lang or '')}\n{code}\n```\n"
            self._current_markdown_buffer += rendered_code
            return rendered_code # Return the formatted code

    # Handle other elements by accumulating their raw content or rendering children
    # We might need to add more handlers (heading, list, etc.) 
    # if we want to preserve more structure in the markdown parts.
    def heading(self, token, state):
        level = token["attrs"]["level"]
        inner_text = self.render_tokens(token["children"], state)
        md_header = '#' * level + ' ' + inner_text + '\n\n'
        self._current_markdown_buffer += md_header
        return md_header

    def render_tokens(self, tokens, state):
        # Helper to render child tokens
        result = ""
        for tok in tokens:
            # Dynamically call the method based on token type
            method = getattr(self, tok["type"], None)
            if method:
                result += method(tok, state)
            elif "raw" in tok: # Fallback for unhandled tokens with raw text
                result += tok["raw"]
        return result

    def finalize(self, data):
         # This method is called at the end by BaseRenderer
         # Flush any remaining buffer content
         self._flush_markdown_buffer()
         # Filter out empty markdown sections
         return [
            item for item in self.extracted_content 
            if item.get("type") != "markdown" or item.get("content")
         ]

# --- End Block Processing Logic ---


def generate_report(report_configuration_id: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Generates report data based on a ReportConfiguration ID.

    1. Loads the ReportConfiguration (currently mocked).
    2. Parses the Markdown configuration content.
    3. Extracts static Markdown and block definitions (YAML).
    4. Instantiates and runs the specified ReportBlocks.
    5. Assembles the results into a list representing the report structure.

    Args:
        report_configuration_id: The ID of the ReportConfiguration to use.
        params: Optional runtime parameters to pass to blocks.

    Returns:
        A list representing the structured report data. Each item is a dict,
        e.g., {"type": "markdown", "content": "..."} or 
        {"type": "block_result", "block_type": "ScoreInfo", "data": {...}}.
        Returns an empty list if the configuration is not found or parsing fails severely.
    """
    report_config = _load_report_configuration(report_configuration_id)
    if not report_config:
        logger.error(f"ReportConfiguration not found: {report_configuration_id}")
        # print(f"[DEBUG] ReportConfiguration not found: {report_configuration_id}") # DEBUG PRINT
        return [] # Or raise an exception

    markdown_content = report_config.get("configuration", "")
    if not markdown_content:
        logger.warning(f"ReportConfiguration {report_configuration_id} has no content.")
        # print(f"[DEBUG] ReportConfiguration {report_configuration_id} has no content.") # DEBUG PRINT
        return []

    logger.info(f"Parsing report configuration: {report_configuration_id}")
    # print(f"[DEBUG] Parsing report configuration: {report_configuration_id}") # DEBUG PRINT
    
    # Instantiate the custom renderer
    renderer_instance = ReportBlockExtractor()
    # Create mistune instance using the renderer instance
    md = mistune.create_markdown(renderer=renderer_instance)
    # Parse the content - this triggers the renderer methods
    md.parse(markdown_content) 
    # Get the final processed data from the renderer instance
    parsed_structure = renderer_instance.finalize(None) 

    # print(f"[DEBUG] Parsed structure: {parsed_structure}") # DEBUG PRINT

    report_data = []
    for item in parsed_structure:
        if item["type"] == "markdown":
            report_data.append(item)
        elif item["type"] == "block_config":
            class_name = item["class_name"]
            block_config_params = item["config"]
            
            BlockClass = BLOCK_CLASSES.get(class_name)
            
            if not BlockClass:
                logger.error(f"ReportBlock class '{class_name}' not found.")
                # print(f"[DEBUG] ReportBlock class '{class_name}' not found.") # DEBUG PRINT
                report_data.append({
                    "type": "error", 
                    "message": f"Block class '{class_name}' not found."
                })
                continue

            try:
                block_instance = BlockClass()
                logger.info(f"Generating block: {class_name} with config: {block_config_params}")
                # print(f"[DEBUG] Generating block: {class_name} with config: {block_config_params}") # DEBUG PRINT
                # Pass both the block-specific config and optional runtime params
                block_result = block_instance.generate(config=block_config_params, params=params)
                # print(f"[DEBUG] Block result: {block_result}") # DEBUG PRINT
                
                # Structure the result - assuming generate() returns the data payload directly
                # The block itself can define its 'type' if needed, like ScoreInfoBlock did
                report_data.append({
                    "type": "block_result",
                    # Use result type if available, else use class name
                    "block_type": block_result.get("type", class_name) if isinstance(block_result, dict) else class_name, 
                    "data": block_result
                })

            except Exception as e:
                logger.exception(f"Error generating block '{class_name}': {e}")
                # print(f"[DEBUG] Error generating block '{class_name}': {e}") # DEBUG PRINT
                report_data.append({
                    "type": "error", 
                    "message": f"Error running block '{class_name}': {e}"
                })
        
        elif item["type"] == "error":
             # Propagate parsing errors
             report_data.append(item)


    logger.info(f"Report generation completed for config: {report_configuration_id}")
    # print(f"[DEBUG] Report generation completed for config: {report_configuration_id}") # DEBUG PRINT
    return report_data


# Example usage (for testing):
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = generate_report("config-1")
    import json
    print(json.dumps(result, indent=2))

    # Example with a non-existent block
    # MOCK_CONFIGURATIONS["config-err"] = { ... add config with bad class ... }
    # result_err = generate_report("config-err")
    # print(json.dumps(result_err, indent=2)) 