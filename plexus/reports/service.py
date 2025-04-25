import importlib
import logging
from typing import Any, Dict, List, Optional, Tuple
import json

# print("[DEBUG] service.py top level print") # DEBUG PRINT

import mistune
import yaml
import jinja2

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


def generate_report(report_configuration_id: str, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Generates a report based on a ReportConfiguration and optional parameters.

    Args:
        report_configuration_id: The ID of the ReportConfiguration to use.
        params: Optional dictionary of parameters to use for this specific run.

    Returns:
        The ID of the generated Report record. 
        (Or potentially raise an exception on failure).
    """
    if params is None:
        params = {}

    logger.info(f"Starting report generation for config ID: {report_configuration_id} with params: {params}")

    # === 1. Load ReportConfiguration ===
    # Call the helper function, which can be mocked by tests.
    # The helper function itself currently returns mock data.
    report_config = _load_report_configuration(report_configuration_id)
    
    # Handle case where config is not found
    if not report_config:
        logger.error(f"ReportConfiguration not found: {report_configuration_id}")
        # Raise the error so tests can catch it
        raise ValueError(f"ReportConfiguration not found: {report_configuration_id}")

    # Extract necessary info from the loaded config
    config_markdown = report_config.get("configuration", "")
    report_config_name = report_config.get("name", f"Unnamed Config {report_configuration_id}")
    # TODO: Get accountId from report_config when using real data
    # account_id = report_config.get("accountId") 

    # Placeholder for loaded config data:
    # mock_config_markdown = f"""
    # # Mock Report for {report_configuration_id}
    # 
    # This report uses parameters: {params}
    # 
    # ```block name="Test Score Info"
    # class: ScoreInfo
    # config:
    #   score: "mock-score-123" 
    #   include_variant: true
    # ```
    # """
    # config_markdown = mock_config_markdown # Use mock data for now
    # report_config_name = f"Mock Config {report_configuration_id[:4]}" # Mock name

    # === 2. TODO: Create Initial Report Record ===
    # report_name = f"Report for {report_config_name} - {datetime.utcnow()}" # Example name
    # initial_report_data = {
    #    "reportConfigurationId": report_configuration_id,
    #    "accountId": report_config.accountId, # Assuming accountId is available
    #    "name": report_name,
    #    "status": "RUNNING",
    #    "parameters": params,
    #    "startedAt": datetime.utcnow().isoformat() + "Z",
    # }
    # created_report = client.create_report(initial_report_data)
    # report_id = created_report.id
    
    # Placeholder report ID
    report_id = f"report-{report_configuration_id}-run1" 
    logger.info(f"Created initial Report record (mock): {report_id}")

    try:
        # === 3. Parse Configuration ===
        # This step extracts the main template structure and the block definitions.
        # The `_parse_report_configuration` function needs to return both.
        template_content_string, block_definitions = _parse_report_configuration(config_markdown)

        # === 4. Process Report Blocks (Before Rendering Template) ===
        block_outputs = {} # Store block outputs keyed by name (or position?)
        block_logs = {} # Store block logs separately
        all_blocks_succeeded = True

        for position, block_def in enumerate(block_definitions):
            block_def['position'] = position # Ensure position is set
            # Use the block's name from the definition if available, otherwise use position
            block_name = block_def.get('name', f'block_{position}') 
            logger.info(f"Processing block {position}: {block_name}")

            # Execute the block
            # TODO: Pass actual report_params if needed by blocks
            block_output_json, block_log_str = _instantiate_and_run_block(block_def, params) 
            
            # Store results for Jinja context and for DB record
            if block_output_json is not None:
                try:
                    # Store the parsed JSON data for Jinja context
                    block_outputs[block_name] = json.loads(block_output_json) 
                except json.JSONDecodeError:
                     logger.error(f"Block {position} ('{block_name}') produced invalid JSON output.")
                     block_outputs[block_name] = {"error": "Invalid JSON output from block."}
                     all_blocks_succeeded = False
            else:
                 all_blocks_succeeded = False
                 logger.warning(f"Block {position} ('{block_name}') failed or produced no output.")
                 # Store an error indicator in the output map for Jinja? 
                 block_outputs[block_name] = {"error": f"Block execution failed or produced no output."}

            block_logs[block_name] = block_log_str

            # === 5. TODO: Create ReportBlock Record ===
            # This should happen *inside* the loop, after each block runs.
            # block_record_data = {
            #     "reportId": report_id,
            #     "name": block_name, # Use the determined name
            #     "position": position,
            #     "output": block_output_json, # Store the raw JSON string
            #     "log": block_log_str, 
            # }
            # created_block = client.create_report_block(block_record_data)
            # logger.debug(f"Stored DB result for block {position}.")
            # Mock storing result for now
            logger.debug(f"Mock storing result for block {position} ('{block_name}').")
            
            # TODO: Consider error handling - stop processing? Mark report as failed?

        # === 6. Render Main Template (After Processing Blocks) ===
        logger.debug("Rendering main Jinja2 template...")
        try:
            jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined) # Fail on undefined variables
            template = jinja_env.from_string(template_content_string)
            
            # Define context for Jinja rendering
            render_context = {
                "params": params, # Report run parameters
                "metadata": { # Information about the report itself
                    "report_id": report_id, 
                    "config_id": report_configuration_id,
                    "config_name": report_config_name # Mocked for now
                },
                "blocks": block_outputs # The collected outputs from the blocks
            }
            final_report_output = template.render(render_context)
            logger.debug("Main template rendered successfully.")
        except jinja2.exceptions.TemplateError as e:
            logger.error(f"Jinja2 template rendering failed: {e}")
            # Mark report as failed if template rendering fails
            all_blocks_succeeded = False
            final_report_output = f"<!-- Report Generation Error: Template rendering failed: {e} -->"
            # TODO: Update report status and error message in DB immediately?

        # === 7. TODO: Update Final Report Record ===
        final_status = "COMPLETED" if all_blocks_succeeded else "FAILED" # Or COMPLETED_WITH_ERRORS?
        # final_report_update = {
        #     "id": report_id,
        #     "status": final_status,
        #     "output": final_report_output,
        #     "completedAt": datetime.utcnow().isoformat() + "Z",
        #     # TODO: Add errorMessage/errorDetails if needed
        # }
        # client.update_report(final_report_update)
        logger.info(f"Report generation finished. Final status (mock): {final_status}")
        logger.info(f"""Final Report Output (mock):
{final_report_output}""")
        logger.info(f"Block Results (mock): {json.dumps(block_outputs, indent=2)}")

    except Exception as e:
        logger.exception(f"Report generation failed for config {report_configuration_id}: {e}")
        # === 8. TODO: Update Report Record on Failure ===
        # error_update = {
        #     "id": report_id,
        #     "status": "FAILED",
        #     "errorMessage": str(e),
        #     "errorDetails": traceback.format_exc(), # Optional detailed traceback
        #     "completedAt": datetime.utcnow().isoformat() + "Z",
        # }
        # client.update_report(error_update)
        # Re-raise the exception? Or return a specific failure indicator?
        raise 

    return report_id # Return the ID of the generated report


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

