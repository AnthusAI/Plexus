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


# Updated function signature
async def generate_report(
    report_config_id: str,
    account_id: str, # Added account_id for clarity when creating/updating
    params: Optional[Dict[str, Any]] = None, # Passed during Report creation
    report_id: Optional[str] = None, # Added: ID of pre-existing report (e.g., from Celery task)
    task_id: Optional[str] = None # Added: Celery task ID for logging/error details
) -> str:
    """
    Generates a report based on a ReportConfiguration and optional parameters.
    Can either create a new Report record or update an existing one identified by report_id.

    Args:
        report_config_id: The ID of the ReportConfiguration to use.
        account_id: The ID of the account owning the report.
        params: Optional dictionary of parameters to use for this specific run.
        report_id: Optional ID of an existing Report record to update.
        task_id: Optional Celery task ID for context.

    Returns:
        The ID of the generated/updated Report record.
    """
    if params is None:
        params = {}

    api_client = PlexusDashboardClient()
    run_start_time = datetime.now(timezone.utc)

    log_prefix = f"[ReportGen report_id={report_id or 'NEW'} config_id={report_config_id} task_id={task_id or 'N/A'}]"
    logger.info(f"{log_prefix} Starting report generation process with params: {params}")

    # === 1. Load ReportConfiguration ===
    report_config_model = await _load_report_configuration(api_client, report_config_id)
    if not report_config_model:
        error_msg = f"ReportConfiguration not found: {report_config_id}"
        logger.error(f"{log_prefix} {error_msg}")
        # Do not update Report status here. Raise error for Celery task to handle Task status.
        raise ValueError(error_msg) # Raise anyway to signal failure

    config_markdown = report_config_model.configuration
    report_config_name = report_config_model.name
    # Verify accountId matches if report_id was provided (optional sanity check)
    if report_id and account_id != report_config_model.accountId:
         logger.warning(f"{log_prefix} Provided account_id ({account_id}) does not match configuration's accountId ({report_config_model.accountId}). Using configuration's accountId.")
         account_id = report_config_model.accountId

    # === 2. Ensure Report Record Exists ===
    if not report_id:
        # Create a new report if no ID was provided (e.g., direct CLI run)
        try:
            timestamp = run_start_time.strftime("%Y-%m-%d_%H-%M-%S")
            report_name = f"{report_config_name} - {timestamp}"
            logger.info(f"{log_prefix} Creating new Report record: {report_name}")
            created_report = await asyncio.to_thread(
                Report.create,
                client=api_client,
                reportConfigurationId=report_config_id,
                accountId=account_id,
                name=report_name,
                parameters=params,
                # Status is managed by the Task, not set here.
            )
            report_id = created_report.id
            # No need to update status or startedAt here, managed by Task.
            logger.info(f"{log_prefix} Successfully created Report record with ID: {report_id}")
            # The created_report object holds the instance
            report_instance = created_report
        except Exception as create_err:
            logger.exception(f"{log_prefix} Failed to create initial Report record: {create_err}")
            raise
    else:
        # If report_id was provided, fetch the existing report
        # This path might be deprecated if we always create Report from Task trigger
        try:
            logger.info(f"{log_prefix} Fetching existing Report record: {report_id}")
            report_instance = await asyncio.to_thread(Report.get_by_id, report_id, api_client)
            if not report_instance:
                raise ValueError(f"Report with ID {report_id} not found.")
            
            # No need to update status/startedAt here, managed by Task.
            logger.info(f"{log_prefix} Successfully fetched existing Report: {report_id}")
        except Exception as fetch_err:
            logger.exception(f"{log_prefix} Failed to fetch or update existing Report record {report_id}: {fetch_err}")
            raise

    # --- Main processing block with final status update ---
    final_output_markdown = None # Store the final markdown here

    try:
        # === 3. Parse Configuration Markdown ===
        logger.info(f"{log_prefix} Parsing report configuration markdown...")
        # Use the existing synchronous parsing function
        template_content_string, block_definitions = _parse_report_configuration(config_markdown)
        final_output_markdown = template_content_string # Store the original markdown for Report.output
        logger.info(f"{log_prefix} Found {len(block_definitions)} blocks to process.")

        # === 4. Process Blocks Sequentially ===
        # Initialize the list to store created ReportBlock objects/IDs
        created_block_ids = []
        block_outputs = {}

        for index, block_def in enumerate(block_definitions):
            position = index + 1 # 1-based positioning
            block_name = block_def.get("name") # Get optional name
            class_name = block_def.get("class_name")
            block_config_params = block_def.get("config")
            logger.info(f"{log_prefix} Processing block {position}/{len(block_definitions)} (Name: {block_name or 'N/A'}, Class: {class_name})...")

            block_output_data = None
            block_log_data = None
            block_error = None

            try:
                # Combine report-level params with block-specific config
                # Block-specific config takes precedence
                combined_params = {**params, **block_config_params}

                # Instantiate and run the block (this is already async)
                block_output_data, block_log_data = await _instantiate_and_run_block(
                    block_def=block_def,
                    report_params=combined_params,
                    api_client=api_client
                )
                logger.debug(f"{log_prefix} Block {position} generated output: {block_output_data}, log: {block_log_data}")

            except Exception as block_exec_err:
                logger.exception(f"{log_prefix} Error executing block {position} ({class_name}): {block_exec_err}")
                block_error = block_exec_err
                # Store minimal error info in block output if possible
                block_output_data = {"error": f"Block execution failed: {block_exec_err}"}
                block_log_data = f"ERROR: {block_exec_err}\n{traceback.format_exc()}"

            # === 5. Store ReportBlock Result ===
            try:
                logger.info(f"{log_prefix} Storing result for block {position}...")
                # Assuming ReportBlock.create is synchronous
                created_block = await asyncio.to_thread(
                    ReportBlock.create,
                    client=api_client,
                    reportId=report_id,
                    name=block_name, # Pass the name if available
                    position=position,
                    output=block_output_data or {}, # Ensure output is dict
                    log=block_log_data
                )
                created_block_ids.append(created_block.id)
                logger.info(f"{log_prefix} Stored ReportBlock {created_block.id} for position {position}.")

                # If there was an error during execution, raise it AFTER storing the block result
                if block_error:
                    raise block_error # Re-raise the execution error

            except Exception as block_store_err:
                logger.exception(f"{log_prefix} Failed to store ReportBlock result for block {position}: {block_store_err}")
                # Decide if this is fatal for the whole report. Maybe continue processing other blocks?
                # For now, let's make it fatal.
                raise RuntimeError(f"Failed to store result for block {position}: {block_store_err}") from block_store_err

        # If all blocks processed without raising an error:
        logger.info(f"{log_prefix} All {len(block_definitions)} blocks processed successfully.")

        # === 7. Update Final Report Details ===
        # Update the report with the final output
        await asyncio.to_thread(
            report_instance.update, # Call update on the instance
            output=final_output_markdown # Only update the output field
        )
        logger.info(f"{log_prefix} Successfully updated final Report output for {report_id}")

    except Exception as processing_err:
        logger.exception(f"{log_prefix} Report generation failed during processing: {processing_err}")
        # Log the error. Status update (FAILED) should happen on the Task record
        # by the calling Celery task or error handler.
        # Ensure final_output_markdown has the template content even on failure
        if final_output_markdown is None and config_markdown:
            try:
                final_output_markdown, _ = _parse_report_configuration(config_markdown)
            except Exception as parse_err:
                 logger.error(f"{log_prefix} Additionally failed to parse markdown for failed report output: {parse_err}")
                 final_output_markdown = "Error: Could not retrieve report template."
        raise # Re-raise the exception so the Celery task knows it failed

    finally:
        # The finally block is no longer needed to update status, as status is managed by the Task.
        pass # Keep finally block syntax valid if other cleanup were needed.

    # Return the report_id regardless of success/failure (as the record should exist)
    return report_id


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