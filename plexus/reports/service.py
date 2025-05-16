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
    block_def: dict, report_params: dict, api_client: PlexusDashboardClient
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Instantiates and runs a specific report block class.

    Args:
        block_def: Dictionary containing block definition ('class_name', 'config', 'block_name', 'position').
        report_params: General parameters passed to the report run.
        api_client: The PlexusDashboardClient instance.

    Returns:
        Tuple (output_json, log_string)
        - output_json: JSON-serializable dictionary from the block's generate method.
        - log_string: Optional log output from the block.
        Returns (None, Error Message String) on failure.
    """
    class_name = block_def["class_name"]
    block_config = block_def["config"]
    block_name = block_def.get("block_name", f"Block at position {block_def.get('position', 'N/A')}")
    log_prefix = f"[ReportBlock {block_name} ({class_name})]"
    logger.info(f"{log_prefix} Instantiating and running block.")

    try:
        # Find the class in the registry
        block_class = BLOCK_CLASSES.get(class_name)
        if not block_class:
            # Simplify the error message
            error_msg = f"Report block class '{class_name}' not found."
            logger.error(f"{log_prefix} {error_msg}")
            # Return None for data, and the error message as the log
            return None, error_msg

        # Instantiate the block
        logger.debug(f"{log_prefix} Instantiating with config: {block_config}")
        block_instance = block_class(config=block_config, params=report_params, api_client=api_client)

        # Run the block's generate method
        logger.debug(f"{log_prefix} Calling generate method...")
        
        # Check if the generate method is a coroutine (async)
        import inspect
        if inspect.iscoroutinefunction(block_instance.generate):
            logger.debug(f"{log_prefix} Detected async generate method, using asyncio.run")
            import asyncio
            output_json, log_string = asyncio.run(block_instance.generate())
        else:
            # Regular synchronous method
            output_json, log_string = block_instance.generate()
            
        logger.info(f"{log_prefix} Block execution finished successfully.")
        logger.debug(f"{log_prefix} Output JSON: {str(output_json)[:200]}...") # Log snippet
        logger.debug(f"{log_prefix} Log String: {log_string}")

        # Ensure output is JSON serializable before returning
        try:
            json.dumps(output_json)
        except TypeError as json_err:
            logger.error(f"{log_prefix} Block output is not JSON serializable: {json_err}")
            raise ValueError(f"Block output is not JSON serializable: {json_err}") from json_err

        return output_json, log_string

    except Exception as e:
        error_msg = f"Error running block {block_name} ({class_name}): {e}"
        detailed_error = traceback.format_exc()
        logger.exception(f"{log_prefix} {error_msg}")
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

        block_results = []
        for i, block_def in enumerate(block_definitions):
            position = block_def.get("position", i)
            block_name = block_def.get("block_name", f"Block at position {position}")
            logger.info(f"{log_prefix} Processing block {i+1}/{num_blocks}: {block_name} (Pos: {position})")

            output_json, log_string = _instantiate_and_run_block(
                block_def=block_def,
                report_params=run_parameters,
                api_client=client
            )

            block_results.append({
                "position": position,
                "name": block_def.get("block_name"),
                "type": block_def["class_name"],  # Use the class_name as the type
                "output": output_json,
                "log": log_string
            })

            if output_json is None:
                block_error = log_string or f"Block {i+1}/{num_blocks} ({block_name}) failed with unspecified error."
                if first_block_error_message is None:
                    first_block_error_message = block_error # Capture the first error
                logger.error(f"{log_prefix} Block {i+1}/{num_blocks} ({block_name}) failed. Error: {block_error}")
            else:
                logger.info(f"{log_prefix} Block {i+1}/{num_blocks} ({block_name}) completed successfully.")

            tracker.update(current_items=i + 1)

        tracker.advance_stage() # Advance to next stage (Finalizing Report)

        # === 5. Create ReportBlock Records ===
        if report_id:
            logger.info(f"{log_prefix} Creating ReportBlock database records for {len(block_results)} blocks.")
            try:
                created_block_ids = []
                for result in block_results:
                    try:
                        output_json_str = json.dumps(result["output"] if result["output"] is not None else {})
                        
                        # Store log content in S3 instead of directly in the ReportBlock record
                        details_files = []
                        log_content = result.get("log")
                        
                        logger.info(f"{log_prefix} Processing block {result.get('name', 'unnamed')}:")
                        logger.info(f"{log_prefix} S3_UTILS_AVAILABLE = {S3_UTILS_AVAILABLE}")
                        
                        # Log the log content details to understand what we're working with
                        if log_content is None:
                            logger.info(f"{log_prefix} Log content is None, skipping S3 upload")
                        elif log_content == "":
                            logger.info(f"{log_prefix} Log content is empty string, skipping S3 upload")
                        else:
                            log_content_length = len(log_content)
                            logger.info(f"{log_prefix} Log content is present: {log_content_length} characters")
                            log_preview = log_content[:100] + "..." if len(log_content) > 100 else log_content
                            logger.info(f"{log_prefix} Log content preview: {log_preview}")
                        
                        # Only upload log file if there's actual content AND S3 utils are available
                        if log_content and S3_UTILS_AVAILABLE:
                            logger.info(f"{log_prefix} Starting S3 upload path for log content")
                            try:
                                # Create a temporary ReportBlock to get an ID
                                logger.info(f"{log_prefix} Creating temporary ReportBlock")
                                temp_block = ReportBlock.create(
                                    reportId=report_id,
                                    position=result["position"],
                                    name=result["name"],
                                    type=result["type"],
                                    output=output_json_str,
                                    log="See log.txt in detailsFiles", # Reference to the file
                                    client=client
                                )
                                logger.info(f"{log_prefix} Created temporary ReportBlock with ID {temp_block.id}")
                                
                                # Upload log content to S3
                                logger.info(f"{log_prefix} Starting upload of log file to S3")
                                log_file_info = upload_report_block_file(
                                    report_block_id=temp_block.id,
                                    file_name="log.txt",
                                    content=log_content,
                                    content_type="text/plain"
                                )
                                logger.info(f"{log_prefix} S3 upload completed successfully: {log_file_info}")
                                
                                # Add file info to details_files
                                details_files.append(log_file_info)
                                logger.info(f"{log_prefix} Added file info to details_files: {details_files}")
                                
                                # Update the block with details_files
                                details_files_json = json.dumps(details_files)
                                logger.info(f"{log_prefix} Updating ReportBlock with detailsFiles JSON: {details_files_json}")
                                temp_block.update(
                                    detailsFiles=details_files_json,
                                    client=client
                                )
                                logger.info(f"{log_prefix} Successfully updated ReportBlock with detailsFiles")
                                
                                created_block_ids.append(temp_block.id)
                                logger.info(f"{log_prefix} Created ReportBlock with ID {temp_block.id} and uploaded log to S3")
                                
                            except Exception as s3_error:
                                logger.exception(f"{log_prefix} Failed to upload log to S3: {s3_error}. Error details:", exc_info=True)
                                # Fall back to storing log directly in the ReportBlock
                                logger.info(f"{log_prefix} Falling back to storing log directly in ReportBlock (truncated if needed)")
                                block_record = ReportBlock.create(
                                    reportId=report_id,
                                    position=result["position"],
                                    name=result["name"],
                                    type=result["type"],
                                    output=output_json_str,
                                    log=log_content[:10000] if log_content else None,  # Truncate if too long
                                    client=client
                                )
                                created_block_ids.append(block_record.id)
                        else:
                            # Either no log content or S3 utils not available
                            if not log_content:
                                logger.info(f"{log_prefix} No log content for block {result.get('name', 'unnamed')}, creating block without S3 upload")
                            else:
                                logger.info(f"{log_prefix} S3 utils not available, storing log directly in ReportBlock")
                                
                            # Create block normally without S3
                            block_record = ReportBlock.create(
                                reportId=report_id,
                                position=result["position"],
                                name=result["name"],
                                type=result["type"],
                                output=output_json_str,
                                log=log_content[:10000] if log_content else None,  # Truncate if too long
                                client=client
                            )
                            created_block_ids.append(block_record.id)
                    except Exception as e:
                        logger.exception(f"{log_prefix} Failed to create ReportBlock record for block at pos {result.get('position')}: {e}")
                        if first_block_error_message is None:
                            first_block_error_message = f"Failed to save results for block at pos {result.get('position')}: {e}"
                        # Don't raise here, try to save other blocks, but ensure overall failure is recorded
                logger.info(f"{log_prefix} Finished creating ReportBlock records (attempted {len(block_results)}, created {len(created_block_ids)})." )
            except Exception as e: # Catch broader errors during the loop setup itself
                logger.exception(f"{log_prefix} Error during ReportBlock creation loop: {e}")
                if first_block_error_message is None:
                    first_block_error_message = f"Error saving block results: {e}"
        else:
             logger.error(f"{log_prefix} Cannot create ReportBlock records because Report ID is missing.")
             if first_block_error_message is None:
                  first_block_error_message = "Failed to create initial Report record."

        # === 6. Finalize ===
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
                    task_fallback = Task.get_by_id(task_id, api_client)
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
                    task_fallback = Task.get_by_id(task_id, api_client)
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