# Placeholder for Report Block parsing result
ReportBlockDefinition = Dict[str, Any] 

def _parse_report_configuration(config_markdown: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parses the report configuration Markdown/Jinja2 string.

    Uses mistune with a custom renderer (ReportBlockExtractor) to identify
    Markdown sections and fenced code blocks marked with 'block'. It extracts
    the block definitions for execution but leaves the original block syntax
    intact in the returned markdown string.

    Args:
        config_markdown: The raw string content from ReportConfiguration.configuration.

    Returns:
        A tuple containing:
        - The original markdown string, suitable for storing in Report.output.
        - A list of block definition dictionaries, each containing details
          like 'class_name', 'config', 'name' (optional), and 'position',
          extracted for execution.
    """
    logger.info("Parsing report configuration markdown...")
    # print("[DEBUG] Parsing report configuration markdown...") # DEBUG PRINT

    # Initialize the mistune Markdown parser with our custom extractor
    markdown_parser = mistune.create_markdown(renderer=ReportBlockExtractor())

    # Parse the input markdown. The extractor's finalize method returns the list.
    parsed_items = markdown_parser(config_markdown)

    # print(f"[DEBUG] Parsed items from extractor: {parsed_items}") # DEBUG PRINT

    main_template_parts = []
    block_definitions = []
    block_counter = 0 # Used for position and default naming

    for item in parsed_items:
        item_type = item.get("type")
        # print(f"[DEBUG] Processing parsed item: {item}") # DEBUG PRINT

        if item_type == "markdown":
            main_template_parts.append(item.get("content", ""))
        elif item_type == "block_config":
            class_name = item.get("class_name")
            config = item.get("config", {})
            # Determine the name: use 'name' from config if present, else generate default
            # We need the name *before* potentially removing it from the config for the definition
            name = config.get("name", f"block_{block_counter}")

            # Create the block definition for execution later
            # Keep the original config structure as parsed by the extractor
            block_def = {
                "class_name": class_name,
                "config": config, # Store the original config dict
                "name": name, # Store the determined/generated name
                "position": block_counter, # Positional index
            }
            block_definitions.append(block_def)

            # Reconstruct the original block definition string for the output markdown
            # Combine class_name and config back into a dictionary for dumping
            original_block_content_dict = {"pythonClass": class_name}
            if config: # Only add 'config' key if it's not empty
                original_block_content_dict["config"] = config
                
            # Dump back to YAML format, trying to preserve original style somewhat
            # Using default_flow_style=False for block style YAML
            # indent=2 for readability
            try:
                reconstructed_yaml = yaml.dump(original_block_content_dict, default_flow_style=False, indent=2, sort_keys=False)
                # Strip trailing newline added by dump if present
                reconstructed_yaml = reconstructed_yaml.strip()
            except yaml.YAMLError:
                # Fallback if dumping fails (should be rare)
                reconstructed_yaml = f"pythonClass: {class_name}\\nconfig: Error reconstructing YAML"

            # Append the reconstructed ```block ... ``` string to the template parts
            reconstructed_block_string = f"```block\\n{reconstructed_yaml}\\n```"
            main_template_parts.append(reconstructed_block_string)

            block_counter += 1
        elif item_type == "error":
            # Include errors in the template output as comments for debugging
            # Also add the error message to the block definitions list?
            # For now, just log and put comment in markdown.
            error_message = item.get('message', 'Unknown parsing error')
            logger.warning(f"Found parsing error in configuration: {error_message}")
            main_template_parts.append(f"<!-- PARSE ERROR: {error_message} -->")
            # Optionally, add an error block definition
            # block_definitions.append({
            #     "type": "error",
            #     "message": error_message,
            #     "position": block_counter
            # })
            # block_counter += 1 # Increment even for errors?
        else:
            logger.warning(f"Ignoring unexpected parsed item type: {item_type}")

    # Join the template parts together
    # Use two newlines to separate parts, mimicking original paragraph/block spacing
    final_markdown_string = "\\n\\n".join(main_template_parts).strip()
    # print(f"[DEBUG] Final reconstructed markdown string:\\n{final_markdown_string}") # DEBUG PRINT
    # print(f"[DEBUG] Final block definitions: {block_definitions}") # DEBUG PRINT

    logger.info(f"Parsed configuration: Found {len(block_definitions)} blocks. Markdown reconstructed.")
    # NOTE: The first returned string is now the reconstructed original markdown,
    # NOT a Jinja template string.
    return final_markdown_string, block_definitions

def _instantiate_and_run_block(block_def: ReportBlockDefinition, report_params: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Instantiates and runs a single report block based on its definition.

    Args:
        block_def: The definition of the block to instantiate and run.
                   Expected keys: 'class_name', 'config', 'name', 'position'.
        report_params: Global parameters passed to the report generation run.

    Returns:
        A tuple containing:
        - The output dictionary from the block, serialized to a JSON string, 
          or None if the block failed or produced no dictionary output.
        - The log string captured during block execution (currently not implemented 
          in BaseReportBlock, so will likely be None), or an error message string 
          if instantiation/generation failed.
    """
    class_name = block_def.get("class_name")
    block_config = block_def.get("config", {})
    block_name = block_def.get("name", f"block_{block_def.get('position', 'unknown')}")
    logger.info(f"Attempting to instantiate and run block '{block_name}' (Class: {class_name})")

    output_json_str: Optional[str] = None
    log_str: Optional[str] = None

    try:
        # 1. Find the block class
        block_class = BLOCK_CLASSES.get(class_name)
        if block_class is None:
            raise ValueError(f"Report block class '{class_name}' not found in registry.")

        # 2. Instantiate the block class
        # Add error handling for instantiation if needed (e.g., __init__ fails)
        block_instance = block_class()
        logger.debug(f"Instantiated block class '{class_name}'")

        # 3. Call the generate method
        # TODO: Implement log capturing if blocks support returning logs
        # For now, BaseReportBlock.generate only returns the output dict.
        # We expect a dictionary here based on BaseReportBlock definition.
        output_dict = block_instance.generate(config=block_config, params=report_params)

        # 4. Validate and Serialize the output
        if output_dict is None:
             logger.warning(f"Block '{block_name}' ({class_name}) returned None output.")
             # Treat None output as non-failure, but store null in DB?
             # For now, serialize None as JSON 'null'. Service layer handles None return.
             output_json_str = json.dumps(None) 
             log_str = "Block returned None."
        elif not isinstance(output_dict, dict):
             # This shouldn't happen if blocks adhere to BaseReportBlock
             logger.error(f"Block '{block_name}' ({class_name}) generate() did not return a dictionary. Returned type: {type(output_dict)}")
             raise TypeError("Block generate() must return a dictionary.")
        else:
             # Serialize the dictionary to JSON
             output_json_str = json.dumps(output_dict, indent=2) # Pretty print for readability
             logger.debug(f"Block '{block_name}' generated output successfully.")
             # log_str = output.get("_log") # Example if logs were part of dict

    except Exception as e:
        logger.exception(f"Error running report block '{block_name}' ({class_name}): {e}")
        # Return None for output, and the error message as the log string
        output_json_str = None
        log_str = f"Error executing block '{block_name}': {e}"

    # Return the JSON string and the log/error string
    return output_json_str, log_str 