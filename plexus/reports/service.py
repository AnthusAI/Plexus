import importlib
import logging
from typing import Any, Dict, List, Optional, Tuple
import json
import asyncio # Added for async operations
from datetime import datetime, timezone # Added datetime
import traceback # Added for error details
import re

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
from plexus.dashboard.api.models.report import Report # Added Report model
from plexus.dashboard.api.models.report_block import ReportBlock # Import ReportBlock for later

# Configure logging
logger = logging.getLogger(__name__)


# --- Remove Mock Data Loading ---
# MOCK_CONFIGURATIONS = { ... } # Removed


async def _load_report_configuration(client: PlexusDashboardClient, config_id: str) -> Optional[ReportConfiguration]:
    """Loads a ReportConfiguration by its ID using the API client."""
    logger.info(f"Loading report configuration from API: {config_id}")
    try:
        # Use the get_by_id method from the ReportConfiguration model
        # Assuming ReportConfiguration.get_by_id uses client.execute which is synchronous
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

    # === 2. Create Initial Report Record ===
    # This happens BEFORE block processing, making the ID available.
    created_report: Optional[Report] = None # Initialize to None
    report_id: Optional[str] = None
    try:
        # Generate a unique name for the report run
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        report_name = f"{report_config_name} - {timestamp}"

        logger.info(f"Creating initial Report record: {report_name}")
        # Assuming Report.create uses client.execute which is synchronous
        created_report = await asyncio.to_thread(
            Report.create,
            client=api_client,
            reportConfigurationId=report_configuration_id,
            accountId=account_id,
            name=report_name,
            parameters=params, # Pass runtime parameters
            status='RUNNING' # Start in RUNNING state
            # startedAt is handled by the model/backend? Check Report.create impl.
        )
        report_id = created_report.id
        logger.info(f"Successfully created initial Report record with ID: {report_id}")

    except Exception as create_err:
        logger.exception(f"Failed to create initial Report record for config {report_configuration_id}: {create_err}")
        # If we can't even create the initial record, we can't proceed.
        raise # Re-raise the exception to indicate catastrophic failure.

    # Make sure we have a report_id before proceeding
    if not report_id or not created_report:
         # This case should ideally be covered by the exception above, but as a safeguard:
         error_msg = "Failed to create or retrieve ID for the initial Report record."
         logger.error(error_msg)
         raise RuntimeError(error_msg)


    # --- Main processing block with final status update ---
    final_status = 'UNKNOWN' # Default status
    error_message = None
    error_details = None
    template_content_string = None # Initialize here

    try:
        # === 3. Parse Configuration ===
        # Make sure config_markdown is available
        if not config_markdown:
             raise ValueError("Report configuration markdown content is empty.")

        template_content_string, block_definitions = _parse_report_configuration(config_markdown)

        # === 4. Process Report Blocks (and create records sequentially) ===
        block_outputs = {}
        block_logs = {}
        all_blocks_succeeded = True # Tracks successful block *execution*
        all_block_records_created = True # Tracks successful block *record creation*

        for position, block_def in enumerate(block_definitions):
            # Ensure position is assigned to the definition itself for use in _instantiate_and_run_block if needed
            block_def['position'] = position 
            block_name = block_def.get('name', f'block_{position}')
            logger.info(f"Processing block {position}: {block_name}")

            block_output_json = None # Initialize for this block iteration
            block_log_str = None

            try:
                # Instantiate and run the block
                # Pass api_client in case the block needs it (though BaseReportBlock doesn't mandate it yet)
                block_output_json, block_log_str = await _instantiate_and_run_block(
                    block_def, report_params=params, api_client=api_client
                )

                # Execution succeeded if block_output_json is not None
                if block_output_json is None:
                    all_blocks_succeeded = False
                    logger.error(f"Block {position} ({block_name}) failed to generate output. Log: {block_log_str or 'No log output.'}")
                    # Even on failure, we try to save the log in ReportBlock
                else:
                    logger.info(f"Block {position} ({block_name}) generated output successfully.")
                    # Store successful output for potential inter-block use (not currently implemented)
                    block_outputs[block_name] = block_output_json
                
                if block_log_str:
                    block_logs[block_name] = block_log_str


            except Exception as exec_err:
                # Catch errors during the block's execution itself
                all_blocks_succeeded = False
                block_log_str = f"Error during block execution: {str(exec_err)}\n{traceback.format_exc()}"
                logger.exception(f"Error executing block {position} ({block_name}): {exec_err}")
                # Proceed to try and save the error in ReportBlock


            # --- 5. Create ReportBlock Record Immediately ---
            try:
                logger.debug(f"Creating ReportBlock record for block {position} ({block_name})...")
                report_block_data = {
                    "reportId": report_id,
                    "name": block_name,
                    "position": position,
                    "output": block_output_json, # Stores None if execution failed
                    "log": block_log_str # Stores log or execution error message
                }
                # Assuming ReportBlock.create uses client.execute which is synchronous
                created_block = await asyncio.to_thread(
                    ReportBlock.create,
                    client=api_client,
                    **report_block_data
                )
                logger.info(f"Successfully created ReportBlock record for block {position} ({block_name}) with ID: {created_block.id}")

            except Exception as block_create_err:
                all_block_records_created = False # Mark record creation failure
                logger.exception(f"Failed to create ReportBlock record for block {position} ({block_name}): {block_create_err}")
                # This is a more serious failure, affecting the overall report status.
                # We will set the final status outside the loop based on this flag.


        # Determine final status after processing all blocks
        if all_blocks_succeeded and all_block_records_created:
             final_status = 'COMPLETED'
             logger.info(f"Report {report_id} completed successfully.")
        elif not all_blocks_succeeded and not all_block_records_created:
             final_status = 'FAILED'
             error_message = "One or more report blocks failed to generate AND one or more block records failed to save."
             logger.error(f"Report {report_id} failed: Blocks failed to generate AND records failed to save.")
        elif not all_blocks_succeeded:
             final_status = 'FAILED' # Treat block execution failure as overall failure
             error_message = "One or more report blocks failed to generate output."
             logger.error(f"Report {report_id} failed: Blocks failed to generate.")
        else: # Implies all_blocks_succeeded is True, but all_block_records_created is False
             final_status = 'FAILED' # Treat inability to save results as failure
             error_message = "Successfully generated all block outputs, but failed to save one or more block records."
             logger.error(f"Report {report_id} failed: Could not save all block records.")

        # If failed, collect detailed errors
        if final_status == 'FAILED':
            try:
                # Combine logs and any creation errors into details
                error_details = json.dumps({
                    "message": error_message,
                    "block_logs": block_logs,
                    "block_execution_failed": not all_blocks_succeeded,
                    "block_record_creation_failed": not all_block_records_created,
                }, indent=2)
            except TypeError:
                error_details = json.dumps({"error": "Could not serialize error details.", "detail": error_message})

        # Update successful completion status and store the original markdown in output
        report_update_data = {
            "status": final_status,
            "completedAt": datetime.now(timezone.utc)
        }
        if final_status == 'COMPLETED':
            report_update_data["output"] = template_content_string # Store original markdown
        else:
            report_update_data["errorMessage"] = error_message
            report_update_data["errorDetails"] = error_details

        await asyncio.to_thread(created_report.update, **report_update_data)
        logger.info(f"Successfully updated final status for Report {report_id} to {final_status}")

        # Return the report_id on success or failure (as the record exists)
        return report_id

    except Exception as e:
        # Catch any other unhandled error during parsing or block processing setup
        logger.exception(f"Unhandled error during report generation for report {report_id}: {e}")
        final_status = 'FAILED'
        error_message = f"Unhandled error during report generation: {str(e)}"
        error_details = traceback.format_exc()

        # Attempt to update the Report record to FAILED status
        if created_report: # Should always be true if we get here
             try:
                 await asyncio.to_thread(
                     created_report.update,
                     status=final_status,
                     errorMessage=error_message,
                     errorDetails=error_details,
                     completedAt=datetime.now(timezone.utc)
                 )
                 logger.info(f"Updated Report {report_id} to FAILED due to unhandled exception.")
             except Exception as update_err:
                  logger.error(f"CRITICAL: Failed to update report {report_id} status to FAILED after unhandled exception {e}: {update_err}")
        # Re-raise the original exception after attempting to update status
        raise e

    # The code should not reach here due to return/raise in try/except blocks,
    # but added for completeness. Could return report_id if needed.
    # return report_id


