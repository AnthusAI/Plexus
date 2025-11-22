from typing import Any, Dict, Optional, Tuple, List
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from collections import Counter
import json # Ensure json import at the top
import yaml # For YAML formatted output with contextual comments

from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.dashboard.api.models.item import Item  # Add Item model import

from .base import BaseReportBlock
from . import feedback_utils

logger = logging.getLogger(__name__)


class FeedbackAnalysis(BaseReportBlock):
    """
    Analyzes feedback data using Gwet's AC1 agreement coefficient.
    
    This block retrieves FeedbackItem records and compares initial and final answer values
    to calculate agreement scores using Gwet's AC1.

    If a specific 'score_id' is provided in the config, it analyzes only that score.
    Otherwise, it analyzes all scores associated with the provided 'scorecard' that
    have a mapping to a Plexus Score with an externalId.
    
    Config:
        scorecard (str): Scorecard identifier. This is REQUIRED.
        days (int, optional): Number of days in the past to analyze (default: 14).
                              FeedbackItems updated within this period will be considered.
        start_date (str, optional): Start date for analysis in YYYY-MM-DD format.
                                   If provided, overrides 'days'.
        end_date (str, optional): End date for analysis in YYYY-MM-DD format.
                                 Defaults to today if not specified.
        score_id (str, optional): Specific score ID to analyze.
                                 If specified, only this score will be analyzed.
    """
    
    # Class-level defaults for name and description
    DEFAULT_NAME = "Feedback Analysis"
    DEFAULT_DESCRIPTION = "Inter-rater Reliability Assessment"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetches feedback data and performs agreement analysis."""
        self.log_messages = []
        final_output_data = None

        try:
            self._log("Starting FeedbackAnalysis block generation.")
            # Only log config keys, not full values
            self._log(f"Config keys: {list(self.config.keys())}")

            # --- 1. Extract and Validate Configuration ---
            cc_scorecard_id_param = self.config.get("scorecard")
            if not cc_scorecard_id_param:
                self._log("ERROR: 'scorecard' missing in block configuration.", level="ERROR")
                raise ValueError("'scorecard' is required in the block configuration.")
            self._log(f"Scorecard ID from config: {cc_scorecard_id_param}")

            # Check if "all" mode is requested
            if str(cc_scorecard_id_param).lower() == "all":
                self._log("Detected 'all scorecards' mode - will analyze every scorecard in the account")
                return await self._generate_all_scorecards_analysis()

            # Otherwise, proceed with single scorecard analysis
            return await self._generate_single_scorecard_analysis(cc_scorecard_id_param)

        except ValueError as ve:
            self._log(f"Configuration or Value Error: {ve}")
            final_output_data = {"error": str(ve), "scores": []}
            summary_log = f"Error: {str(ve)}"
            detailed_log = "\n".join(self.log_messages) if self.log_messages else f"Error: {str(ve)}"
            return final_output_data, detailed_log
        except Exception as e:
            self._log(f"ERROR during FeedbackAnalysis generation: {str(e)}", level="ERROR")
            import traceback
            self._log(traceback.format_exc())
            final_output_data = {"error": str(e), "scores": []}
            summary_log = f"Error: {str(e)}"
            detailed_log = "\n".join(self.log_messages) if self.log_messages else f"Error: {str(e)}"
            return final_output_data, detailed_log

    async def _generate_single_scorecard_analysis(self, cc_scorecard_id_param: str, skip_indexed_items: bool = False) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Analyzes a single scorecard. This is the original generate() logic extracted for reuse.

        Args:
            cc_scorecard_id_param: The scorecard ID to analyze
            skip_indexed_items: If True, skip creating detailed indexed feedback item files (for all_scorecards mode)
        """
        final_output_data = None

        try:
            days = int(self.config.get("days", 14))
            start_date_str = self.config.get("start_date")
            end_date_str = self.config.get("end_date")
            cc_question_id_param = self.config.get("score_id") # Optional CC Question ID

            # Parse date strings
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            else:
                start_date = datetime.now() - timedelta(days=days)
            # Make start_date UTC aware (assuming naive datetime is intended as UTC)
            start_date = start_date.replace(tzinfo=timezone.utc)
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            else:
                end_date = datetime.now()
            
            # Ensure end_date is at the end of the day for correct filtering
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            # Make end_date UTC aware (assuming naive datetime is intended as UTC)
            end_date = end_date.replace(tzinfo=timezone.utc)

            self._log(f"Effective date range for filtering FeedbackItems: {start_date.isoformat()} to {end_date.isoformat()}")
            if cc_question_id_param:
                self._log(f"Call Criteria Question ID from config: {cc_question_id_param}")

            # --- 2. Resolve Plexus Scorecard ---
            self._log(f"Resolving Plexus Scorecard for parameter: {cc_scorecard_id_param}...")
            try:
                # Try to determine if this is a UUID or external ID
                # UUIDs are typically 36 characters with dashes (e.g., "f4076c72-e74b-4eaf-afd6-d4f61c9f0142")
                # External IDs are typically shorter numeric strings (e.g., "97")
                is_uuid = len(str(cc_scorecard_id_param)) > 20 and '-' in str(cc_scorecard_id_param)

                if is_uuid:
                    # Try to fetch by ID (UUID)
                    self._log(f"Parameter appears to be a UUID, fetching by ID...")
                    plexus_scorecard_obj = await asyncio.to_thread(
                        Scorecard.get_by_id,
                        id=str(cc_scorecard_id_param),
                        client=self.api_client
                    )
                else:
                    # Try to fetch by external ID
                    self._log(f"Parameter appears to be an external ID, fetching by external_id...")
                    plexus_scorecard_obj = await asyncio.to_thread(
                        Scorecard.get_by_external_id,
                        external_id=str(cc_scorecard_id_param),
                        client=self.api_client
                    )

                if not plexus_scorecard_obj:
                    msg = f"Plexus Scorecard not found for parameter: {cc_scorecard_id_param}"
                    self._log(f"ERROR: {msg}", level="ERROR")
                    raise ValueError(msg)
                self._log(f"Found Plexus Scorecard: '{plexus_scorecard_obj.name}' (ID: {plexus_scorecard_obj.id})")
            except Exception as e:
                self._log(f"ERROR resolving Plexus Scorecard: {e}", level="ERROR")
                raise

            # --- 3. Determine Plexus Score(s) to Process ---
            scores_to_process = [] # List of {'plexus_score_id': str, 'plexus_score_name': str, 'cc_question_id': str}
            
            if cc_question_id_param:
                self._log(f"Looking up specific Plexus Score for CC Question ID: {cc_question_id_param} on Plexus Scorecard: {plexus_scorecard_obj.id}")
                try:
                    plexus_score_obj = await asyncio.to_thread(
                        Score.get_by_external_id,
                        external_id=str(cc_question_id_param),
                        scorecard_id=plexus_scorecard_obj.id,
                        client=self.api_client
                    )
                    if plexus_score_obj:
                        scores_to_process.append({
                            'plexus_score_id': plexus_score_obj.id,
                            'plexus_score_name': plexus_score_obj.name,
                            'cc_question_id': str(cc_question_id_param)
                        })
                        self._log(f"Found specific Plexus Score: '{plexus_score_obj.name}' (ID: {plexus_score_obj.id})")
                    else:
                        self._log(f"WARNING: Plexus Score not found for CC Question ID: {cc_question_id_param} on Scorecard '{plexus_scorecard_obj.name}'. This score will be skipped.", level="WARNING")
                except Exception as e:
                    self._log(f"ERROR looking up specific Plexus Score (CC Question ID: {cc_question_id_param}): {e}. This score will be skipped.", level="ERROR")
            else:
                self._log(f"Fetching all Plexus Scores for Scorecard '{plexus_scorecard_obj.name}' (ID: {plexus_scorecard_obj.id}) to find mappable scores.")
                # Use the utility function to fetch scores
                try:
                    scores_to_process = await feedback_utils.fetch_scores_for_scorecard(self.api_client, plexus_scorecard_obj.id)
                    self._log(f"Identified and sorted {len(scores_to_process)} Plexus Scores with externalIds to process.")
                except Exception as e:
                    self._log(f"ERROR fetching and sorting scores for Plexus Scorecard '{plexus_scorecard_obj.name}': {e}", level="ERROR")
                    # Continue if some scores were found before error, or caught by next check
            
            if not scores_to_process:
                msg = "No Plexus Scores identified for analysis (either none found or none had a mappable CC Question ID, or an error occurred during fetching/sorting)."
                self._log(f"ERROR: {msg}", level="ERROR")
                # Return a structure indicating no data, but not an error state for the report block itself.
                return {
                    "overall_ac1": None, "total_items": 0, "total_mismatches": 0, "accuracy": None,
                    "scores": [],
                    "total_feedback_items_retrieved": 0,
                    "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                    "message": msg,
                    "classes_count": 2,  # Default to binary classification for overall
                    "warning": None,
                    "warnings": None,
                    "notes": None,
                    "discussion": None
                }, "\n".join(self.log_messages)

            # --- 4. Fetch and Analyze Feedback for Each Score ---
            all_feedback_items_retrieved_count = 0
            all_date_filtered_feedback_items = [] # For overall calculation
            per_score_analysis_results = []
            
            # Store the report block ID when created for attaching files later
            report_block_id = None
            if hasattr(self, 'report_block_id') and self.report_block_id:
                report_block_id = self.report_block_id
            
            for score_index, score_info in enumerate(scores_to_process):
                self._log(f"--- Processing Score: '{score_info['plexus_score_name']}' (ID: {score_info['plexus_score_id']}, CC ID: {score_info['cc_question_id']}) ---")
                
                items_for_this_score = await self._fetch_feedback_items_for_score(
                    plexus_scorecard_id=plexus_scorecard_obj.id,
                    plexus_score_id=score_info['plexus_score_id'],
                    start_date=start_date,
                    end_date=end_date
                )
                all_feedback_items_retrieved_count += len(items_for_this_score)
                self._log(f"Retrieved {len(items_for_this_score)} FeedbackItems for this score within date range: {start_date.date()} - {end_date.date()}")
                
                all_date_filtered_feedback_items.extend(items_for_this_score)

                if not items_for_this_score:
                    self._log("No feedback items for this score within the date range.", level="WARNING")
                    analysis_for_this_score = {
                        "score_id": score_info['plexus_score_id'],
                        "score_name": score_info['plexus_score_name'],
                        "cc_question_id": score_info['cc_question_id'],
                        "ac1": None, "item_count": 0, "mismatches": 0, "agreements": 0, "accuracy": None,
                        "message": "No feedback items found in the specified date range.",
                        "classes_count": 2,  # Default to binary classification
                        "label_distribution": {},
                        "confusion_matrix": None,
                        "class_distribution": [],
                        "predicted_class_distribution": [],
                        "precision": None,
                        "recall": None,
                        "warning": "No data.",
                        "warnings": "No data.",
                        "notes": None,
                        "discussion": None
                    }
                else:
                    try:
                        analysis_for_this_score = self._analyze_feedback_data_gwet(
                            feedback_items=items_for_this_score,
                            score_id_info=score_info['plexus_score_id'] # For logging within analysis
                        )
                        analysis_for_this_score["score_id"] = score_info['plexus_score_id']
                        analysis_for_this_score["score_name"] = score_info['plexus_score_name']
                        analysis_for_this_score["cc_question_id"] = score_info['cc_question_id']

                        # Create indexed feedback items structure for this score (skip if requested)
                        if not skip_indexed_items:
                            indexed_items = await self._create_indexed_feedback_items(items_for_this_score)

                            # Export the indexed items to a JSON file
                            if indexed_items and report_block_id:
                                file_name = f"score-{score_index + 1}-results.json"
                                self._log(f"Creating indexed feedback items JSON file: {file_name}")

                                # Write the indexed items to a detail file
                                detailed_json_content = json.dumps(indexed_items, default=str, indent=2)
                                try:
                                    # Log the state of the ReportBlock before attaching file
                                    try:
                                        block_before = ReportBlock.get_by_id(report_block_id, self.api_client)
                                        if block_before:
                                            self._log(f"BEFORE ATTACH - ReportBlock {report_block_id} state: attachedFiles={block_before.attachedFiles}", level="DEBUG")
                                    except Exception as e:
                                        self._log(f"Error fetching ReportBlock before attach: {e}", level="WARNING")

                                    # Attach the file - this now returns a path string, not an object
                                    file_path = self.attach_detail_file(
                                        report_block_id=report_block_id,
                                        file_name=file_name,
                                        content=detailed_json_content,
                                        content_type="application/json"
                                    )
                                    self._log(f"Successfully attached indexed feedback items file: {file_name}, path: {file_path}")

                                    # Log the state of the ReportBlock after attaching file
                                    try:
                                        block_after = ReportBlock.get_by_id(report_block_id, self.api_client)
                                        if block_after:
                                            self._log(f"AFTER ATTACH - ReportBlock {report_block_id} state: attachedFiles={block_after.attachedFiles}", level="INFO")

                                            # Try to parse and validate the attachedFiles content
                                            if block_after.attachedFiles:
                                                try:
                                                    # Check if already a list
                                                    if isinstance(block_after.attachedFiles, list):
                                                        paths_list = block_after.attachedFiles
                                                        self._log(f"attachedFiles is already a list with {len(paths_list)} paths: {paths_list}", level="INFO")
                                                    else:
                                                        # For backward compatibility - try to parse JSON if it's a string
                                                        paths_list = json.loads(block_after.attachedFiles)
                                                        self._log(f"attachedFiles parsed from JSON string (for backward compatibility): {paths_list}", level="INFO")
                                                except json.JSONDecodeError as je:
                                                    self._log(f"attachedFiles is not valid JSON but should be a list: {je}", level="WARNING")
                                            else:
                                                self._log(f"attachedFiles is empty or None", level="WARNING")
                                    except Exception as e:
                                        self._log(f"Error fetching ReportBlock after attach: {e}", level="WARNING")

                                    # Add reference to the file in the analysis result - just the filename since paths are now in attachedFiles
                                    analysis_for_this_score["indexed_items_file"] = file_name
                                except Exception as e:
                                    self._log(f"Error attaching indexed feedback items file: {e}", level="ERROR")
                                    import traceback
                                    self._log(f"Error details: {traceback.format_exc()}", level="ERROR")
                        else:
                            self._log(f"Skipping indexed items creation for score '{score_info['plexus_score_name']}' (all_scorecards mode)", level="DEBUG")
                    except Exception as e:
                        self._log(f"Error analyzing score {score_info['plexus_score_name']}: {e}", level="ERROR")
                        raise  # Re-raise to be caught by outer try/except
                
                per_score_analysis_results.append(analysis_for_this_score)
                # Only log a summary instead of the full analysis details
                accuracy_str = f"{analysis_for_this_score.get('accuracy'):.2f}%" if analysis_for_this_score.get('accuracy') is not None else "N/A"
                self._log(f"Analysis summary for score '{score_info['plexus_score_name']}': AC1={analysis_for_this_score.get('ac1')}, Items={analysis_for_this_score.get('item_count')}, Agreements={analysis_for_this_score.get('agreements')}, Mismatches={analysis_for_this_score.get('mismatches')}, Accuracy={accuracy_str}, Classes={analysis_for_this_score.get('classes_count')}")

            # --- 5. Calculate Overall Metrics ---
            self._log(f"Calculating overall metrics from {len(all_date_filtered_feedback_items)} date-filtered feedback items across all processed scores.")
            if not all_date_filtered_feedback_items:
                overall_analysis = {"ac1": None, "item_count": 0, "mismatches": 0, "agreements": 0, "accuracy": None, "classes_count": 2, 
                                    "label_distribution": {}, "confusion_matrix": None, "class_distribution": [], 
                                    "predicted_class_distribution": [], "precision": None, "recall": None, "warning": None, "warnings": None, "notes": None, "discussion": None}
                self._log("No date-filtered items available for overall analysis.", level="WARNING")
            else:
                # Use a generic score_id_info for the overall log
                overall_analysis = self._analyze_feedback_data_gwet(all_date_filtered_feedback_items, "Overall") 
            
            # Log a summary of the overall analysis instead of full details
            accuracy_str = f"{overall_analysis.get('accuracy'):.2f}%" if overall_analysis.get('accuracy') is not None else "N/A"
            self._log(f"Overall analysis summary: AC1={overall_analysis.get('ac1')}, Items={overall_analysis.get('item_count')}, Agreements={overall_analysis.get('agreements')}, Mismatches={overall_analysis.get('mismatches')}, Accuracy={accuracy_str}, Classes={overall_analysis.get('classes_count', 2)}")

            # --- 6. Generate Summary Warning ---
            summary_warning = self._generate_summary_warning(per_score_analysis_results)
            
            # --- 7. Structure Final Output ---
            final_output_data = {
                "overall_ac1": overall_analysis.get("ac1"), # Renamed from overall_ac1
                "total_items": overall_analysis.get("item_count"), # Renamed from item_count
                "total_mismatches": overall_analysis.get("mismatches"), # Renamed from mismatches
                "total_agreements": overall_analysis.get("agreements"), # Renamed from agreements
                "accuracy": overall_analysis.get("accuracy"), # Renamed from accuracy
                "scores": per_score_analysis_results,
                "total_feedback_items_retrieved": all_feedback_items_retrieved_count,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "message": f"Processed {len(scores_to_process)} score(s)." if scores_to_process else "No scores were processed.",
                "classes_count": overall_analysis.get("classes_count", 2),
                "label_distribution": overall_analysis.get("label_distribution", {}),
                # Add the new data from our enhanced analysis
                "confusion_matrix": overall_analysis.get("confusion_matrix"),
                "class_distribution": overall_analysis.get("class_distribution", []),
                "predicted_class_distribution": overall_analysis.get("predicted_class_distribution", []),
                "precision": overall_analysis.get("precision"),
                "recall": overall_analysis.get("recall"),
                "warning": summary_warning,  # Summary warning for ReportBlock display
                "warnings": overall_analysis.get("warnings"),  # Keep individual warnings for backwards compatibility
                "notes": overall_analysis.get("notes"),
                "discussion": overall_analysis.get("discussion"),
                # Add block metadata for frontend display
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION
            }
            # Don't log the full output data - it's redundant and can be large
            self._log(f"Finished generating analysis for {len(scores_to_process)} scores with {all_feedback_items_retrieved_count} total feedback items.")

            # Create a summary log for the ReportBlock.log field (keep it short)
            summary_log = f"Processed {len(scores_to_process)} score(s) across {all_feedback_items_retrieved_count} feedback items. See detailed logs in log.txt."
            
            # The full detailed log will be stored in the S3 file
            detailed_log = "\n".join(self.log_messages) if self.log_messages else "No logs generated."

        except ValueError as ve:
            self._log(f"Configuration or Value Error: {ve}")
            final_output_data = {"error": str(ve), "scores": []}
            summary_log = f"Error: {str(ve)}"
            detailed_log = "\n".join(self.log_messages) if self.log_messages else f"Error: {str(ve)}"
        except Exception as e:
            self._log(f"ERROR during FeedbackAnalysis generation: {str(e)}", level="ERROR")
            import traceback
            self._log(traceback.format_exc())
            final_output_data = {"error": str(e), "scores": []}
            summary_log = f"Error: {str(e)}"
            detailed_log = "\n".join(self.log_messages) if self.log_messages else f"Error: {str(e)}"

        # Return YAML formatted output with contextual comments
        if final_output_data and not final_output_data.get("error"):
            try:
                contextual_comment = """# Feedback Analysis Report Output
# 
# This is the structured output from a feedback analysis process that:
# 1. Retrieves feedback items from scorecards within a specified time range
# 2. Analyzes agreement between initial and final answer values using Gwet's AC1 coefficient
# 3. Provides statistical measures of inter-rater reliability and agreement
# 4. Generates insights about feedback quality and consistency across evaluators
#
# The output contains agreement scores, statistical measures, detailed breakdowns,
# and analytical insights for understanding feedback consistency and reliability.

"""
                yaml_output = yaml.dump(final_output_data, indent=2, allow_unicode=True, sort_keys=False)
                final_output_data = contextual_comment + yaml_output
            except Exception as e:
                logger.error(f"Failed to create YAML formatted output: {e}")
                # Fallback to basic YAML without comments
                final_output_data = yaml.dump(final_output_data, indent=2, allow_unicode=True, sort_keys=False)

        # Always return the detailed_log as the second return value to ensure logs are saved to S3
        # The service.py code will use this to upload to S3
        return final_output_data, detailed_log

    async def _fetch_all_scorecards(self) -> List[Scorecard]:
        """
        Fetches all scorecards for the current account.

        Returns:
            List of Scorecard objects
        """
        self._log("Fetching all scorecards for the account...")

        # Get account_id
        account_id = self.params.get("account_id")
        if not account_id:
            if hasattr(self.api_client, 'context') and self.api_client.context:
                account_id = self.api_client.context.account_id

        if not account_id:
            self._log("ERROR: Could not determine account_id for fetching scorecards", level="ERROR")
            return []

        # Use the utility function
        scorecards = await feedback_utils.fetch_all_scorecards(self.api_client, account_id)
        
        if scorecards:
            self._log(f"Found {len(scorecards)} scorecards for account {account_id}")
        else:
            self._log("No scorecards found or unexpected response format", level="WARNING")
        
        return scorecards

    async def _analyze_single_scorecard_for_all_mode(self, scorecard: Scorecard, idx: int, total: int) -> Dict[str, Any]:
        """
        Analyzes a single scorecard and returns a complete result dict.
        This is designed to be run in parallel with other scorecards.

        Args:
            scorecard: The Scorecard object to analyze
            idx: The index of this scorecard (1-based, for logging)
            total: Total number of scorecards being analyzed (for logging)

        Returns:
            Dictionary with scorecard analysis results or error placeholder
        """
        self._log(f"=== [{idx}/{total}] Analyzing '{scorecard.name}' (ID: {scorecard.id}, External ID: {scorecard.externalId}) ===")

        try:
            # Run analysis for this scorecard, skipping detailed item files to reduce data size
            analysis_output, analysis_log = await self._generate_single_scorecard_analysis(
                scorecard.id,
                skip_indexed_items=True  # Skip detailed feedback items for all_scorecards mode
            )

            # Parse the YAML output back to dict if needed
            if isinstance(analysis_output, str):
                # Remove the comment header if present
                yaml_content = analysis_output
                if yaml_content.startswith("#"):
                    lines = yaml_content.split('\n')
                    # Find where the actual YAML starts (after comments)
                    yaml_start = 0
                    for i, line in enumerate(lines):
                        if line and not line.strip().startswith('#'):
                            yaml_start = i
                            break
                    yaml_content = '\n'.join(lines[yaml_start:])

                try:
                    analysis_dict = yaml.safe_load(yaml_content)
                except:
                    # If parsing fails, assume it's already a dict or use as-is
                    analysis_dict = analysis_output if isinstance(analysis_output, dict) else {}
            else:
                analysis_dict = analysis_output

            # Add scorecard metadata to the result
            scorecard_result = {
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "scorecard_external_id": scorecard.externalId,
                # Include all the analysis data from the single scorecard analysis
                **analysis_dict
            }

            # Log summary
            ac1 = analysis_dict.get('overall_ac1')
            total_items = analysis_dict.get('total_items', 0)
            accuracy = analysis_dict.get('accuracy')
            self._log(f"[{idx}/{total}] Completed '{scorecard.name}': AC1={ac1}, Items={total_items}, Accuracy={accuracy}")

            return scorecard_result

        except Exception as e:
            self._log(f"[{idx}/{total}] Error analyzing '{scorecard.name}': {e}", level="ERROR")
            import traceback
            self._log(traceback.format_exc())

            # Return placeholder for failed scorecard
            return {
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "scorecard_external_id": scorecard.externalId,
                "overall_ac1": None,
                "total_items": 0,
                "error": str(e),
                "scores": []
            }

    async def _generate_all_scorecards_analysis(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Analyzes all scorecards in the account and ranks them by AC1 performance.
        This generates metrics and confusion matrices for each scorecard, but skips
        detailed individual feedback item files to keep the output manageable.
        """
        self._log("Starting 'all scorecards' analysis mode")
        self._log("Note: Detailed feedback item drill-down files will be skipped to reduce data size")

        # Get date configuration
        days = int(self.config.get("days", 14))
        start_date_str = self.config.get("start_date")
        end_date_str = self.config.get("end_date")

        # Parse date strings
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        else:
            start_date = datetime.now() - timedelta(days=days)
        start_date = start_date.replace(tzinfo=timezone.utc)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            end_date = datetime.now()

        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        end_date = end_date.replace(tzinfo=timezone.utc)

        self._log(f"Date range: {start_date.isoformat()} to {end_date.isoformat()}")

        # Fetch all scorecards
        scorecards = await self._fetch_all_scorecards()

        if not scorecards:
            msg = "No scorecards found for this account"
            self._log(f"ERROR: {msg}", level="ERROR")
            return {
                "mode": "all_scorecards",
                "error": msg,
                "total_scorecards_analyzed": 0,
                "scorecards": []
            }, "\n".join(self.log_messages)

        self._log(f"Will analyze {len(scorecards)} scorecards in parallel")

        # Create tasks for parallel analysis
        analysis_tasks = []
        for idx, scorecard in enumerate(scorecards, 1):
            task = self._analyze_single_scorecard_for_all_mode(scorecard, idx, len(scorecards))
            analysis_tasks.append(task)

        # Run all analyses in parallel
        self._log(f"Starting parallel analysis of {len(analysis_tasks)} scorecards...")
        scorecard_results = await asyncio.gather(*analysis_tasks, return_exceptions=False)

        # Filter out scorecards with no feedback data
        scorecards_before_filter = len(scorecard_results)
        scorecard_results = [result for result in scorecard_results if result.get('total_items', 0) > 0]
        scorecards_filtered = scorecards_before_filter - len(scorecard_results)

        if scorecards_filtered > 0:
            self._log(f"Filtered out {scorecards_filtered} scorecard(s) with no feedback data")

        if not scorecard_results:
            msg = "No scorecards with feedback data found"
            self._log(f"WARNING: {msg}", level="WARNING")
            return {
                "mode": "all_scorecards",
                "message": msg,
                "total_scorecards_analyzed": 0,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "scorecards": []
            }, "\n".join(self.log_messages)

        # Sort scorecards by AC1 (best first, None values at the end)
        self._log("Sorting scorecards by overall AC1...")

        def sort_key(scorecard_result):
            ac1 = scorecard_result.get('overall_ac1')
            # None values get -infinity so they sort to the end
            return (ac1 is not None, ac1 if ac1 is not None else -float('inf'))

        scorecard_results.sort(key=sort_key, reverse=True)

        # Add rank to each scorecard
        for rank, result in enumerate(scorecard_results, 1):
            result['rank'] = rank

        self._log(f"Completed analysis of {len(scorecard_results)} scorecards with feedback data")

        # Build final output
        final_output = {
            "mode": "all_scorecards",
            "total_scorecards_analyzed": len(scorecard_results),
            "total_scorecards_with_data": len(scorecard_results),
            "total_scorecards_filtered": scorecards_filtered,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "scorecards": scorecard_results,
            "message": f"Analyzed {len(scorecard_results)} scorecard(s) with feedback data, sorted by overall AC1 (best to worst). Filtered out {scorecards_filtered} scorecard(s) with no data.",
            # Add block metadata
            "block_title": f"{self.DEFAULT_NAME} - All Scorecards",
            "block_description": f"{self.DEFAULT_DESCRIPTION} across all scorecards in the account"
        }

        # Format as YAML with comments
        try:
            contextual_comment = """# All Scorecards Feedback Analysis Report
#
# This report analyzes every scorecard in the account that has feedback data,
# running full feedback analysis on each one and ranking them by overall AC1
# (agreement coefficient).
#
# Scorecards with no feedback data in the specified time period are automatically
# filtered out to keep the report focused and manageable.
#
# Scorecards are sorted from best to worst performing (by AC1).
#
# Each scorecard entry contains the complete per-score analysis, just like a
# single-scorecard feedback analysis report.

"""
            yaml_output = yaml.dump(final_output, indent=2, allow_unicode=True, sort_keys=False)
            formatted_output = contextual_comment + yaml_output
        except Exception as e:
            self._log(f"Failed to create YAML formatted output: {e}", level="ERROR")
            formatted_output = yaml.dump(final_output, indent=2, allow_unicode=True, sort_keys=False)

        detailed_log = "\n".join(self.log_messages) if self.log_messages else "No logs generated."

        return formatted_output, detailed_log

    async def _fetch_feedback_items_for_score(self, plexus_scorecard_id: str, plexus_score_id: str, 
                                       start_date: Optional[datetime] = None, 
                                       end_date: Optional[datetime] = None) -> List[FeedbackItem]:
        """
        Fetches FeedbackItem records for a specific Plexus Score on a Plexus Scorecard.
        Now with direct GraphQL query for date-filtered items.
        
        Args:
            plexus_scorecard_id: The ID of the scorecard
            plexus_score_id: The ID of the score
            start_date: Optional start date for filtering (UTC aware)
            end_date: Optional end date for filtering (UTC aware)
        """
        self._log(f"Fetching feedback items for Plexus Scorecard ID: {plexus_scorecard_id}, Plexus Score ID: {plexus_score_id}")
        if start_date and end_date:
            self._log(f"With date filtering: {start_date.isoformat()} to {end_date.isoformat()}")
        
        # Get account_id
        account_id = self.params.get("account_id")
        if not account_id and hasattr(self.api_client, 'context') and self.api_client.context:
             account_id = self.api_client.context.account_id

        if not account_id:
            # Attempt to resolve account_id if not directly available in params or context
            try:
                self._log("Attempting to resolve account_id via PlexusDashboardClient...", level="DEBUG")
                if hasattr(self.api_client, '_resolve_account_id'):
                    account_id = await asyncio.to_thread(self.api_client._resolve_account_id) 
                elif hasattr(self.api_client, 'account_id'):
                    account_id = self.api_client.account_id

                if account_id:
                    self._log(f"Resolved account_id: {account_id}")
                else:
                    self._log("WARNING: account_id could not be resolved. FeedbackItem fetching might be incomplete or fail.", level="WARNING")
            except Exception as e:
                self._log(f"Error resolving account_id: {e}. Proceeding with account_id as None.", level="WARNING")
                account_id = None
        else:
            self._log(f"Using account_id: {account_id}", level="DEBUG")

        if not account_id:
            self._log("No account_id available. Cannot fetch feedback items.", level="ERROR")
            return []

        # Use the utility function
        items = await feedback_utils.fetch_feedback_items_for_score(
            self.api_client,
            account_id,
            plexus_scorecard_id,
            plexus_score_id,
            start_date,
            end_date
        )
        
        self._log(f"Total items fetched for score {plexus_score_id}: {len(items)}")
        return items
    
    def _analyze_feedback_data_gwet(self, feedback_items: List[FeedbackItem], score_id_info: str) -> Dict[str, Any]:
        """
        Analyzes a list of feedback items using Gwet's AC1.
        This function is generalized to work on any list of FeedbackItems.
        
        Args:
            feedback_items: List of FeedbackItem objects to analyze.
            score_id_info: Identifier string for the score (e.g., Plexus Score ID or "Overall") for logging.
            
        Returns:
            Dictionary with analysis results: {ac1, item_count, mismatches, accuracy, classes_count, label_distribution}
        """
        self._log(f"Analyzing {len(feedback_items)} feedback items for: {score_id_info}")
        
        if not feedback_items:
            self._log(f"No feedback items to analyze for {score_id_info}.", level="WARNING")
            return {"ac1": None, "item_count": 0, "mismatches": 0, "agreements": 0, "accuracy": None, "classes_count": 2, 
                    "label_distribution": {}, "confusion_matrix": None, "class_distribution": [], 
                    "predicted_class_distribution": [], "precision": None, "recall": None, "warning": "No data.", "warnings": "No data.", "notes": None, "discussion": None}
            
        # Don't log intermediate data processing details unless debugging
        valid_pairs_count = 0
        paired_initial = []
        paired_final = []

        # For Gwet's AC1, we need a list of ratings from rater1 and rater2 for the *same set of items*.
        # Here, 'initialAnswerValue' is rater1, 'finalAnswerValue' is rater2 for the same FeedbackItem.
        for item in feedback_items:
            if item.initialAnswerValue is not None and item.finalAnswerValue is not None:
                paired_initial.append(item.initialAnswerValue)
                paired_final.append(item.finalAnswerValue)
                valid_pairs_count +=1
        
        self._log(f"Found {valid_pairs_count} valid initial/final pairs for analysis for {score_id_info}.")

        if valid_pairs_count == 0:
            self._log(f"No valid (non-None initial and final) pairs to analyze for {score_id_info}.", level="WARNING")
            return {"ac1": None, "item_count": 0, "mismatches": 0, "agreements": 0, "accuracy": None, "classes_count": 2, 
                    "label_distribution": {}, "confusion_matrix": None, "class_distribution": [], 
                    "predicted_class_distribution": [], "precision": None, "recall": None, "warning": "No data.", "warnings": "No data.", "notes": None, "discussion": None}

        # Calculate label distribution
        label_distribution = dict(Counter(paired_final))
        self._log(f"Final value distribution for {score_id_info}: {label_distribution}")
        
        # Calculate initial value distribution
        initial_label_distribution = dict(Counter(paired_initial))
        self._log(f"Initial value distribution for {score_id_info}: {initial_label_distribution}")

        # Calculate Gwet's AC1
        try:
            # Get the number of valid classes from the score configuration
            num_classes = 2  # Default to binary classification
            if score_id_info != "Overall":
                try:
                    # Get the score object and its valid classes count
                    score = Score.get_by_id(score_id_info, client=self.api_client)
                    if score:
                        # Ensure the client is set on the score instance
                        score.client = self.api_client
                        num_classes = score.get_valid_classes_count()
                        self._log(f"Found {num_classes} valid classes in score configuration")
                except Exception as e:
                    self._log(f"Error getting valid classes count, defaulting to 2: {e}", level="WARNING")
            
            # Create GwetAC1 instance - it will determine classes from the input data
            gwet_ac1_calculator = GwetAC1()
            
            # Prepare reference and predictions lists
            # Final answer is the reference (ground truth), Initial answer is the prediction
            reference_list = [str(f) for f in paired_final]
            predictions_list = [str(i) for i in paired_initial]
            
            # Create Metric.Input object
            metric_input = Metric.Input(reference=reference_list, predictions=predictions_list)
            
            # Calculate Gwet's AC1
            calculation_result = gwet_ac1_calculator.calculate(metric_input)
            ac1_value = calculation_result.value # Get value from the result object

            self._log(f"Gwet's AC1 for {score_id_info}: {ac1_value}")
            
            # Calculate accuracy
            mismatches = sum(1 for i, f in zip(paired_initial, paired_final) if i != f)
            agreements = valid_pairs_count - mismatches
            accuracy_percentage = (agreements / valid_pairs_count) * 100 if valid_pairs_count > 0 else None
            
            accuracy_str = f"{accuracy_percentage:.2f}%" if accuracy_percentage is not None else "N/A"
            self._log(f"Analysis results for {score_id_info}: Gwet's AC1={ac1_value}, Items={valid_pairs_count}, Agreements={agreements}, Mismatches={mismatches}, Accuracy={accuracy_str}, Classes={num_classes}")
            
            # Generate confusion matrix
            # Final answer is the reference (ground truth), Initial answer is the prediction
            confusion_matrix = self._build_confusion_matrix(paired_final, paired_initial)
            
            # Generate class distribution for visualization
            class_distribution = self._format_class_distribution(label_distribution)
            
            # Generate predicted class distribution for visualization
            predicted_class_distribution = self._format_class_distribution(initial_label_distribution)
            
            # Calculate precision and recall metrics if there are multiple classes
            # Final answer is the reference (ground truth), Initial answer is the prediction
            precision_recall = self._calculate_precision_recall(paired_final, paired_initial, label_distribution.keys())
            
            # Generate warnings based on heuristics
            warnings = self._generate_warnings(ac1_value, label_distribution)
            
            return {
                "ac1": ac1_value,
                "item_count": valid_pairs_count,
                "mismatches": mismatches,
                "agreements": agreements,
                "accuracy": accuracy_percentage,
                "classes_count": num_classes,
                "label_distribution": label_distribution,
                "confusion_matrix": confusion_matrix,
                "class_distribution": class_distribution,
                "predicted_class_distribution": predicted_class_distribution,
                "precision": precision_recall.get("precision"),
                "recall": precision_recall.get("recall"),
                "warning": warnings,  # Individual score warning for frontend display
                "warnings": warnings,  # Keep for backwards compatibility
                "notes": None,
                "discussion": None
            }
            
        except Exception as e:
            self._log(f"Error calculating Gwet's AC1 for {score_id_info}: {e}", level="ERROR")
            # Don't log full traceback, just the error message
            raise
    
    def _format_class_distribution(self, distribution: Dict[Any, int]) -> List[Dict[str, Any]]:
        """
        Format class distribution for visualization.
        
        Args:
            distribution: Dictionary mapping class labels to counts
            
        Returns:
            List of dictionaries in the format expected by the UI
        """
        if not distribution:
            return []
            
        # Calculate total for percentages
        total = sum(distribution.values())
        
        # Format data to match ClassDistribution interface in UI
        result = [
            {
                "label": str(label),  # Ensure label is a string
                "count": count        # Keep count as an integer
            }
            for label, count in distribution.items()
        ]
        
        # Sort by count descending
        result.sort(key=lambda x: x["count"], reverse=True)
        
        self._log(f"Formatted class distribution: {result}")
        return result
    
    def _build_confusion_matrix(self, reference_values: List, predicted_values: List) -> Dict[str, Any]:
        """
        Build a confusion matrix from reference and predicted values.
        
        Args:
            reference_values: List of reference (ground truth) values
            predicted_values: List of predicted values
            
        Returns:
            Dictionary representation of confusion matrix in the format expected by the UI
        """
        # Get unique classes from both lists and ensure they are strings
        all_classes = sorted(list(set(str(v) for v in reference_values + predicted_values)))
        
        # Initialize matrix structure to match UI expectations
        matrix_result = {
            "labels": all_classes,
            "matrix": []
        }
        
        # Build matrix rows matching the ConfusionMatrixData format
        for true_class in all_classes:
            # Create a row object with actualClassLabel
            row = {
                "actualClassLabel": true_class,
                "predictedClassCounts": {}
            }
            
            # Add counts for each predicted class
            for pred_class in all_classes:
                # Count instances where reference is true_class and prediction is pred_class
                count = 0
                for ref_val, pred_val in zip(reference_values, predicted_values):
                    str_ref = str(ref_val)
                    str_pred = str(pred_val)
                    if str_ref == str(true_class) and str_pred == str(pred_class):
                        count += 1
                        # Log the values contributing to this cell
                        self._log(f"[Debug CM] Matched for cell true='{str(true_class)}', pred='{str(pred_class)}': item_ref='{str_ref}', item_pred='{str_pred}'", level="DEBUG")
                row["predictedClassCounts"][pred_class] = count
            
            # Add this row to the matrix
            matrix_result["matrix"].append(row)
        
        self._log(f"Built confusion matrix with {len(all_classes)} classes")
        self._log(f"Matrix structure: labels={matrix_result['labels']}, row count={len(matrix_result['matrix'])}")
        return matrix_result
    
    def _calculate_precision_recall(self, reference_values: List, predicted_values: List, classes: Any) -> Dict[str, float]:
        """
        Calculate precision and recall metrics.
        
        Args:
            reference_values: List of reference (ground truth) values
            predicted_values: List of predicted values
            classes: Iterable of class labels
            
        Returns:
            Dictionary with precision and recall values
        """
        # Default result if calculation fails
        result = {"precision": None, "recall": None}
        
        try:
            # Convert values to strings for comparison
            str_reference = [str(v) for v in reference_values]
            str_predicted = [str(v) for v in predicted_values]
            str_classes = [str(c) for c in classes]
            
            # If there are only two classes, calculate binary precision/recall
            if len(str_classes) == 2:
                # Assuming the first class is the positive class
                positive_class = str_classes[0]
                
                # Calculate TP, FP, FN
                true_positives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                    if ref == positive_class and pred == positive_class)
                false_positives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                     if ref != positive_class and pred == positive_class)
                false_negatives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                     if ref == positive_class and pred != positive_class)
                
                # Calculate precision and recall
                precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
                recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
                
                result = {"precision": precision * 100, "recall": recall * 100}  # Convert to percentage
            else:
                # For multiclass, use macro averaging (average of per-class metrics)
                precisions = []
                recalls = []
                
                for cls in str_classes:
                    # For each class, treat it as the positive class
                    true_positives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                        if ref == cls and pred == cls)
                    false_positives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                         if ref != cls and pred == cls)
                    false_negatives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                         if ref == cls and pred != cls)
                    
                    # Calculate class precision and recall
                    class_precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
                    class_recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
                    
                    precisions.append(class_precision)
                    recalls.append(class_recall)
                
                # Macro averaging
                macro_precision = sum(precisions) / len(precisions) if precisions else 0
                macro_recall = sum(recalls) / len(recalls) if recalls else 0
                
                result = {"precision": macro_precision * 100, "recall": macro_recall * 100}  # Convert to percentage
        
        except Exception as e:
            self._log(f"Error calculating precision/recall: {e}", level="WARNING")
        
        return result
    
    def _generate_warnings(self, ac1: Optional[float], label_distribution: Dict[Any, int]) -> Optional[str]:
        """
        Generate concise warnings based on simple heuristics for problematic analysis conditions.
        
        Args:
            ac1: Gwet's AC1 value (agreement coefficient)
            label_distribution: Dictionary mapping class labels to their counts in the data
            
        Returns:
            Warning text if warnings are needed, None otherwise
        """
        warnings = []
        
        # Check for negative agreement (systematic disagreement)
        if ac1 is not None and ac1 < 0:
            warnings.append("Systematic disagreement.")
        
        # Check for zero agreement (random chance)
        elif ac1 is not None and ac1 == 0:
            warnings.append("Random chance.")
        
        # Check for class imbalance (only one class present)
        if label_distribution and len(label_distribution) == 1:
            single_class = list(label_distribution.keys())[0]
            warnings.append(f"Single class ({single_class}).")
        
        # Check for imbalanced class distribution (multiple classes, but not balanced)
        # Using same 20% tolerance as ClassDistributionVisualizer component
        elif label_distribution and len(label_distribution) > 1:
            if not self._is_distribution_balanced(label_distribution):
                warnings.append("Imbalanced classes.")
        
        # Return combined warnings or None if no warnings
        if warnings:
            return " ".join(warnings)
        else:
            return None
    
    def _is_distribution_balanced(self, label_distribution: Dict[Any, int]) -> bool:
        """
        Check if class distribution is balanced using same logic as ClassDistributionVisualizer.
        Uses 20% tolerance from perfect balance.
        
        Args:
            label_distribution: Dictionary mapping class labels to their counts
            
        Returns:
            True if distribution is balanced, False if imbalanced
        """
        if not label_distribution or len(label_distribution) <= 1:
            return True  # Single class or no classes are considered "balanced" (no imbalance warning needed)
        
        total = sum(label_distribution.values())
        expected_count = total / len(label_distribution)
        tolerance = 0.2  # 20% tolerance, same as Evaluation.py
        
        # Check if all classes are within 20% tolerance of expected count
        return all(
            abs(count - expected_count) <= expected_count * tolerance 
            for count in label_distribution.values()
        )
    
    def _generate_summary_warning(self, score_results: List[Dict[str, Any]]) -> Optional[str]:
        """
        Generate a concise summary warning based on individual score warnings.
        
        Args:
            score_results: List of score analysis results, each potentially containing a 'warning' field
            
        Returns:
            Summary warning text if warnings are present, None otherwise
        """
        if not score_results:
            return None
        
        # Count warning types
        warning_counts = {
            'systematic_disagreement': 0,
            'random_chance': 0,
            'single_class': 0,
            'imbalanced_classes': 0,
            'no_data': 0
        }
        
        total_scores = len(score_results)
        scores_with_warnings = 0
        
        for result in score_results:
            warning = result.get('warning')
            if warning:
                scores_with_warnings += 1
                # Check for specific warning types (using our Hemingway-style phrases)
                if 'Systematic disagreement' in warning:
                    warning_counts['systematic_disagreement'] += 1
                elif 'Random chance' in warning:
                    warning_counts['random_chance'] += 1
                elif 'Single class' in warning:
                    warning_counts['single_class'] += 1
                elif 'Imbalanced classes' in warning:
                    warning_counts['imbalanced_classes'] += 1
                elif 'No data' in warning:
                    warning_counts['no_data'] += 1
        
        if scores_with_warnings == 0:
            return None
            
        # Generate concise summary following Hemingway style
        
        # If all scores have warnings, just say "All scores" 
        if scores_with_warnings == total_scores:
            score_phrase = "All scores"
        elif scores_with_warnings == 1:
            score_phrase = "1 score"
        else:
            score_phrase = f"{scores_with_warnings} scores with"
        
        # List the warning types found
        warning_types = []
        if warning_counts['systematic_disagreement'] > 0:
            warning_types.append("disagreement")
        if warning_counts['random_chance'] > 0:
            warning_types.append("random chance")
        if warning_counts['single_class'] > 0:
            warning_types.append("single class")
        if warning_counts['imbalanced_classes'] > 0:
            warning_types.append("imbalanced")
        if warning_counts['no_data'] > 0:
            warning_types.append("no data")
        
        if len(warning_types) == 1:
            if scores_with_warnings == total_scores or scores_with_warnings == 1:
                return f"{score_phrase}: {warning_types[0]}."
            else:
                return f"{score_phrase} {warning_types[0]}."
        elif len(warning_types) == 2:
            if scores_with_warnings == total_scores or scores_with_warnings == 1:
                return f"{score_phrase}: {warning_types[0]} and {warning_types[1]}."
            else:
                return f"{score_phrase} {warning_types[0]} and {warning_types[1]}."
        else:
            # 3 or more warning types - use "multiple issues" and put each on separate line
            if scores_with_warnings == total_scores or scores_with_warnings == 1:
                return f"{score_phrase} with multiple issues:\n" + "\n".join(f"• {wtype}" for wtype in warning_types) + "."
            else:
                return f"{score_phrase} multiple issues:\n" + "\n".join(f"• {wtype}" for wtype in warning_types) + "."

    def _log(self, message: str, level="INFO"):
        """Helper method to log messages and store them for the report block's log output.
        
        Args:
            message: The message to log
            level: Log level (INFO, DEBUG, WARNING, ERROR)
        """
        # Only store non-DEBUG messages in the log output
        if level == "DEBUG":
            # Just log to system logger but don't add to block log
            logger.debug(f"[ReportBlock {self.config.get('name', 'Unnamed')} (FeedbackAnalysis)] {message}")
        else:
            # For all other levels (INFO, WARNING, ERROR), log to both system and block log
            log_method = getattr(logger, level.lower(), logger.info)
            log_method(f"[ReportBlock {self.config.get('name', 'Unnamed')} (FeedbackAnalysis)] {message}")
            
            # Add to block log with level prefix for important messages
            if level in ("WARNING", "ERROR"):
                self.log_messages.append(f"{datetime.now().isoformat()} - {level}: {message}")
            else:
                self.log_messages.append(f"{datetime.now().isoformat()} - {message}")

    async def _create_indexed_feedback_items(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """
        Creates an indexed structure of feedback items organized by initial (predicted) and final (actual) answers.
        This allows for quick lookup of feedback items for any cell in the confusion matrix.
        
        Args:
            feedback_items: List of FeedbackItem objects to index
            
        Returns:
            Dictionary with structure:
            {
                "answer1": {
                    "answer1": [feedback_items_with_answer1_answer1],
                    "answer2": [feedback_items_with_answer1_answer2],
                    ...
                },
                "answer2": {
                    "answer1": [feedback_items_with_answer2_answer1],
                    "answer2": [feedback_items_with_answer2_answer2],
                    ...
                },
                ...
            }
        """
        self._log(f"Creating indexed feedback items structure for {len(feedback_items)} items")
        
        # Initialize the structure - simplified to use initial values directly as top-level keys
        indexed_structure = {}
        
        # Process only items with both values present
        valid_items = [item for item in feedback_items if item.initialAnswerValue is not None and item.finalAnswerValue is not None]
        self._log(f"Found {len(valid_items)} valid items with both initial and final answer values")
        
        # Process each valid item
        for item in valid_items:
            # Ensure the item relationship is loaded
            await self._ensure_item_loaded(item)
            
            # Convert values to strings to ensure consistent keys
            initial_value = str(item.initialAnswerValue)
            final_value = str(item.finalAnswerValue)
            
            # Ensure nested structure exists
            if initial_value not in indexed_structure:
                indexed_structure[initial_value] = {}
            
            if final_value not in indexed_structure[initial_value]:
                indexed_structure[initial_value][final_value] = []
            
            # Log the specific keys being used for this item
            self._log(f"[Debug Indexing] Item ID {item.id}: initial_key='{initial_value}', final_key='{final_value}'", level="DEBUG")

            # Create a simplified representation of the feedback item
            item_dict = {
                "id": item.id,
                "initialAnswerValue": item.initialAnswerValue,
                "finalAnswerValue": item.finalAnswerValue,
                "initialCommentValue": item.initialCommentValue,
                "finalCommentValue": item.finalCommentValue,
                "editCommentValue": item.editCommentValue,
                "editedAt": item.editedAt,
                "editorName": item.editorName,
                "isAgreement": item.isAgreement,
                "scorecardId": item.scorecardId,
                "scoreId": item.scoreId,
                "itemId": item.itemId,
                "cacheKey": item.cacheKey,
                "createdAt": item.createdAt,
                "updatedAt": item.updatedAt
            }
            
            # Add item identifiers if available
            if hasattr(item, 'item') and item.item and hasattr(item.item, 'identifiers'):
                item_dict["item"] = {
                    "id": item.item.id if hasattr(item.item, 'id') else None,
                    "identifiers": item.item.identifiers,
                    "externalId": item.item.externalId if hasattr(item.item, 'externalId') else None,
                }
                # Log to confirm we're including identifiers
                self._log(f"Including item identifiers for feedback item {item.id}: {item.item.identifiers}", level="DEBUG")
            else:
                # Add a message if identifiers are not available
                self._log(f"Item identifiers not available for feedback item {item.id}", level="DEBUG")
                item_dict["item"] = {
                    "id": item.itemId,
                    "identifiers": None,
                    "message": "Item details not available"
                }
            
            # Add the item to the appropriate list
            indexed_structure[initial_value][final_value].append(item_dict)
        
        # Sort each list of items by edit date (newest first)
        for initial_value, final_values_dict in indexed_structure.items():
            for final_value, items_list in final_values_dict.items():
                # Sort by editedAt first (if available), then by updatedAt, then by createdAt
                # Using reverse=True to get newest first
                def sort_key(item):
                    # Try editedAt first, then updatedAt, then createdAt
                    # For reverse chronological order, we want the newest items first
                    date_val = item.get('editedAt') or item.get('updatedAt') or item.get('createdAt')
                    if date_val is None:
                        # Items without dates should sort to the end (return a very old date)
                        return datetime.min.replace(tzinfo=timezone.utc)
                    
                    # Convert string dates to datetime objects for proper comparison
                    if isinstance(date_val, str):
                        try:
                            # Parse ISO format date strings
                            return datetime.fromisoformat(date_val.replace('Z', '+00:00'))
                        except ValueError:
                            # Fallback to string comparison if parsing fails
                            return date_val
                    
                    # If it's already a datetime object, return as-is
                    if hasattr(date_val, 'isoformat'):
                        return date_val
                    
                    # Fallback to string conversion
                    return str(date_val)
                
                # Log before sorting
                self._log(f"Before sorting {len(items_list)} items for initial={initial_value}, final={final_value}")
                for i, item in enumerate(items_list[:3]):  # Show first 3 items before sorting
                    date_val = item.get('editedAt') or item.get('updatedAt') or item.get('createdAt')
                    self._log(f"BEFORE - Item {i+1}: ID={item.get('id')}, sort_date={date_val}")
                
                items_list.sort(key=sort_key, reverse=True)
                
                # Log after sorting
                self._log(f"After sorting {len(items_list)} items for initial={initial_value}, final={final_value}")
                for i, item in enumerate(items_list[:3]):  # Show first 3 items after sorting
                    date_val = item.get('editedAt') or item.get('updatedAt') or item.get('createdAt')
                    self._log(f"AFTER - Item {i+1}: ID={item.get('id')}, sort_date={date_val}")
        
        # Add summary count of items with identifiers
        items_with_identifiers = 0
        total_indexed = 0
        for initial_value, final_values_dict in indexed_structure.items():
            for final_value, items_list in final_values_dict.items():
                count = len(items_list)
                total_indexed += count
                self._log(f"Indexed {count} items with initial={initial_value}, final={final_value}")
                
                for item in items_list:
                    if "item" in item and item["item"] and "identifiers" in item["item"] and item["item"]["identifiers"] is not None:
                        items_with_identifiers += 1
        
        self._log(f"Total indexed items: {total_indexed}")
        self._log(f"Indexed items with identifiers: {items_with_identifiers} out of {total_indexed}")
        return indexed_structure

    async def _ensure_item_loaded(self, feedback_item: FeedbackItem):
        """
        Ensures the Item relationship is loaded for a FeedbackItem.
        This is necessary because the relationship might not be automatically loaded, 
        especially when the feedback item is created without the nested item data.
        
        Args:
            feedback_item: The FeedbackItem to ensure item is loaded for
        
        Returns:
            True if the item was loaded successfully, False otherwise
        """
        if hasattr(feedback_item, 'item') and feedback_item.item is not None:
            # Item is already loaded
            return True
            
        if not feedback_item.itemId or not self.api_client:
            # No itemId or client to load with
            return False
            
        try:
            # Import here to avoid circular imports
            from plexus.dashboard.api.models.item import Item
            
            # Construct a GraphQL query to fetch the item
            query = """
            query GetItem($id: ID!) {
                getItem(id: $id) {
                    id
                    identifiers
                    externalId
                }
            }
            """
            
            variables = {"id": feedback_item.itemId}
            
            # Execute the query
            result = await asyncio.to_thread(self.api_client.execute, query, variables)
            
            if result and 'getItem' in result and result['getItem']:
                item_data = result['getItem']
                # Create an Item instance and attach it
                feedback_item.item = Item.from_dict(item_data, client=self.api_client)
                self._log(f"Successfully loaded Item for FeedbackItem {feedback_item.id}: identifiers={feedback_item.item.identifiers}")
                return True
            else:
                self._log(f"Failed to load Item {feedback_item.itemId} for FeedbackItem {feedback_item.id}", level="WARNING")
                return False
                
        except Exception as e:
            self._log(f"Error loading Item for FeedbackItem {feedback_item.id}: {e}", level="ERROR")
            return False

# Example of how this block might be configured in a ReportConfiguration:
"""
```block name="Feedback Agreement Analysis"
class: FeedbackAnalysis
scorecard: "1438" # Call Criteria Scorecard ID
days: 30 # Analyze feedback from the last 30 days
# score_id: "44246" # Optional: Call Criteria Question ID to analyze a specific score
```
""" 