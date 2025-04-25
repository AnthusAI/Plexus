import importlib
import logging
from typing import Any, Dict, List, Optional, Tuple
import json
import asyncio # Added for async operations

# print("[DEBUG] service.py top level print") # DEBUG PRINT

import mistune
import yaml
import jinja2

# Import block classes dynamically or maintain a registry
# For now, let's import the known ones to start. Need a robust way later.
from plexus.reports import blocks
# Import API client and models
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.report_configuration import ReportConfiguration

# Configure logging
logger = logging.getLogger(__name__)


# --- Remove Mock Data Loading ---
# MOCK_CONFIGURATIONS = { ... } # Removed


async def _load_report_configuration(client: PlexusDashboardClient, config_id: str) -> Optional[ReportConfiguration]:
    """Loads a ReportConfiguration by its ID using the API client."""
    logger.info(f"Loading report configuration from API: {config_id}")
    try:
        # Use the get_by_id method from the ReportConfiguration model
        config = await asyncio.to_thread(ReportConfiguration.get_by_id, config_id, client)

        if config:
            logger.info(f"Successfully loaded configuration: {config_id}")
            return config
        else:
            logger.warning(f"ReportConfiguration with ID {config_id} not found.")
            return None
    except Exception as e:
        logger.exception(f"Error loading ReportConfiguration {config_id} from API: {e}")
        return None
# --- End Data Loading ---


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


