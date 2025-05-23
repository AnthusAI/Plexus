import importlib
import logging
from typing import Any, Dict, List, Optional, Tuple
import json
from datetime import datetime, timezone # Added datetime
import traceback # Added for error details
import re
import os # Added for API client env vars
import asyncio # Add asyncio import

# print("[DEBUG] service.py top level print") # DEBUG PRINT

import mistune
import yaml
import jinja2

# Import S3 utils explicitly at the top level to ensure it's loaded
try:
    from plexus.reports.s3_utils import upload_report_block_file, get_bucket_name
    logger = logging.getLogger(__name__)
    logger.info("Successfully imported S3 utils at module level")
    S3_UTILS_AVAILABLE = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import S3 utils at module level: {str(e)}")
    S3_UTILS_AVAILABLE = False

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
        # return token["raw"] # MODIFIED: Don't return, just buffer

    def paragraph(self, token, state):
        # Instead of rendering <p>, just accumulate the inner text
        # Process children to ensure their content is added to the buffer
        self.render_tokens(token["children"], state)
        # Add paragraph breaks AFTER children content for potentially better formatting later
        self._current_markdown_buffer += "\\n\\n"
        # return inner_text # MODIFIED: Don't return, just buffer

    def block_code(self, token, state):
        lang_info = token["attrs"].get("info") if token.get("attrs") else None
        lang_info = lang_info.strip() if lang_info else ""
        code = token["raw"]
        # Use token metadata if available (Mistune v3+) for more robust raw extraction
        start_pos = token.get('start_pos')
        end_pos = token.get('end_pos')
        input_markdown = getattr(state, '_raw', None) if state else None

        logger.debug(f"[Extractor] block_code called. Lang Info: '{lang_info}'")

        # Check if the language info starts with 'block'
        if lang_info.startswith("block"):
            logger.debug("[Extractor] Found 'block' prefix. Processing as report block.")
            self._flush_markdown_buffer() # Add preceding Markdown first

            # --- Extract attributes from lang_info (e.g., name) ---
            # Simple regex to find key="value" pairs after 'block'
            attrs_str = lang_info[len("block"):].strip()
            attrs = {}
            # Regex: find key= followed by either "quoted value" or unquoted_value
            pattern = re.compile(r'(\\w+)\\s*=\\s*(?:"([^"]*)"|(\\S+))')
            for match in pattern.finditer(attrs_str):
                key = match.group(1)
                # Value can be in group 2 (quoted) or group 3 (unquoted)
                value = match.group(2) if match.group(2) is not None else match.group(3)
                attrs[key] = value
            logger.debug(f"[Extractor] Extracted attributes from lang info: {attrs}")
            # --- End Attribute Extraction ---

            try:
                logger.debug(f"[Extractor] Parsing YAML content:\\n{code}")
                yaml_config = yaml.safe_load(code)
                logger.debug(f"[Extractor] YAML parsed successfully: {yaml_config}")

                if not isinstance(yaml_config, dict):
                    logger.error("[Extractor] Parsed YAML is not a dictionary.")
                    raise ValueError("Block YAML content must be a dictionary.")

                # Combine attributes from lang info and YAML content
                # YAML content takes precedence if keys overlap (e.g., 'name' defined in both)
                block_config = {**attrs, **yaml_config}
                logger.debug(f"[Extractor] Combined block config: {block_config}")

                # --- Extract core properties (class, config, name) ---
                class_name = block_config.get("class") # Still expect 'class' key
                # Use 'config' sub-dict if present, otherwise use the whole dict excluding 'class' and 'name'
                block_params = block_config.get("config", {k: v for k, v in block_config.items() if k not in ["class", "name"]})
                block_name = block_config.get("name") # Name can come from attrs or YAML
                # --- End Core Property Extraction ---

                logger.debug(f"[Extractor] Final extracted properties: class='{class_name}', name='{block_name}', config={block_params}")

                if not class_name:
                    logger.error("[Extractor] `class` key not found in combined block config.")
                    raise ValueError("`class` not specified in block definition (either YAML or attributes).")

                # --- Determine original raw content for storage ---
                # Prefer using start/end pos if available for accuracy
                original_block_content = ""
                if start_pos is not None and end_pos is not None and input_markdown:
                    original_block_content = input_markdown[start_pos:end_pos].strip()
                else: # Fallback to reconstructing
                    original_block_content = f"```block{attrs_str}\\n{code}\\n```"
                # --- End Original Content Determination ---


                self.extracted_content.append({
                    "type": "block_config",
                    "class_name": class_name,
                    "config": block_params,
                    "block_name": block_name, # Use the resolved block name
                    # "content": f"```block{attrs_str}\\n{code}\\n```" # STORE ORIGINAL RAW CONTENT
                    "content": original_block_content # Store potentially more accurate raw content
                })
                logger.debug("[Extractor] Appended block_config to extracted_content.")
                return "" # Indicate successful block processing (no return needed for buffer)

            except (yaml.YAMLError, ValueError, re.error) as e: # Added re.error
                logger.error(f"[Extractor] Error parsing report block definition: {e}", exc_info=True)
                # Try to get raw block content even on error for reconstruction
                raw_content_on_error = ""
                if start_pos is not None and end_pos is not None and input_markdown:
                    raw_content_on_error = input_markdown[start_pos:end_pos].strip()
                else:
                    raw_content_on_error = f"```block {lang_info}\\n{code}\\n```" # Best guess

                self.extracted_content.append({
                    "type": "error",
                    "message": f"Error parsing block definition: {e}",
                    "content": raw_content_on_error # Store raw content even on error
                })
                # return "<!-- Error parsing block -->" # Don't return
                return "" # Still return empty string

        else:
            # Treat as regular markdown code block
            logger.debug(f"[Extractor] Non-'block' language prefix ('{lang_info}'). Treating as regular markdown.")
            # Reconstruct the raw code block markdown accurately if possible
            if start_pos is not None and end_pos is not None and input_markdown:
                 raw_code_md = input_markdown[start_pos:end_pos].strip()
                 self._current_markdown_buffer += raw_code_md + "\\n\\n" # Add spacing
            else: # Fallback
                 rendered_code = f"```{(lang_info or '')}\\n{code}\\n```\\n"
                 self._current_markdown_buffer += rendered_code
            # return rendered_code # MODIFIED: Don't return, just buffer
            return "" # Return empty string

    # Handle other elements by accumulating their raw content or rendering children
    # We might need to add more handlers (heading, list, etc.)
    # if we want to preserve more structure in the markdown parts.
    def heading(self, token, state):
        level = token["attrs"]["level"]
        # Use token metadata if available (Mistune v3+) for more robust raw extraction
        start_pos = token.get('start_pos')
        end_pos = token.get('end_pos')
        input_markdown = getattr(state, '_raw', None) if state else None

        # Try to reconstruct raw markdown directly for simplicity and accuracy
        if start_pos is not None and end_pos is not None and input_markdown:
             raw_heading_md = input_markdown[start_pos:end_pos].strip()
             # Ensure reasonable spacing after the heading
             self._current_markdown_buffer += raw_heading_md + "\\n\\n"
        else: # Fallback if raw isn't easily available
             # Fallback involves processing children, which might be less accurate
             # if text handler is modified
             self._current_markdown_buffer += '#' * level + ' '
             self.render_tokens(token["children"], state) # Process children to buffer text
             self._current_markdown_buffer += "\\n\\n" # Add spacing
        # return md_header # MODIFIED: Don't return, just buffer

    def render_tokens(self, tokens, state):
        # Helper to render child tokens - MODIFIED
        # result = "" # No longer accumulate result
        for tok in tokens:
            # Dynamically call the method based on token type
            method = getattr(self, tok["type"], None)
            if method:
                # result += method(tok, state) # Don't accumulate result
                method(tok, state) # Just call the method to process it (and modify buffer)
            elif "raw" in tok: # Fallback for unhandled tokens with raw text
                # result += tok["raw"] # Don't accumulate result
                # Append raw content from unhandled tokens directly to buffer
                # This might be needed for things like inline code, emphasis, etc.
                self._current_markdown_buffer += tok["raw"]
        # return result # Don't return anything

    def finalize(self, data):
         # This method is called at the end by BaseRenderer
         # Flush any remaining buffer content
         self._flush_markdown_buffer()
         # Filter out empty markdown sections
         return [
            item for item in self.extracted_content 
            if item.get("type") != "markdown" or item.get("content")
         ]

