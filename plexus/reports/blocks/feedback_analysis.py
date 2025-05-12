from typing import Any, Dict, Optional, Tuple, List
import logging
import asyncio
from datetime import datetime, timedelta, timezone

from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard

from .base import BaseReportBlock

logger = logging.getLogger(__name__)


class FeedbackAnalysis(BaseReportBlock):
    """
    Analyzes feedback data using Gwet's AC1 agreement coefficient.
    
    This block retrieves FeedbackItem records and compares initial and final answer values
    to calculate agreement scores using Gwet's AC1.

    If a specific 'score_id' (Call Criteria Question ID) is provided in the config,
    it analyzes only that score. Otherwise, it analyzes all scores associated with
    the provided 'scorecard' (Call Criteria Scorecard ID) that have a mapping
    to a Plexus Score with an externalId.
    
    Config:
        scorecard (str): Call Criteria Scorecard ID (e.g., "1438"). This is REQUIRED.
        days (int, optional): Number of days in the past to analyze (default: 14).
                              FeedbackItems updated within this period will be considered.
        start_date (str, optional): Start date for analysis in YYYY-MM-DD format.
                                   If provided, overrides 'days'.
        end_date (str, optional): End date for analysis in YYYY-MM-DD format.
                                 Defaults to today if not specified.
        score_id (str, optional): Specific Call Criteria Question ID to analyze.
                                 If specified, only this score will be analyzed.
    """

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetches feedback data and performs agreement analysis."""
        self.log_messages = []
        final_output_data = None

        try:
            self._log("Starting FeedbackAnalysis block generation.")
            self._log(f"Raw config: {self.config}")
            self._log(f"Raw params: {self.params}")

            # --- 1. Extract and Validate Configuration ---
            cc_scorecard_id_param = self.config.get("scorecard")
            if not cc_scorecard_id_param:
                self._log("ERROR: 'scorecard' (Call Criteria Scorecard ID) missing in block configuration.")
                raise ValueError("'scorecard' is required in the block configuration.")
            self._log(f"Call Criteria Scorecard ID from config: {cc_scorecard_id_param}")

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
            self._log(f"Resolving Plexus Scorecard for CC Scorecard ID: {cc_scorecard_id_param}...")
            try:
                plexus_scorecard_obj = await asyncio.to_thread(
                    Scorecard.get_by_external_id,
                    external_id=str(cc_scorecard_id_param),
                    client=self.api_client
                )
                if not plexus_scorecard_obj:
                    msg = f"Plexus Scorecard not found for Call Criteria Scorecard ID: {cc_scorecard_id_param}"
                    self._log(f"ERROR: {msg}")
                    raise ValueError(msg)
                self._log(f"Found Plexus Scorecard: '{plexus_scorecard_obj.name}' (ID: {plexus_scorecard_obj.id})")
            except Exception as e:
                self._log(f"ERROR resolving Plexus Scorecard: {e}")
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
                        self._log(f"WARNING: Plexus Score not found for CC Question ID: {cc_question_id_param} on Scorecard '{plexus_scorecard_obj.name}'. This score will be skipped.")
                except Exception as e:
                    self._log(f"ERROR looking up specific Plexus Score (CC Question ID: {cc_question_id_param}): {e}. This score will be skipped.")
            else:
                self._log(f"Fetching all Plexus Scores for Scorecard '{plexus_scorecard_obj.name}' (ID: {plexus_scorecard_obj.id}) to find mappable scores.")
                scores_query = """
                query GetScorecardScores($scorecardId: ID!) {
                    getScorecard(id: $scorecardId) {
                        id name
                        sections { items { id scores { items { id name externalId } } } }
                    }
                }
                """
                try:
                    result = await asyncio.to_thread(self.api_client.execute, scores_query, {'scorecardId': plexus_scorecard_obj.id})
                    scorecard_data = result.get('getScorecard')
                    if scorecard_data and scorecard_data.get('sections') and scorecard_data['sections'].get('items'):
                        for section in scorecard_data['sections']['items']:
                            if section.get('scores') and section['scores'].get('items'):
                                for score_item in section['scores']['items']:
                                    if score_item.get('externalId'):
                                        scores_to_process.append({
                                            'plexus_score_id': score_item['id'],
                                            'plexus_score_name': score_item['name'],
                                            'cc_question_id': score_item['externalId']
                                        })
                                    else:
                                        self._log(f"Plexus Score '{score_item.get('name')}' (ID: {score_item.get('id')}) is missing an externalId (CC Question ID). Skipping.")
                    self._log(f"Identified {len(scores_to_process)} Plexus Scores with externalIds to process.")
                except Exception as e:
                    self._log(f"ERROR fetching scores for Plexus Scorecard '{plexus_scorecard_obj.name}': {e}")
                    # Continue if some scores were found, otherwise this will be caught by the next check
            
            if not scores_to_process:
                msg = "No Plexus Scores identified for analysis (either none found or none had a mappable CC Question ID)."
                self._log(f"ERROR: {msg}")
                # Return a structure indicating no data, but not an error state for the report block itself.
                return {
                    "overall_ac1": None, "total_items": 0, "total_mismatches": 0, "accuracy": None,
                    "scores": [],
                    "total_feedback_items_retrieved": 0,
                    "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                    "message": msg
                }, "\n".join(self.log_messages)

            # --- 4. Fetch and Analyze Feedback for Each Score ---
            all_feedback_items_retrieved_count = 0
            all_date_filtered_feedback_items = [] # For overall calculation
            per_score_analysis_results = []

            for score_info in scores_to_process:
                self._log(f"--- Processing Score: '{score_info['plexus_score_name']}' (ID: {score_info['plexus_score_id']}, CC ID: {score_info['cc_question_id']}) ---")
                
                items_for_this_score = await self._fetch_feedback_items_for_score(
                    plexus_scorecard_id=plexus_scorecard_obj.id,
                    plexus_score_id=score_info['plexus_score_id']
                )
                all_feedback_items_retrieved_count += len(items_for_this_score)
                self._log(f"Retrieved {len(items_for_this_score)} FeedbackItems for this score (before date filtering).")

                # Date filter items for this score
                date_filtered_items_for_score = [
                    item for item in items_for_this_score
                    if item.updatedAt and start_date <= item.updatedAt <= end_date
                ]
                self._log(f"{len(date_filtered_items_for_score)} items for this score within date range: {start_date.date()} - {end_date.date()}")
                
                all_date_filtered_feedback_items.extend(date_filtered_items_for_score)

                if not date_filtered_items_for_score:
                    self._log("No feedback items for this score within the date range.")
                    analysis_for_this_score = {
                        "score_id": score_info['plexus_score_id'],
                        "score_name": score_info['plexus_score_name'],
                        "cc_question_id": score_info['cc_question_id'],
                        "ac1": None, "item_count": 0, "mismatches": 0, "accuracy": None,
                        "message": "No feedback items found in the specified date range."
                    }
                else:
                    analysis_for_this_score = self._analyze_feedback_data_gwet(
                        feedback_items=date_filtered_items_for_score,
                        score_id_info=score_info['plexus_score_id'] # For logging within analysis
                    )
                    analysis_for_this_score["score_id"] = score_info['plexus_score_id']
                    analysis_for_this_score["score_name"] = score_info['plexus_score_name']
                    analysis_for_this_score["cc_question_id"] = score_info['cc_question_id']
                
                per_score_analysis_results.append(analysis_for_this_score)
                self._log(f"Analysis for score '{score_info['plexus_score_name']}': {analysis_for_this_score}")

            # --- 5. Calculate Overall Metrics ---
            self._log(f"Calculating overall metrics from {len(all_date_filtered_feedback_items)} date-filtered feedback items across all processed scores.")
            if not all_date_filtered_feedback_items:
                overall_analysis = {"ac1": None, "item_count": 0, "mismatches": 0, "accuracy": None}
                self._log("No date-filtered items available for overall analysis.")
            else:
                # Use a generic score_id_info for the overall log
                overall_analysis = self._analyze_feedback_data_gwet(all_date_filtered_feedback_items, "Overall") 
            
            self._log(f"Overall analysis: {overall_analysis}")

            # --- 6. Structure Final Output ---
            final_output_data = {
                "overall_ac1": overall_analysis.get("ac1"), # Renamed from overall_ac1
                "total_items": overall_analysis.get("item_count"), # Renamed from item_count
                "total_mismatches": overall_analysis.get("mismatches"), # Renamed from mismatches
                "accuracy": overall_analysis.get("accuracy"), # Renamed from accuracy
                "scores": per_score_analysis_results,
                "total_feedback_items_retrieved": all_feedback_items_retrieved_count,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "message": f"Processed {len(scores_to_process)} score(s)." if scores_to_process else "No scores were processed."
            }
            self._log(f"Final output data: {final_output_data}")

        except ValueError as ve:
            self._log(f"Configuration or Value Error: {ve}")
            # final_output_data remains None, or could be set to an error structure
            final_output_data = {"error": str(ve), "scores": []}
        except Exception as e:
            self._log(f"ERROR during FeedbackAnalysis generation: {str(e)}")
            import traceback
            self._log(traceback.format_exc())
            final_output_data = {"error": str(e), "scores": []}

        log_string = "\n".join(self.log_messages) if self.log_messages else None
        return final_output_data, log_string
    
    async def _fetch_feedback_items_for_score(self, plexus_scorecard_id: str, plexus_score_id: str) -> List[FeedbackItem]:
        """Fetches all FeedbackItem records for a specific Plexus Score on a Plexus Scorecard."""
        self._log(f"Fetching feedback items for Plexus Scorecard ID: {plexus_scorecard_id}, Plexus Score ID: {plexus_score_id}")
        
        all_items_for_score = []
        next_token = None
        account_id = self.params.get("account_id") # Assuming account_id is in self.params from Task context
        if not account_id and hasattr(self.api_client, 'context') and self.api_client.context:
             account_id = self.api_client.context.account_id # Try to get from client context

        if not account_id:
            # Attempt to resolve account_id if not directly available in params or context
            try:
                self._log("Attempting to resolve account_id via PlexusDashboardClient...")
                # Ensure _resolve_account_id can be called or account_id is pre-resolved.
                # This might require self.api_client to have context.account_key set.
                if hasattr(self.api_client, '_resolve_account_id'):
                    account_id = await asyncio.to_thread(self.api_client._resolve_account_id) 
                elif hasattr(self.api_client, 'account_id'): # if it was resolved and stored
                    account_id = self.api_client.account_id

                if account_id:
                    self._log(f"Resolved account_id: {account_id}")
                else: # Final fallback if it cannot be resolved
                    self._log("WARNING: account_id could not be resolved. FeedbackItem fetching might be incomplete or fail.")
                    # Depending on API, not providing account_id might fetch for all accounts (bad) or fail.
                    # For safety, we might choose to return empty list here if account_id is critical.
                    # For now, proceed with None, and let FeedbackItem.list handle it.
            except Exception as e:
                self._log(f"Error resolving account_id: {e}. Proceeding with account_id as None.")
                account_id = None # Ensure it's None if resolution fails
        else:
            self._log(f"Using account_id: {account_id}")


        while True:
            try:
                # Ensure all required args for FeedbackItem.list are provided.
                # It's crucial that `FeedbackItem.list` can handle `score_id` being None if that's intended.
                # However, in this method, `plexus_score_id` should always be provided.
                self._log(f"Calling FeedbackItem.list with account_id='{account_id}', scorecard_id='{plexus_scorecard_id}', score_id='{plexus_score_id}', limit=100, next_token='{next_token}'")
                
                # Making FeedbackItem.list an async-compatible call
                items, next_token = await asyncio.to_thread(
                    FeedbackItem.list, # Assuming FeedbackItem.list is a static/class method
                    client=self.api_client,
                    account_id=account_id, # Pass resolved or param account_id
                    scorecard_id=plexus_scorecard_id,
                    score_id=plexus_score_id, # Specific score for this fetch
                    limit=100,
                    next_token=next_token
                )
                all_items_for_score.extend(items)
                self._log(f"Fetched {len(items)} items for this score (total for score: {len(all_items_for_score)})")
                
                if not next_token:
                    break
            except Exception as e:
                self._log(f"Error during paginated fetch for score {plexus_score_id}: {str(e)}")
                import traceback
                self._log(traceback.format_exc())
                break # Stop fetching for this score on error
                
        return all_items_for_score
    
    def _analyze_feedback_data_gwet(self, feedback_items: List[FeedbackItem], score_id_info: str) -> Dict[str, Any]:
        """
        Analyzes a list of feedback items using Gwet's AC1.
        This function is generalized to work on any list of FeedbackItems.
        
        Args:
            feedback_items: List of FeedbackItem objects to analyze.
            score_id_info: Identifier string for the score (e.g., Plexus Score ID or "Overall") for logging.
            
        Returns:
            Dictionary with analysis results: {ac1, item_count, mismatches, accuracy}
        """
        self._log(f"Analyzing {len(feedback_items)} feedback items for: {score_id_info}")
        
        if not feedback_items:
            self._log(f"No feedback items to analyze for {score_id_info}.")
            return {"ac1": None, "item_count": 0, "mismatches": 0, "accuracy": None}
            
        initial_values = [item.initialAnswerValue for item in feedback_items if item.initialAnswerValue is not None]
        final_values = [item.finalAnswerValue for item in feedback_items if item.finalAnswerValue is not None]
        
        # Gwet's AC1 requires paired data. Ensure lists are of the same length by taking the minimum.
        # This assumes items are already somewhat paired or we're comparing corresponding entries.
        # A more robust pairing might be needed if items aren't implicitly paired.
        valid_pairs_count = 0
        paired_initial = []
        paired_final = []

        # Iterate based on the full list of feedback_items to ensure each item is considered once for pairing
        processed_indices = set() # To avoid double counting if items are not perfectly one-to-one by index
        
        # For Gwet's AC1, we need a list of ratings from rater1 and rater2 for the *same set of items*.
        # Here, 'initialAnswerValue' is rater1, 'finalAnswerValue' is rater2 for the same FeedbackItem.
        for item in feedback_items:
            if item.initialAnswerValue is not None and item.finalAnswerValue is not None:
                paired_initial.append(item.initialAnswerValue)
                paired_final.append(item.finalAnswerValue)
                valid_pairs_count +=1
        
        self._log(f"Found {valid_pairs_count} valid initial/final pairs for analysis for {score_id_info}.")

        if valid_pairs_count == 0:
            self._log(f"No valid (non-None initial and final) pairs to analyze for {score_id_info}.")
            return {"ac1": None, "item_count": 0, "mismatches": 0, "accuracy": None}

        # Calculate Gwet's AC1
        try:
            # Ensure GwetAC1 can handle the data format (e.g., list of strings)
            # Convert values to string just in case they are not, as GwetAC1 might expect consistent types.
            
            # Corrected GwetAC1 usage:
            gwet_ac1_calculator = GwetAC1() # Instantiate without arguments
            
            # Prepare reference and predictions lists
            reference_list = [str(i) for i in paired_initial]
            predictions_list = [str(f) for f in paired_final]
            
            # Create Metric.Input object
            metric_input = Metric.Input(reference=reference_list, predictions=predictions_list)
            
            # Calculate Gwet's AC1
            calculation_result = gwet_ac1_calculator.calculate(metric_input)
            ac1_value = calculation_result.value # Get value from the result object

            self._log(f"Gwet's AC1 for {score_id_info}: {ac1_value}")
        except Exception as e:
            self._log(f"Error calculating Gwet's AC1 for {score_id_info}: {e}")
            import traceback
            self._log(traceback.format_exc())
            ac1_value = None
            
        # Calculate mismatches and accuracy based on the paired data
        mismatches = sum(1 for i, f in zip(paired_initial, paired_final) if i != f)
        
        if valid_pairs_count > 0:
            accuracy_float = (valid_pairs_count - mismatches) / valid_pairs_count
            accuracy_percentage = accuracy_float * 100
        else:
            accuracy_percentage = None # MODIFIED: Set to None if no valid pairs
        
        self._log(f"Analysis for {score_id_info} - Items: {valid_pairs_count}, Mismatches: {mismatches}, Accuracy: {f'{accuracy_percentage:.2f}%' if accuracy_percentage is not None else 'N/A'}") # MODIFIED Log
        
        return {
            "ac1": ac1_value,
            "item_count": valid_pairs_count, # Number of items used in AC1 calculation
            "mismatches": mismatches,
            "accuracy": accuracy_percentage # Return as percentage or None
        }

    def _log(self, message: str):
        """Helper method to log messages and store them for the report block's log output."""
        logger.info(f"[ReportBlock {self.config.get('name', 'Unnamed')} (FeedbackAnalysis)] {message}")
        self.log_messages.append(f"{datetime.now().isoformat()} - {message}")

# Example of how this block might be configured in a ReportConfiguration:
"""
```block name="Feedback Agreement Analysis"
class: FeedbackAnalysis
scorecard: "1438" # Call Criteria Scorecard ID
days: 30 # Analyze feedback from the last 30 days
# score_id: "44246" # Optional: Call Criteria Question ID to analyze a specific score
```
""" 