async def generate_report(report_configuration_id: str, params: Optional[Dict[str, Any]] = None) -> str:
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

    # Initialize API Client (assumes credentials are set via env vars)
    # TODO: Consider if client should be passed in or instantiated differently
    api_client = PlexusDashboardClient()

    logger.info(f"Starting report generation for config ID: {report_configuration_id} with params: {params}")

    # === 1. Load ReportConfiguration ===
    # Use the actual loader function now
    report_config_model = await _load_report_configuration(api_client, report_configuration_id)

    # Handle case where config is not found
    if not report_config_model:
        logger.error(f"ReportConfiguration not found: {report_configuration_id}")
        # Raise the error so tests can catch it
        raise ValueError(f"ReportConfiguration not found: {report_configuration_id}")

    # Extract necessary info from the loaded config model
    config_markdown = report_config_model.configuration # Access the attribute directly
    report_config_name = report_config_model.name
    account_id = report_config_model.accountId # Get accountId from the model

    # === 2. TODO: Create Initial Report Record ===
    # Use account_id from the loaded config
    # report_name = f"Report for {report_config_name} - {datetime.utcnow()}" # Example name
    # initial_report_data = {
    #    "reportConfigurationId": report_configuration_id,
    #    "accountId": account_id, # Use actual account ID
    #    "name": report_name,
    #    "status": "RUNNING",
    #    "parameters": params,
    #    "startedAt": datetime.utcnow().isoformat() + "Z",
    # }
    # Use Report.create(...) here
    # created_report = await asyncio.to_thread(
    #     Report.create,
    #     client=api_client,
    #     reportConfigurationId=report_configuration_id,
    #     accountId=account_id,
    #     name=report_name,
    #     parameters=params,
    #     status='RUNNING'
    # )
    # report_id = created_report.id

    # Placeholder report ID
    report_id = f"report-{report_configuration_id}-run1"
    logger.info(f"Created initial Report record (mock): {report_id}")

    try:
        # === 3. Parse Configuration ===
        # The markdown content comes from the loaded model
        template_content_string, block_definitions = _parse_report_configuration(config_markdown)

        # === 4. Process Report Blocks (Before Rendering Template) ===
        block_outputs = {} # Store block outputs keyed by name (or position?)
        block_logs = {} # Store block logs separately
        # List to hold created ReportBlock model instances (or data to create them)
        report_block_records = []
        all_blocks_succeeded = True

        for position, block_def in enumerate(block_definitions):
            block_def['position'] = position # Ensure position is set
            # Use the block's name from the definition if available, otherwise use position
            block_name = block_def.get('name', f'block_{position}')
            logger.info(f"Processing block {position}: {block_name}")

            # Instantiate and run the block (remains synchronous for now)
            # TODO: Consider if _instantiate_and_run_block should also be async if blocks do I/O
            block_output_json, block_log_str = _instantiate_and_run_block(
                block_def, report_params=params
            )

            # --- 5. TODO: Create ReportBlock Record (In Memory or Directly to DB) ---
            if block_output_json is not None:
                block_outputs[block_name] = block_output_json # Still useful for context if needed later
                # Prepare data for ReportBlock creation
                report_block_data = {
                    "reportId": report_id, # Link to the parent report
                    "name": block_name,
                    "position": position,
                    "output": block_output_json, # Store the JSON output
                    "log": block_log_str
                }
                report_block_records.append(report_block_data)
                # Option 1: Create immediately (might be slow if many blocks)
                # await asyncio.to_thread(
                #     ReportBlock.create,
                #     client=api_client,
                #     **report_block_data
                # )
                # Option 2: Collect and batch create later (preferred)

                if block_log_str:
                    block_logs[block_name] = block_log_str
            else:
                all_blocks_succeeded = False
                logger.error(f"Block {position} ({block_name}) failed to generate output.")
                # Store error information? Maybe update the Report record?
                # TODO: Create ReportBlock record even on failure?
                # ReportBlock.create(..., status='FAILED', log=block_log_str or "Unknown error") ?

        # === 6. TODO: Batch Create ReportBlock Records ===
        # if report_block_records:
        #     # Use ReportBlock.batch_create(...) if implemented, or loop create
        #     logger.info(f"Creating {len(report_block_records)} ReportBlock records...")
        #     # await ReportBlock.batch_create(client=api_client, items=report_block_records) # Ideal
        #     # Fallback: Loop create (less efficient)
        #     for record_data in report_block_records:
        #         try:
        #             await asyncio.to_thread(ReportBlock.create, client=api_client, **record_data)
        #         except Exception as block_create_err:
        #             logger.error(f"Failed to create ReportBlock for {record_data.get('name')}: {block_create_err}")


        # === 7. Finalize Report Record ===
        final_status = 'COMPLETED' if all_blocks_succeeded else 'FAILED' # Or 'PARTIAL'?
        logger.info(f"Report generation finished. Final status: {final_status}")

        # Update the main Report record with the final status, completion time, and the *original* markdown
        # report_update_data = {
        #    "status": final_status,
        #    "output": template_content_string, # Store the original Markdown per plan
        #    "completedAt": datetime.utcnow().isoformat() + "Z",
        # }
        # if not all_blocks_succeeded:
        #    report_update_data["errorMessage"] = "One or more report blocks failed to generate."
        #    # report_update_data["errorDetails"] = json.dumps(block_logs or {"detail": "See block logs"})
        
        # Fetch the report object if created earlier, then call update
        # report_obj = await asyncio.to_thread(Report.get_by_id, report_id, api_client)
        # if report_obj:
        #     await asyncio.to_thread(report_obj.update, **report_update_data)
        # else:
        #     logger.error(f"Could not find Report {report_id} to update final status.")

        # Return the (mock) report ID for now
        return report_id

    except ValueError as ve: # Catch specific config-not-found error
        logger.error(f"Configuration loading failed: {ve}")
        # TODO: Update Report status to FAILED if it was created
        raise # Re-raise the ValueError
    except Exception as e:
        logger.exception(f"Unhandled error during report generation for config {report_configuration_id}: {e}")
        # --- TODO: Update Report record to FAILED status ---
        # report_obj = await asyncio.to_thread(Report.get_by_id, report_id, api_client)
        # if report_obj:
        #     await asyncio.to_thread(
        #         report_obj.update,
        #         status='FAILED',
        #         errorMessage=f"Unhandled exception: {type(e).__name__}",
        #         errorDetails=traceback.format_exc(),
        #         completedAt=datetime.utcnow().isoformat() + "Z"
        #     )
        # else:
        #     logger.error(f"Could not find Report {report_id} to mark as FAILED after exception.")
        raise # Re-raise the exception


# --- Helper: Parse Configuration ---
# Takes the raw Markdown string from the ReportConfiguration.configuration field
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

def _instantiate_and_run_block(block_def: dict, report_params: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Instantiates and runs a specific ReportBlock Python class.

    Args:
        block_def: Dictionary containing 'class_name', 'config', 'name', 'position'.
        report_params: Global parameters passed to the report run.

    Returns:
        A tuple containing:
            - JSON string of the block's output data (or None on failure).
            - String containing logs/messages from the block's execution (or None).
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