# Initialize Mistune with the custom renderer
# Use mistune v3 API if applicable
# For now, assume v2 style initialization works or adapt as needed
markdown_parser = mistune.create_markdown(renderer=ReportBlockExtractor())

def _parse_report_configuration(config_markdown: str) -> List[Dict[str, Any]]:
    """
    Parses the ReportConfiguration Markdown content to extract a list of defined block configurations.
    The original Markdown template is no longer reconstructed here.

    Args:
        config_markdown: The Markdown string from ReportConfiguration.configuration.

    Returns:
        - block_definitions (List[Dict]): A list of dictionaries, each representing a block to run.
    """
    logger.debug("Parsing report configuration markdown to extract blocks...")
    extractor = ReportBlockExtractor()
    mistune.create_markdown(renderer=extractor)(config_markdown)
    parsed_data = extractor.finalize(None)

    block_definitions = []
    block_position = 0

    for item in parsed_data:
        if item["type"] == "block_config":
            item["position"] = block_position
            block_definitions.append(item)
            block_position += 1
        elif item["type"] == "error":
            logger.error(f"Error encountered during config parsing: {item['message']}")
            # If parsing fails, we might want to raise an error here instead of just logging
            # For now, just log and continue extraction if possible, but don't include in template

    logger.debug(f"Parsed {len(block_definitions)} blocks.")
    return block_definitions


