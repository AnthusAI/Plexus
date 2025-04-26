import importlib
import logging
from typing import Any, Dict, List, Optional, Tuple
import json
from datetime import datetime, timezone # Added datetime
import traceback # Added for error details
import re
import os # Added for API client env vars

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
from plexus.dashboard.api.models.task import Task # Added Task model
from plexus.cli.task_progress_tracker import TaskProgressTracker, StageConfig # Added Tracker and StageConfig

# Configure logging
logger = logging.getLogger(__name__)


# --- Remove Mock Data Loading ---
# MOCK_CONFIGURATIONS = { ... } # Removed


def _load_report_configuration(client: PlexusDashboardClient, config_id: str) -> Optional[ReportConfiguration]:
    """Loads a ReportConfiguration by its ID using the API client."""
    logger.info(f"Loading report configuration from API: {config_id}")
    try:
        # Use the get_by_id method from the ReportConfiguration model
        # ReportConfiguration.get_by_id is synchronous
        config = ReportConfiguration.get_by_id(config_id, client)

        if config:
            logger.info(f"Successfully loaded configuration: {config_id}")
            return config
        else:
            logger.warning(f"ReportConfiguration with ID {config_id} not found.")
            return None
    except Exception as e:
        logger.exception(f"Error loading ReportConfiguration {config_id}: {e}")
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
                    "config": block_params,
                    "block_name": block_config.get("name") # Extract optional block name
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
def generate_report(task_id: str):
    """
    Generates a report based on a Task record containing configuration details.
    Updates the Task status and progress via TaskProgressTracker.
    Creates Report and ReportBlock records linked to the Task.

    Args:
        task_id: The ID of the Task record triggering this report generation.

    Returns:
        None. Task status indicates success or failure.
    """
    api_client = PlexusDashboardClient()
    run_start_time = datetime.now(timezone.utc)
    log_prefix = f"[ReportGen task_id={task_id}]"
    logger.info(f"{log_prefix} Starting report generation process.")

    # === 1. Fetch Task Record ===
    try:
        task = Task.get_by_id(task_id, api_client)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        logger.info(f"{log_prefix} Fetched Task record.")
    except Exception as e:
        logger.exception(f"{log_prefix} Failed to fetch Task {task_id}: {e}")
        # Cannot update task status if we can't fetch it, so just raise
        raise

    # === 2. Extract Config from Task Metadata ===
    try:
        if not task.metadata:
            raise ValueError("Task metadata is missing or empty.")
        task_metadata = json.loads(task.metadata)
        report_config_id = task_metadata.get("report_configuration_id")
        account_id = task_metadata.get("account_id")
        params = task_metadata.get("report_parameters", {}) # Get params from metadata

        if not report_config_id:
            raise ValueError("'report_configuration_id' not found in Task metadata.")
        if not account_id:
            raise ValueError("'account_id' not found in Task metadata.")
        logger.info(f"{log_prefix} Extracted config: report_config_id={report_config_id}, account_id={account_id}")

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        error_msg = f"Failed to extract configuration from Task metadata: {e}"
        logger.error(f"{log_prefix} {error_msg}")
        logger.debug(f"{log_prefix} Task metadata content: {task.metadata}")
        # Update Task to FAILED before raising
        try:
            task.update(status="FAILED", errorMessage=error_msg, completedAt=datetime.now(timezone.utc).isoformat())
        except Exception as update_err:
            logger.error(f"{log_prefix} Additionally failed to update Task status after metadata error: {update_err}")
        raise ValueError(error_msg) from e # Re-raise original error

    # === 3. Load ReportConfiguration ===
    # Defined before tracker so we can potentially use config details in stages
    report_config_model = _load_report_configuration(api_client, report_config_id)
    if not report_config_model:
        error_msg = f"ReportConfiguration not found: {report_config_id}"
        logger.error(f"{log_prefix} {error_msg}")
        # Update Task to FAILED before raising
        try:
            task.update(status="FAILED", errorMessage=error_msg, completedAt=datetime.now(timezone.utc).isoformat())
        except Exception as update_err:
            logger.error(f"{log_prefix} Additionally failed to update Task status after config load error: {update_err}")
        raise ValueError(error_msg)

    config_markdown = report_config_model.configuration
    report_config_name = report_config_model.name
    # Verify accountId matches - this should ideally be enforced by permissions/logic before task creation
    if account_id != report_config_model.accountId:
        logger.warning(f"{log_prefix} Task account_id ({account_id}) does not match configuration's accountId ({report_config_model.accountId}). Using configuration's accountId for Report creation.")
        account_id = report_config_model.accountId # Use the config's account ID for the Report

    # === 4. Initialize Task Progress Tracker ===
    # Define stages - adjust as needed
    stage_configs = {
        "Setup": StageConfig(order=1, status_message="Initializing report generation..."),
        "Generate Blocks": StageConfig(order=2, status_message="Generating report content..."), # We'll set total_items later if needed
        "Finalize": StageConfig(order=3, status_message="Saving report...")
    }

    # Instantiate the tracker, passing the existing task_id.
    # It will automatically fetch the task and handle status updates.
    tracker = TaskProgressTracker(
        task_id=task_id, # Link to the existing task
        stage_configs=stage_configs,
        # These are not needed when providing task_id
        total_items=0, # Will be set per stage if needed
        prevent_new_task=True # IMPORTANT: ensures it uses the existing task_id
    )

    # === 5. Run Generation within Tracker Context ===
    report_instance = None # Define outside try/finally for potential use in finally
    try:
        with tracker: # Handles setting final status (COMPLETED/FAILED)
            tracker.set_stage("Setup")

            # === 5a. Create Report Record ===
            try:
                timestamp = run_start_time.strftime("%Y-%m-%d_%H-%M-%S")
                report_name = f"{report_config_name} - {timestamp}"
                logger.info(f"{log_prefix} Creating new Report record: {report_name}")
                report_instance = Report.create(
                    client=api_client,
                    reportConfigurationId=report_config_id,
                    accountId=account_id,
                    name=report_name,
                    parameters=params,
                    taskId=task_id # Link report to the task
                )
                report_id = report_instance.id
                logger.info(f"{log_prefix} Successfully created Report record with ID: {report_id}")
            except Exception as create_err:
                logger.exception(f"{log_prefix} Failed to create Report record: {create_err}")
                # Let tracker.fail() handle the task status
                raise RuntimeError(f"Failed to create Report record: {create_err}") from create_err # Re-raise to trigger tracker.fail

            # === 5b. Parse Configuration & Extract Blocks ===
            try:
                logger.info(f"{log_prefix} Parsing report configuration Markdown.")
                original_markdown_template, block_definitions = _parse_report_configuration(config_markdown)
                logger.info(f"{log_prefix} Found {len(block_definitions)} block definitions.")
            except Exception as parse_err:
                logger.exception(f"{log_prefix} Failed to parse report configuration: {parse_err}")
                raise RuntimeError(f"Failed to parse report configuration: {parse_err}") from parse_err

            # === 5c. Process Blocks ===
            tracker.set_stage("Generate Blocks", total_items=len(block_definitions))
            all_block_outputs = [] # Store tuples of (position, block_record_id)
            block_errors = []

            for index, block_def in enumerate(block_definitions):
                block_position = index + 1 # 1-based positioning
                block_name = block_def.get("block_name") # Get optional name
                logger.info(f"{log_prefix} Processing block {block_position}/{len(block_definitions)}: Name='{block_name or 'N/A'}', Class='{block_def['class_name']}'")
                try:
                    # Instantiate and run the block
                    block_output_json, block_log = _instantiate_and_run_block(
                        block_def=block_def,
                        report_params=params,
                        api_client=api_client # Pass client if blocks need it
                    )

                    # Create ReportBlock record
                    if block_output_json is not None:
                        try:
                            report_block = ReportBlock.create(
                                client=api_client,
                                reportId=report_id,
                                position=block_position,
                                name=block_name, # Store the optional name
                                output=block_output_json, # Store JSON string
                                log=block_log
                            )
                            all_block_outputs.append((block_position, report_block.id))
                            logger.debug(f"{log_prefix} Created ReportBlock record {report_block.id} for position {block_position}")
                        except Exception as create_block_err:
                            logger.exception(f"{log_prefix} Failed to create ReportBlock record for position {block_position}: {create_block_err}")
                            block_errors.append(f"Position {block_position}: Failed to store block result: {create_block_err}")
                    else:
                        # Handle case where block run failed internally but didn't raise
                        logger.warning(f"{log_prefix} Block at position {block_position} did not return output JSON.")
                        block_errors.append(f"Position {block_position}: Block execution failed or returned no output.")

                    # Update tracker progress
                    tracker.update(current_items=index + 1)

                except Exception as block_err:
                    logger.exception(f"{log_prefix} Error running block at position {block_position}: {block_err}")
                    block_errors.append(f"Position {block_position}: {block_err}")
                    # Optionally decide whether to continue or fail fast
                    # For now, let's continue but record the error.
                    # Create a ReportBlock indicating failure for this position
                    try:
                        error_block = ReportBlock.create(
                            client=api_client,
                            reportId=report_id,
                            position=block_position,
                            name=block_name,
                            output=json.dumps({"error": f"Block execution failed: {block_err}"}),
                            log=traceback.format_exc() # Store traceback in log
                        )
                        logger.warning(f"{log_prefix} Created error ReportBlock {error_block.id} for failed position {block_position}")
                    except Exception as create_error_block_err:
                         logger.exception(f"{log_prefix} Failed to create error ReportBlock record for position {block_position}: {create_error_block_err}")
                    # Update tracker progress even on failure to avoid stall
                    tracker.update(current_items=index + 1)

            # After loop, check if critical block errors occurred
            if block_errors:
                # Decide if partial success is acceptable or if the whole task should fail
                # For now, we log errors but let the task complete, storing partial results.
                # A future enhancement could allow configuration to fail task on block errors.
                logger.warning(f"{log_prefix} Encountered {len(block_errors)} errors during block processing. Report may be incomplete.")
                # Store summary of block errors in Task metadata?
                # task.update(metadata=json.dumps({"block_errors": block_errors, **task_metadata})) # Careful with metadata updates

            # === 5d. Store Original Markdown in Report Output ===
            try:
                logger.info(f"{log_prefix} Saving original Markdown template to Report.output for Report ID {report_id}")
                report_instance.update(output=original_markdown_template)
                logger.info(f"{log_prefix} Successfully saved Markdown template.")
            except Exception as update_err:
                logger.exception(f"{log_prefix} Failed to save final Markdown output to Report {report_id}: {update_err}")
                # Allow task to complete, but log the error.
                # Consider if this should trigger a task failure.

            # === 5e. Finalize ===
            tracker.set_stage("Finalize")
            logger.info(f"{log_prefix} Report generation process completed within tracker context.")
            # Tracker's __exit__ will set Task status to COMPLETED

    except Exception as e:
        # This catches errors raised within the `with tracker:` block
        # The tracker's __exit__ will handle setting the Task to FAILED
        # and storing the error message `e`.
        logger.exception(f"{log_prefix} Report generation failed: {e}")
        # Optionally, perform specific cleanup if needed, but avoid updating Task status here.
        # Example: If report_instance was created, maybe mark it as failed?
        # if report_instance:
        #     try:
        #         report_instance.update(status="FAILED", errorMessage=f"Task failed: {e}")
        #     except Exception as final_update_err:
        #         logger.error(f"{log_prefix} Failed to mark Report {report_id} as FAILED after task failure: {final_update_err}")

    logger.info(f"{log_prefix} Report generation function finished.")
    # No return value needed, status is on the Task record


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
def _instantiate_and_run_block(block_def: dict, report_params: dict, api_client: PlexusDashboardClient) -> Tuple[Optional[str], Optional[str]]:
    """
    Instantiates and runs a single report block.

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
            error_msg = f"Report block class '{class_name}' not found."
            logger.error(error_msg)
            # Return None, Log String
            return None, error_msg

        # Instantiate the block
        # Pass api_client to block constructor if needed
        block_instance = block_class(config=block_config_params, params=report_params, client=api_client) # Pass client

        # Run the block's generate method (synchronous)
        output_data = block_instance.generate()
        block_log = getattr(block_instance, 'get_log', lambda: None)() # Get logs if method exists

        # Serialize output to JSON string
        output_json = json.dumps(output_data, indent=2)

        return output_json, block_log

    except Exception as e:
        logger.exception(f"Error executing report block '{class_name}': {e}")
        # Re-raise the exception to be caught by the main loop
        raise RuntimeError(f"Error in block '{class_name}': {e}") from e 