def _parse_report_configuration(config_markdown: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parses the report configuration Markdown to extract block definitions
    and reconstruct the original Markdown string (including block definitions).

    Args:
        config_markdown: The raw Markdown content from ReportConfiguration.configuration.

    Returns:
        A tuple containing:
          - The original Markdown string.
          - A list of dictionaries, each representing a block definition
            extracted from ```block ... ``` sections.
    """
    logger.debug("Parsing report configuration markdown...")

    block_definitions = []
    reconstructed_markdown = ""
    current_position = 0 # Track block position

    # Use mistune to parse the markdown into tokens
    # Note: Using a custom renderer is complex for preserving original structure perfectly.
    # A simpler regex approach might be better for just extracting ```block``` sections
    # while keeping the rest intact.

    # --- Regex Approach ---
    # Pattern to find ```block ... ``` sections
    # Using re.DOTALL so '.' matches newlines within the YAML block
    # Using re.MULTILINE for potentially cleaner handling if needed, though DOTALL is key
    pattern = re.compile(r"^```block(?: name=\"([^\"]*)\")?\s*\n(.*?)\n^```", re.MULTILINE | re.DOTALL)

    last_end = 0
    for match in pattern.finditer(config_markdown):
        start, end = match.span()
        block_name = match.group(1) # Optional name from ```block name="..."
        yaml_content = match.group(2)

        # Append markdown text before this block
        reconstructed_markdown += config_markdown[last_end:start]
        # Append the raw block definition itself to the reconstructed markdown
        reconstructed_markdown += match.group(0) + "\n" # Add newline after block

        try:
            # Parse the YAML content within the block
            block_config = yaml.safe_load(yaml_content)
            if not isinstance(block_config, dict):
                raise ValueError("Block YAML must be a dictionary.")

            # Extract required 'pythonClass' and optional 'config'
            class_name = block_config.get("pythonClass")
            if not class_name:
                 raise ValueError("`pythonClass` not specified in block YAML.")
            block_params = block_config.get("config", {})

            # Add extracted definition to our list
            block_def = {
                "type": "block_config",
                "name": block_name or f"block_{current_position}", # Use extracted name or generate default
                "class_name": class_name,
                "config": block_params,
                "position": current_position # Add position based on parse order
            }
            block_definitions.append(block_def)
            logger.debug(f"Extracted block definition: {block_def}")
            current_position += 1

        except (yaml.YAMLError, ValueError) as e:
            logger.error(f"Error parsing report block YAML at position {current_position}: {e}\nYAML:\n{yaml_content}")
            # How to handle parse errors? Option 1: Skip block, Option 2: Fail report
            # For now, let's skip the block but log error. The report might still partially run.
            # TODO: Decide on final error handling strategy for block parsing failures.
            # Add an error marker to the definition list?
            block_definitions.append({
                "type": "error",
                "message": f"Error parsing block definition: {e}",
                "yaml_content": yaml_content,
                "position": current_position
            })
            # We still increment position for subsequent blocks
            current_position += 1


        last_end = end

    # Append any remaining markdown text after the last block
    reconstructed_markdown += config_markdown[last_end:]

    logger.debug(f"Finished parsing. Found {len(block_definitions)} blocks.")
    # Filter out any potential error markers before returning definitions to run
    valid_block_definitions = [bd for bd in block_definitions if bd.get("type") == "block_config"]

    return reconstructed_markdown.strip(), valid_block_definitions


# Note: Updated signature to accept api_client
async def _instantiate_and_run_block(block_def: dict, report_params: dict, api_client: PlexusDashboardClient) -> Tuple[Optional[str], Optional[str]]:
    """
    Instantiates and runs a specific ReportBlock Python class.

    Args:
        block_def: Dictionary containing block definition ('class_name', 'config', 'name', 'position').
        report_params: Overall parameters for the report run.
        api_client: The PlexusDashboardClient instance.

    Returns:
        A tuple containing:
          - JSON string of the block's output, or None if execution failed.
          - String containing logs or error message from the block's execution.
    """
    class_name = block_def.get('class_name')
    block_config_params = block_def.get('config', {}) # Params specific to this block instance
    block_name = block_def.get('name', 'Unnamed Block')

    # Combine general report params with block-specific params (block takes precedence)
    # TODO: Define precedence rules more clearly if needed.
    combined_params = {**report_params, **block_config_params}

    logger.debug(f"Attempting to instantiate block: {class_name} with combined params: {combined_params}")

    block_instance = None
    output_json: Optional[str] = None
    log_output: Optional[str] = "No log output." # Default log message

    try:
        # Find the class constructor
        block_class = BLOCK_CLASSES.get(class_name)
        if not block_class:
            raise ImportError(f"ReportBlock class '{class_name}' not found or not registered.")

        # Instantiate the block
        # Pass api_client and combined_params to the constructor
        # Ensure BaseReportBlock and subclasses accept these (or handle **kwargs)
        # TODO: Update BaseReportBlock constructor if necessary
        block_instance = block_class(config=block_config_params, params=report_params, api_client=api_client) # Adjust as needed

        # Run the block's generate method
        # Assuming generate is now async
        logger.info(f"Running generate() for block: {block_name} ({class_name})")
        # output_data should be JSON-serializable, log_output a string
        # The generate method itself should handle internal errors and return None for output on failure.
        output_data, log_output = await block_instance.generate()

        # Serialize the successful output to JSON string
        if output_data is not None:
            try:
                 # Use default=str to handle non-serializable types like datetime
                 output_json = json.dumps(output_data, default=str)
                 logger.debug(f"Block {block_name} finished. Output size: {len(output_json)} chars. Log: {log_output or 'None'}")
            except TypeError as json_err:
                logger.exception(f"Failed to serialize output from block {block_name} to JSON: {json_err}")
                # Set output to None as it's unusable, store serialization error in log
                output_json = None
                log_output = f"Failed to serialize block output to JSON: {str(json_err)}\n{traceback.format_exc()}"
        else:
             # Execution within generate() failed, log should contain details.
             logger.warning(f"Block {block_name} ({class_name}) generate() returned None for output.")
             # log_output should already be set by the generate method in case of failure


    except ImportError as ie:
        error_msg = f"ImportError for block '{block_name}' ({class_name}): {ie}"
        logger.error(error_msg)
        log_output = error_msg # Return error in log field
        # Output remains None

    except Exception as e:
        # Catch errors during instantiation or unexpected errors in generate() call
        error_msg = f"Error instantiating or running block '{block_name}' ({class_name}): {e}"
        logger.exception(error_msg) # Log full traceback
        log_output = f"{error_msg}\n{traceback.format_exc()}" # Return error details in log
        # Output remains None

    # Return the JSON string (or None) and the log string
    return output_json, log_output 