def _instantiate_and_run_block(
    block_def: dict, report_params: dict, api_client: PlexusDashboardClient, report_block_id: Optional[str] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Instantiates and runs a single report block.

    Args:
        block_def: Definition of the block (class_name, config, etc.).
        report_params: Global parameters for the report run.
        api_client: PlexusDashboardClient instance.
        report_block_id: Optional ID of the ReportBlock record this execution is for.
                         If provided, it will be set on the block instance.

    Returns:
        A tuple containing the block's output data (JSON serializable dict) and log string.
        Returns (None, error_message_string) if the block fails.
    """
    class_name = block_def["class_name"]
    block_config = block_def["config"]
    block_display_name = block_def.get("block_name", class_name) # Use provided name or class name

    logger.info(f"Instantiating block: {class_name} with config: {block_config}")

    if class_name not in BLOCK_CLASSES:
        error_msg = f"Block class '{class_name}' not found or not registered. Available: {list(BLOCK_CLASSES.keys())}"
        logger.error(error_msg)
        return None, error_msg

    try:
        block_class = BLOCK_CLASSES[class_name]
        # Pass api_client and report_params to the block's constructor
        block_instance = block_class(config=block_config, params=report_params, api_client=api_client)
        
        # Set the report_block_id on the instance if provided
        if report_block_id:
            block_instance.report_block_id = report_block_id
            logger.info(f"Set report_block_id '{report_block_id}' on block instance '{class_name}'")

        # Run the block's generate method (assuming it's async)
        # output_data, log_output = asyncio.run(block_instance.generate())
        # Check if running in an existing event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = None

        if loop and loop.is_running():
            # If there's a running loop, schedule generate() as a task
            # This is typical in an async environment like a Celery worker or FastAPI
            logger.info(f"Detected running event loop. Scheduling block '{class_name}' generation as a task.")
            # This won't work as a direct call if _instantiate_and_run_block is synchronous.
            # For now, we assume _generate_report_core is not itself async, so direct await or run is needed.
            # If _generate_report_core were async, we could 'await block_instance.generate()'
            # Let's stick to asyncio.run for now, assuming this function might be called
            # from a synchronous context that needs to drive an async method.
            # Re-evaluating this: if called by Celery, Celery itself might handle the loop.
            # Plexus tasks are often async. The caller (Celery task) should manage the async context.
            # For simplicity, let's assume we need to run it.
            # If _instantiate_and_run_block is called from an async func, then use:
            # output_data, log_output = await block_instance.generate()
            # If called from sync, and generate is async:
            output_data, log_output = asyncio.run(block_instance.generate())
        else:
            # If no running loop, create one to run the async method
            logger.info(f"No running event loop. Creating new loop for block '{class_name}' generation.")
            output_data, log_output = asyncio.run(block_instance.generate())
            

        logger.info(f"Block '{block_display_name}' executed. Log output length: {len(log_output) if log_output else 0}")
        # logger.debug(f"Block '{block_display_name}' log output:\n{log_output}") # Can be very verbose
        return output_data, log_output

    except Exception as e:
        error_msg = f"Error running block {block_display_name} ({class_name}): {e}"
        detailed_error = traceback.format_exc()
        logger.exception(f"{error_msg}")
        # Return None for JSON output and the error message as the log string
        return None, f"{error_msg}\nDetails:\n{detailed_error}"

# --- End Block Processing Logic ---


def _generate_report_core(
    report_config_id: str,
    account_id: str,
    run_parameters: Dict[str, Any],
    client: PlexusDashboardClient,
    tracker: TaskProgressTracker,
    log_prefix_override: Optional[str] = None # For CLI context
) -> Tuple[str, Optional[str]]:
    """
    Core logic for generating a report. Assumes Task exists and tracker is initialized.

    Args:
        report_config_id: ID of the ReportConfiguration to use.
        account_id: ID of the account owning the report.
        run_parameters: Dictionary of parameters for this specific run.
        client: Initialized PlexusDashboardClient.
        tracker: Initialized TaskProgressTracker for status and progress updates.
        log_prefix_override: Optional prefix for logs (e.g., for CLI context).

    Returns:
        A tuple containing:
        - report_id (str): The ID of the generated Report record.
        - first_error_message (Optional[str]): The first specific error encountered during block
                                               processing, or None if all blocks succeeded.

    Raises:
        Exception: If any critical step fails (config load, parsing, DB update).
    """
    log_prefix = log_prefix_override or f"[ReportGen task_id={tracker.task_id}]"
    logger.info(f"{log_prefix} Starting core report generation logic.")
    report_id = None # Initialize report_id
    first_block_error_message: Optional[str] = None

    try:
        # === 1. Load ReportConfiguration ===
        # Stage 1: Loading Configuration (Implicitly started by tracker init)
        report_config_model = _load_report_configuration(client, report_config_id)
        if not report_config_model:
            raise ValueError(f"ReportConfiguration not found or failed to load: {report_config_id}")

        config_markdown = report_config_model.configuration
        report_config_name = report_config_model.name
        logger.info(f"{log_prefix} Loaded ReportConfiguration: {report_config_name} ({report_config_id})")

        # Verify accountId consistency (owner of config vs. owner of triggering task/report)
        if account_id != report_config_model.accountId:
            logger.warning(f"{log_prefix} Report account_id ({account_id}) differs from Configuration's accountId ({report_config_model.accountId}). Proceeding with Report's accountId.")
            # Keep the account_id provided to this function (originating from Task or CLI)

        tracker.advance_stage() # Advance to next stage (Initializing Report Record)

        # === 2. Create Report Record ===
        # Stage 2: Initializing Report Record
        report_name = f"{report_config_name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        logger.info(f"{log_prefix} Creating Report DB record: '{report_name}'")
        try:
            # --- DEBUG: Inspect config_markdown before saving --- #
            logger.info(f"{log_prefix} repr(config_markdown) before Report.create:\n{repr(config_markdown)}")
            # Add actual content logging
            logger.info(f"{log_prefix} Actual content (first 100 chars): {config_markdown[:100]}")
            has_literal_newlines = "\\n" in config_markdown
            has_actual_newlines = "\n" in config_markdown
            logger.info(f"{log_prefix} Content contains literal newlines: {has_literal_newlines}")
            logger.info(f"{log_prefix} Content contains actual newlines: {has_actual_newlines}")
            # --- END DEBUG --- #
            report = Report.create(
                client=client,
                name=report_name,
                accountId=account_id,
                reportConfigurationId=report_config_id,
                taskId=tracker.task.id,
                parameters=json.dumps(run_parameters),
                output=config_markdown # Store original config markdown directly
            )
            report_id = report.id
            # Log content after report creation
            logger.info(f"{log_prefix} Report content after creation (first 100 chars): {report.output[:100]}")
            has_literal_newlines = "\\n" in report.output
            has_actual_newlines = "\n" in report.output
            logger.info(f"{log_prefix} Report content contains literal newlines: {has_literal_newlines}")
            logger.info(f"{log_prefix} Report content contains actual newlines: {has_actual_newlines}")
            logger.info(f"{log_prefix} Successfully created Report record with ID: {report_id}")
        except Exception as e:
            logger.exception(f"{log_prefix} Failed to create Report database record: {e}")
            raise RuntimeError(f"Failed to create Report database record: {e}") from e
        tracker.advance_stage() # Advance to next stage (Parsing Configuration)

        # === 3. Parse Configuration Markdown ===
        logger.info(f"{log_prefix} Parsing configuration markdown to extract blocks.") # Updated log message
        try:
            # original_markdown_template, block_definitions = _parse_report_configuration(config_markdown)
            block_definitions = _parse_report_configuration(config_markdown) # Get only block definitions
            logger.info(f"{log_prefix} Found {len(block_definitions)} blocks to process.")
            # Ensure report object exists before updating
            # REMOVED: No longer need to update report output here, it was set during creation.
            # if report_id:
            #      report_to_update = Report.get_by_id(report_id, client) # Refetch to ensure object exists
            #      if report_to_update:
            #          report_to_update.update(output=original_markdown_template)
            #          logger.info(f"{log_prefix} Updated Report record with initial markdown template.")
            #      else:
            #          logger.warning(f"{log_prefix} Could not re-fetch report {report_id} to update template.")
            # else:
            #      logger.error(f"{log_prefix} Cannot update report template, report ID is missing.")

        except Exception as e:
            logger.exception(f"{log_prefix} Failed to parse report configuration markdown: {e}")
            # If parsing fails, we still have the original markdown stored, but should mark task as failed.
            # try:
            #     if report_id:
            #          report_to_update = Report.get_by_id(report_id, client) # Refetch
            #          if report_to_update:
            #              report_to_update.update(output=f"# Report Generation Failed\n\nError parsing configuration: {e}")
            #          else:
            #              logger.error(f"{log_prefix} Could not re-fetch report {report_id} to update with parsing error.")
            #     else:
            #         logger.error(f"{log_prefix} Cannot update report with parsing error, report ID is missing.")
            # except Exception as update_err:
            #     logger.error(f"{log_prefix} Additionally failed to update report output after parsing error: {update_err}")
            raise RuntimeError(f"Failed to parse report configuration markdown: {e}") from e
        tracker.advance_stage() # Advance to next stage (Processing Report Blocks)

        # === 4. Process Report Blocks ===
        num_blocks = len(block_definitions)
        logger.info(f"{log_prefix} Starting processing of {num_blocks} report blocks.")
        tracker.set_total_items(num_blocks)

        # Initialize default values for ReportBlock creation
        initial_output: Optional[Dict[str, Any]] = {"status": "pending"}
        initial_log: Optional[str] = "Block execution pending."
        initial_attached_files: Optional[str] = None # Or json.dumps([]) if you prefer an empty list string

        for i, block_def in enumerate(block_definitions):
            position = block_def.get("position", i)
            block_class_name = block_def["class_name"]
            block_display_name = block_def.get("block_name", f"{block_class_name} at pos {position}")
            
            logger.info(f"{log_prefix} Preparing block {i+1}/{num_blocks}: {block_display_name} (Class: {block_class_name}, Pos: {position})")

            # Create the ReportBlock record *before* running the block instance
            # This allows the block instance to know its ID and attach files to itself.
            current_report_block = None
            try:
                logger.info(f"{log_prefix} Creating initial ReportBlock record for {block_display_name}")
                current_report_block = ReportBlock.create(
                    client=client,
                    reportId=report_id,
                    position=position,
                    name=block_display_name,
                    type=block_class_name, # Pass the determined block type
                    output=json.dumps(initial_output), # Ensure output is JSON string
                    log=initial_log,
                    attachedFiles=initial_attached_files # Renamed from detailsFiles
                )
                logger.info(f"{log_prefix} Created ReportBlock ID {current_report_block.id} for {block_display_name}")
            except Exception as e:
                logger.exception(f"{log_prefix} Failed to create initial ReportBlock for {block_display_name}: {e}")
                # Record this as a block-level error and continue to next block if possible
                if first_block_error_message is None:
                    first_block_error_message = f"Failed to create DB record for block {block_display_name}: {e}"
                tracker.update(current_items=i + 1) # Still advance tracker
                continue # Skip to next block definition
            

            # Run the block instance, passing its report_block_id
            output_json, log_string = _instantiate_and_run_block(
                block_def=block_def,
                report_params=run_parameters,
                api_client=client,
                report_block_id=current_report_block.id # Pass the ID
            )

            # Fetch the latest state of the ReportBlock, as the block itself might have updated attachedFiles
            existing_details_files_list = [] # Initialize before try block
            try:
                logger.info(f"{log_prefix} Re-fetching ReportBlock ID {current_report_block.id} after block execution.")
                db_block_state = ReportBlock.get_by_id(current_report_block.id, client)
                if not db_block_state:
                    logger.error(f"{log_prefix} Failed to re-fetch ReportBlock {current_report_block.id} after execution. File attachments might be lost.")
                    # Fallback to an empty list if fetch fails, though this is problematic
                    # existing_details_files_list is already []
                else:
                    logger.info(f"{log_prefix} Fetched DB state. Current attachedFiles: {db_block_state.attachedFiles}")
                    if db_block_state.attachedFiles:
                        # Handle both list and potential legacy JSON string formats
                        if isinstance(db_block_state.attachedFiles, list):
                            existing_details_files_list = db_block_state.attachedFiles
                            logger.info(f"{log_prefix} attachedFiles is already a list with {len(existing_details_files_list)} items")
                        else:
                            # For backward compatibility - try to parse JSON if it's a string
                            try:
                                existing_details_files_list = json.loads(db_block_state.attachedFiles)
                                logger.info(f"{log_prefix} Successfully parsed existing attachedFiles JSON (for backward compatibility)")
                                
                                # Check if we have old format objects and extract just paths
                                if existing_details_files_list and isinstance(existing_details_files_list[0], dict) and 'path' in existing_details_files_list[0]:
                                    logger.warning(f"{log_prefix} Converting old format attachedFiles to just paths")
                                    existing_details_files_list = [item['path'] for item in existing_details_files_list]
                            except (json.JSONDecodeError, TypeError):
                                # If not valid JSON or not string, treat as a single item
                                logger.warning(f"{log_prefix} Could not parse attachedFiles as JSON - treating as a single item")
                                existing_details_files_list = [db_block_state.attachedFiles]
                            
                        # Ensure it's a list
                        if not isinstance(existing_details_files_list, list):
                            logger.warning(f"{log_prefix} attachedFiles for ReportBlock {current_report_block.id} was not a list: {existing_details_files_list}. Resetting.")
                            existing_details_files_list = []
            except Exception as e:
                logger.exception(f"{log_prefix} Error fetching or parsing ReportBlock {current_report_block.id} attachedFiles: {e}. Proceeding with empty list.")
                existing_details_files_list = [] # Ensure it's an empty list on error
            
            # Handle log content attachment
            final_log_message_for_db = "No detailed log output."
            if log_string:
                if S3_UTILS_AVAILABLE:
                    try:
                        logger.info(f"{log_prefix} Uploading log.txt for ReportBlock {current_report_block.id}")
                        log_file_info = upload_report_block_file(
                            report_block_id=current_report_block.id,
                            file_name="log.txt",
                            content=log_string.encode('utf-8'),  # Encode to bytes
                            content_type="text/plain"
                        )
                        existing_details_files_list.append(log_file_info)
                        logger.info(f"{log_prefix} Appended log.txt info. New attachedFiles list: {existing_details_files_list}")
                        final_log_message_for_db = "See log.txt in attachedFiles."
                    except Exception as e:
                        logger.exception(f"{log_prefix} Failed to upload log.txt to S3 for ReportBlock {current_report_block.id}: {str(e)}. Storing log inline (truncated).", exc_info=True)
                        final_log_message_for_db = log_string[:10000] # Truncate if storing inline
                else:
                    logger.warning(f"{log_prefix} S3_UTILS_AVAILABLE is false. Storing log inline (truncated) for ReportBlock {current_report_block.id}.")
                    final_log_message_for_db = log_string[:10000] # Truncate
            

            # Final update to the ReportBlock record
            try:
                logger.info(f"{log_prefix} Performing final update for ReportBlock {current_report_block.id}")
                
                current_report_block.update(
                    output=json.dumps(output_json if output_json is not None else {"status": "failed", "error": log_string}),
                    log=final_log_message_for_db,
                    attachedFiles=existing_details_files_list, # Pass array directly without JSON conversion
                    client=client
                )
                logger.info(f"{log_prefix} Successfully finalized ReportBlock {current_report_block.id}. attachedFiles: {existing_details_files_list}")
            except Exception as e:
                 logger.exception(f"{log_prefix} Failed to finalize ReportBlock {current_report_block.id}: {e}")
                 if first_block_error_message is None:
                    first_block_error_message = f"Failed to finalize block {block_display_name}: {e}"
            

            if output_json is None and first_block_error_message is None:
                first_block_error_message = log_string or f"Block {block_display_name} failed with unspecified error."
            
            logger.info(f"{log_prefix} Completed processing for block {block_display_name} (ID: {current_report_block.id})")
            tracker.update(current_items=i + 1)

        # === 5. Create ReportBlock Records ===
        # This section is now fully integrated into the main processing loop (Step 4 above).
        # ReportBlocks are created, executed (which may attach files), and then finalized
        # with their log.txt within that single loop.
        # No separate loop is needed here to create/update ReportBlock records from intermediate results.
        logger.info(f"{log_prefix} All block processing and ReportBlock record finalization completed in the main loop.")
        
        tracker.advance_stage() # Advance to next stage (Finalizing Report)

        # === 6. Finalize Report === (This stage was implicitly step 5 before)
        logger.info(f"{log_prefix} Report generation core logic finished.")

        if first_block_error_message:
            logger.warning(f"{log_prefix} Report generation completed with errors. First error: {first_block_error_message}")
        else:
            logger.info(f"{log_prefix} All report blocks completed and results saved successfully.")

        # Return the report_id and the first specific error message (or None if successful)
        return report_id, first_block_error_message

    except Exception as e:
        # This catches critical errors from Task fetching, Tracker init, Metadata extraction, OR core logic.
        final_error_msg = f"Report generation failed: {e}"
        detailed_error = traceback.format_exc()
        logger.exception(f"{log_prefix} {final_error_msg}")

        if tracker:
            try:
                tracker.fail(f"{final_error_msg}\\nDetails:\\n{detailed_error}")
                logger.info(f"{log_prefix} Task status set to FAILED via tracker.")
            except Exception as tracker_fail_err:
                logger.error(f"{log_prefix} Additionally failed to set FAILED status via tracker: {tracker_fail_err}")
                try:
                    # Refetch task for direct update as fallback
                    task_fallback = Task.get_by_id(tracker.task_id, tracker.api_client)
                    if task_fallback:
                        task_fallback.update(status="FAILED", errorMessage=final_error_msg, errorDetails=detailed_error, completedAt=datetime.now(timezone.utc).isoformat())
                        logger.error(f"{log_prefix} Set Task status to FAILED via direct update as fallback.")
                except Exception as final_update_err:
                    logger.error(f"{log_prefix} CRITICAL: Failed to set task status to FAILED via any method after error: {final_update_err}")
        else:
            # Handle case where tracker wasn't initialized (e.g., initial Task fetch failed)
            logger.error(f"{log_prefix} Cannot set final task status as tracker was not initialized.")

        # Return None for report_id and the first error message
        return None, first_block_error_message


# Updated function signature for Celery task
def generate_report(task_id: str):
    """
    Celery task handler for generating a report based on a Task record.
    Fetches task, initializes tracker, calls core logic, and sets final task status.

    Args:
        task_id: The ID of the Task record triggering this report generation.

    Returns:
        None. Task status indicates success or failure.
    """
    api_client = PlexusDashboardClient()
    tracker = None # Initialize tracker later
    log_prefix = f"[ReportGen task_id={task_id}]"
    logger.info(f"{log_prefix} Received report generation task.")

    try:
        # === 1. Fetch Task Record ===
        try:
            task = Task.get_by_id(task_id, api_client)
            if not task:
                raise ValueError(f"Task not found: {task_id}")
            logger.info(f"{log_prefix} Fetched Task record.")
        except Exception as e:
            logger.exception(f"{log_prefix} Critical error: Failed to fetch Task {task_id}. Cannot update status. Error: {e}")
            raise # Re-raise the exception

        # === 2. Initialize Task Progress Tracker ===
        try:
            stage_configs = {
                "Loading Configuration": StageConfig(order=1, status_message="Loading report configuration details."),
                "Initializing Report Record": StageConfig(order=2, status_message="Creating initial database entry for the report."),
                "Parsing Configuration": StageConfig(order=3, status_message="Analyzing report structure and block definitions."),
                "Processing Report Blocks": StageConfig(order=4, status_message="Executing individual report block components.", total_items=0),
                "Finalizing Report": StageConfig(order=5, status_message="Saving results and completing generation."),
            }
            tracker = TaskProgressTracker(
                task_id=task_id,
                stage_configs=stage_configs,
                total_items=0,
                prevent_new_task=True
            )
            logger.info(f"{log_prefix} TaskProgressTracker initialized.")
        except Exception as e:
            logger.exception(f"{log_prefix} Critical error: Failed to initialize TaskProgressTracker for task {task_id}. Error: {e}")
            try:
                # Attempt direct update only if task was successfully fetched
                if 'task' in locals() and task:
                    task.update(status="FAILED", errorMessage=f"Failed to initialize progress tracker: {e}", completedAt=datetime.now(timezone.utc).isoformat())
                    logger.error(f"{log_prefix} Set Task status to FAILED due to tracker initialization error.")
                else:
                    logger.error(f"{log_prefix} Cannot update task status - task object not available.")
            except Exception as update_err:
                logger.error(f"{log_prefix} Additionally failed to update Task status after tracker init error: {update_err}")
            raise # Re-raise the tracker init error

        # === 3. Extract Config from Task Metadata ===
        try:
            if not task.metadata:
                raise ValueError("Task metadata is missing or empty.")
            task_metadata = json.loads(task.metadata)
            report_config_id = task_metadata.get("report_configuration_id")
            account_id = task_metadata.get("account_id")
            # Ensure run_parameters is treated as dict, even if empty in metadata
            run_parameters = task_metadata.get("report_parameters") 
            if run_parameters is None:
                run_parameters = {}
            elif isinstance(run_parameters, str): # Handle accidental string storage
                try:
                    run_parameters = json.loads(run_parameters)
                except json.JSONDecodeError:
                    logger.warning(f"{log_prefix} 'report_parameters' in metadata was a non-JSON string. Treating as empty dict.")
                    run_parameters = {}
            
            if not isinstance(run_parameters, dict):
                 logger.warning(f"{log_prefix} 'report_parameters' in metadata was not a dict or JSON string. Treating as empty dict. Type: {type(run_parameters)}")
                 run_parameters = {}

            if not report_config_id:
                raise ValueError("'report_configuration_id' not found in Task metadata.")
            if not account_id:
                raise ValueError("'account_id' not found in Task metadata.")
            logger.info(f"{log_prefix} Extracted config: report_config_id={report_config_id}, account_id={account_id}")
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            error_msg = f"Failed to extract configuration from Task metadata: {e}"
            logger.error(f"{log_prefix} {error_msg}")
            logger.debug(f"{log_prefix} Task metadata content: {task.metadata}")
            tracker.fail(error_msg)
            raise # Stop execution

        # === 4. Call Core Generation Logic ===
        logger.info(f"{log_prefix} Calling _generate_report_core...")
        report_id, first_block_error_message = _generate_report_core(
            report_config_id=report_config_id,
            account_id=account_id,
            run_parameters=run_parameters,
            client=api_client,
            tracker=tracker,
            log_prefix_override=log_prefix
        )
        logger.info(f"{log_prefix} _generate_report_core finished. Report ID: {report_id}, First Error: {first_block_error_message}")

        # === 5. Mark Task Status based on Core Logic Result ===
        if first_block_error_message is None:
            tracker.complete()
            logger.info(f"{log_prefix} Report generation task finished successfully.")
        else:
            # Use the specific error message from the core logic
            tracker.fail(first_block_error_message)
            logger.error(f"{log_prefix} Report generation task finished with errors: {first_block_error_message}")

    except Exception as e:
        # This catches critical errors from Task fetching, Tracker init, Metadata extraction, OR core logic.
        final_error_msg = f"Report generation failed: {e}"
        detailed_error = traceback.format_exc()
        logger.exception(f"{log_prefix} {final_error_msg}")

        if tracker:
            try:
                tracker.fail(f"{final_error_msg}\\nDetails:\\n{detailed_error}")
                logger.info(f"{log_prefix} Task status set to FAILED via tracker.")
            except Exception as tracker_fail_err:
                logger.error(f"{log_prefix} Additionally failed to set FAILED status via tracker: {tracker_fail_err}")
                try:
                    # Refetch task for direct update as fallback
                    task_fallback = Task.get_by_id(tracker.task_id, tracker.api_client)
                    if task_fallback:
                        task_fallback.update(status="FAILED", errorMessage=final_error_msg, errorDetails=detailed_error, completedAt=datetime.now(timezone.utc).isoformat())
                        logger.error(f"{log_prefix} Set Task status to FAILED via direct update as fallback.")
                except Exception as final_update_err:
                    logger.error(f"{log_prefix} CRITICAL: Failed to set task status to FAILED via any method after error: {final_update_err}")
        else:
            # Handle case where tracker wasn't initialized (e.g., initial Task fetch failed)
            logger.error(f"{log_prefix} Cannot set final task status as tracker was not initialized.")

# --- Placeholder for future Jinja2 integration ---
# def render_report_output(template_str: str, block_data: Dict[str, Any]) -> str:
#     """Renders the final report output using Jinja2."""
#     env = jinja2.Environment(loader=jinja2.BaseLoader())
#     template = env.from_string(template_str)
#     # The 'block_data' needs to be structured in a way that the template can easily access it,
#     # perhaps keyed by block name or position.
#     return template.render(blocks=block_data)
# --- End Placeholder --- 