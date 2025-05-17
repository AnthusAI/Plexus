from typing import Any, Dict, Optional, Tuple, List
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from collections import Counter

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
            # Only log config keys, not full values
            self._log(f"Config keys: {list(self.config.keys())}")

            # --- 1. Extract and Validate Configuration ---
            cc_scorecard_id_param = self.config.get("scorecard")
            if not cc_scorecard_id_param:
                self._log("ERROR: 'scorecard' (Call Criteria Scorecard ID) missing in block configuration.", level="ERROR")
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
                                        self._log(f"Plexus Score '{score_item.get('name')}' (ID: {score_item.get('id')}) is missing an externalId (CC Question ID). Skipping.", level="DEBUG")
                    self._log(f"Identified {len(scores_to_process)} Plexus Scores with externalIds to process.")
                except Exception as e:
                    self._log(f"ERROR fetching scores for Plexus Scorecard '{plexus_scorecard_obj.name}': {e}", level="ERROR")
                    # Continue if some scores were found, otherwise this will be caught by the next check
            
            if not scores_to_process:
                msg = "No Plexus Scores identified for analysis (either none found or none had a mappable CC Question ID)."
                self._log(f"ERROR: {msg}", level="ERROR")
                # Return a structure indicating no data, but not an error state for the report block itself.
                return {
                    "overall_ac1": None, "total_items": 0, "total_mismatches": 0, "accuracy": None,
                    "scores": [],
                    "total_feedback_items_retrieved": 0,
                    "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                    "message": msg,
                    "classes_count": 2  # Default to binary classification for overall
                }, "\n".join(self.log_messages)

            # --- 4. Fetch and Analyze Feedback for Each Score ---
            all_feedback_items_retrieved_count = 0
            all_date_filtered_feedback_items = [] # For overall calculation
            per_score_analysis_results = []

            for score_info in scores_to_process:
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
                        "ac1": None, "item_count": 0, "mismatches": 0, "accuracy": None,
                        "message": "No feedback items found in the specified date range.",
                        "classes_count": 2,  # Default to binary classification
                        "label_distribution": {},
                        "confusion_matrix": None,
                        "class_distribution": [],
                        "predicted_class_distribution": [],
                        "precision": None,
                        "recall": None,
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
                    except Exception as e:
                        self._log(f"Error analyzing score {score_info['plexus_score_name']}: {e}", level="ERROR")
                        raise  # Re-raise to be caught by outer try/except
                
                per_score_analysis_results.append(analysis_for_this_score)
                # Only log a summary instead of the full analysis details
                accuracy_str = f"{analysis_for_this_score.get('accuracy'):.2f}%" if analysis_for_this_score.get('accuracy') is not None else "N/A"
                self._log(f"Analysis summary for score '{score_info['plexus_score_name']}': AC1={analysis_for_this_score.get('ac1')}, Items={analysis_for_this_score.get('item_count')}, Mismatches={analysis_for_this_score.get('mismatches')}, Accuracy={accuracy_str}, Classes={analysis_for_this_score.get('classes_count')}")

            # --- 5. Calculate Overall Metrics ---
            self._log(f"Calculating overall metrics from {len(all_date_filtered_feedback_items)} date-filtered feedback items across all processed scores.")
            if not all_date_filtered_feedback_items:
                overall_analysis = {"ac1": None, "item_count": 0, "mismatches": 0, "accuracy": None, "classes_count": 2, 
                                    "label_distribution": {}, "confusion_matrix": None, "class_distribution": [], 
                                    "predicted_class_distribution": [], "precision": None, "recall": None, "discussion": None}
                self._log("No date-filtered items available for overall analysis.", level="WARNING")
            else:
                # Use a generic score_id_info for the overall log
                overall_analysis = self._analyze_feedback_data_gwet(all_date_filtered_feedback_items, "Overall") 
            
            # Log a summary of the overall analysis instead of full details
            accuracy_str = f"{overall_analysis.get('accuracy'):.2f}%" if overall_analysis.get('accuracy') is not None else "N/A"
            self._log(f"Overall analysis summary: AC1={overall_analysis.get('ac1')}, Items={overall_analysis.get('item_count')}, Mismatches={overall_analysis.get('mismatches')}, Accuracy={accuracy_str}, Classes={overall_analysis.get('classes_count', 2)}")

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
                "message": f"Processed {len(scores_to_process)} score(s)." if scores_to_process else "No scores were processed.",
                "classes_count": overall_analysis.get("classes_count", 2),
                "label_distribution": overall_analysis.get("label_distribution", {}),
                # Add the new data from our enhanced analysis
                "confusion_matrix": overall_analysis.get("confusion_matrix"),
                "class_distribution": overall_analysis.get("class_distribution", []),
                "predicted_class_distribution": overall_analysis.get("predicted_class_distribution", []),
                "precision": overall_analysis.get("precision"),
                "recall": overall_analysis.get("recall"),
                "discussion": overall_analysis.get("discussion")
            }
            # Don't log the full output data - it's redundant and can be large
            self._log(f"Finished generating analysis for {len(scores_to_process)} scores with {all_feedback_items_retrieved_count} total feedback items.")

            # Create a summary log for the ReportBlock.log field (keep it short)
            summary_log = f"Processed {len(scores_to_process)} score(s) across {all_feedback_items_retrieved_count} feedback items. See detailed logs in log.txt."
            
            # The full detailed log will be stored in the S3 file
            detailed_log = "\n".join(self.log_messages) if self.log_messages else "No logs generated."

        except ValueError as ve:
            self._log(f"Configuration or Value Error: {ve}")
            # final_output_data remains None, or could be set to an error structure
            final_output_data = {"error": str(ve), "scores": []}
            summary_log = f"Error: {str(ve)}"
            detailed_log = "\n".join(self.log_messages) if self.log_messages else f"Error: {str(ve)}"
        except Exception as e:
            self._log(f"ERROR during FeedbackAnalysis generation: {str(e)}", level="ERROR")
            # Log only first few lines of traceback, not the full trace
            import traceback
            self._log(traceback.format_exc())
            final_output_data = {"error": str(e), "scores": []}
            summary_log = f"Error: {str(e)}"
            detailed_log = "\n".join(self.log_messages) if self.log_messages else f"Error: {str(e)}"

        # Always return the detailed_log as the second return value to ensure logs are saved to S3
        # The service.py code will use this to upload to S3
        return final_output_data, detailed_log
    
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
        
        all_items_for_score = []
        account_id = self.params.get("account_id") # Assuming account_id is in self.params from Task context
        if not account_id and hasattr(self.api_client, 'context') and self.api_client.context:
             account_id = self.api_client.context.account_id # Try to get from client context

        if not account_id:
            # Attempt to resolve account_id if not directly available in params or context
            try:
                self._log("Attempting to resolve account_id via PlexusDashboardClient...", level="DEBUG")
                # Ensure _resolve_account_id can be called or account_id is pre-resolved.
                if hasattr(self.api_client, '_resolve_account_id'):
                    account_id = await asyncio.to_thread(self.api_client._resolve_account_id) 
                elif hasattr(self.api_client, 'account_id'): # if it was resolved and stored
                    account_id = self.api_client.account_id

                if account_id:
                    self._log(f"Resolved account_id: {account_id}")
                else:
                    self._log("WARNING: account_id could not be resolved. FeedbackItem fetching might be incomplete or fail.", level="WARNING")
            except Exception as e:
                self._log(f"Error resolving account_id: {e}. Proceeding with account_id as None.", level="WARNING")
                account_id = None # Ensure it's None if resolution fails
        else:
            self._log(f"Using account_id: {account_id}", level="DEBUG")

        if not account_id:
            self._log("No account_id available. Cannot fetch feedback items.", level="ERROR")
            return []

        try:
            # Try using the optimized GSI directly with GraphQL
            if plexus_scorecard_id and plexus_score_id and start_date and end_date:
                self._log("Using direct GraphQL query with GSI", level="DEBUG")
                
                # Construct a direct GraphQL query using the new GSI
                query = """
                query ListFeedbackItemsByGSI(
                    $accountId: String!, 
                    $SortKeyInput: ModelFeedbackItemByAccountScorecardScoreUpdatedAtCompositeKeyConditionInput,
                    $limit: Int,
                    $nextToken: String
                ) {
                    listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt(
                        accountId: $accountId,
                        scorecardIdScoreIdUpdatedAt: $SortKeyInput, # Argument for the composite sort key parts
                        limit: $limit,
                        nextToken: $nextToken
                    ) {
                        items {
                            id
                            accountId
                            scorecardId
                            scoreId
                            cacheKey
                            initialAnswerValue
                            finalAnswerValue
                            initialCommentValue
                            finalCommentValue
                            editCommentValue
                            isAgreement
                            createdAt
                            updatedAt
                        }
                        nextToken
                    }
                }
                """
                
                # Prepare variables for the query
                variables = {
                    "accountId": account_id,
                    "SortKeyInput": { # This object matches the $SortKeyInput variable
                        "scorecardId": {"eq": plexus_scorecard_id},
                        "scoreId": {"eq": plexus_score_id},
                        "updatedAt": {"between": [start_date.isoformat(), end_date.isoformat()]}
                    },
                    "limit": 1000,
                    "nextToken": None
                }
                
                next_token = None
                
                while True:
                    if next_token:
                        variables["nextToken"] = next_token
                    
                    try:
                        # Execute the query
                        response = await asyncio.to_thread(self.api_client.execute, query, variables)
                        
                        if response and 'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt' in response:
                            result = response['listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt']
                            item_dicts = result.get('items', [])
                            
                            # Convert to FeedbackItem objects
                            items = [FeedbackItem.from_dict(item_dict, client=self.api_client) for item_dict in item_dicts]
                            all_items_for_score.extend(items)
                            
                            self._log(f"Fetched {len(items)} items using GSI query (total: {len(all_items_for_score)})")
                            
                            # Get next token for pagination
                            next_token = result.get('nextToken')
                            if not next_token:
                                break
                        else:
                            if response and 'errors' in response:
                                self._log(f"GraphQL errors with GSI query: {response.get('errors')}", level="WARNING")
                            else:
                                self._log("Unexpected response format from GSI query", level="WARNING")
                            raise ValueError("Invalid response format")
                            
                    except Exception as e:
                        self._log(f"Error with GSI query, falling back to standard query: {e}", level="WARNING")
                        # Clear items and use standard method below
                        all_items_for_score = []
                        break
            
            # If we have no items yet (either we didn't try GSI or it failed), use standard filtering
            if not all_items_for_score:
                self._log("Using standard query method", level="DEBUG")
                
                # Build filter for standard query
                filter_params = {
                    "accountId": {"eq": account_id},
                    "scorecardId": {"eq": plexus_scorecard_id},
                    "scoreId": {"eq": plexus_score_id}
                }
                
                # Add date filtering if provided
                if start_date and end_date:
                    filter_params["updatedAt"] = {"between": [start_date.isoformat(), end_date.isoformat()]}
                
                next_token = None
                
                # Use standard list query
                while True:
                    items, next_token = await asyncio.to_thread(
                        FeedbackItem.list,
                        client=self.api_client,
                        filter=filter_params,
                        limit=100,
                        next_token=next_token
                    )
                    
                    all_items_for_score.extend(items)
                    self._log(f"Fetched {len(items)} items using standard query (total: {len(all_items_for_score)})")
                    
                    if not next_token:
                        break
        
        except Exception as e:
            self._log(f"Error during feedback item fetch for score {plexus_score_id}: {str(e)}", level="ERROR")
            # Don't log full traceback, just the error message
        
        self._log(f"Total items fetched for score {plexus_score_id}: {len(all_items_for_score)}")
        return all_items_for_score
    
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
            return {"ac1": None, "item_count": 0, "mismatches": 0, "accuracy": None, "classes_count": 2, 
                    "label_distribution": {}, "confusion_matrix": None, "class_distribution": [], 
                    "predicted_class_distribution": [], "precision": None, "recall": None, "discussion": None}
            
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
            return {"ac1": None, "item_count": 0, "mismatches": 0, "accuracy": None, "classes_count": 2, 
                    "label_distribution": {}, "confusion_matrix": None, "class_distribution": [], 
                    "predicted_class_distribution": [], "precision": None, "recall": None, "discussion": None}

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
            reference_list = [str(i) for i in paired_initial]
            predictions_list = [str(f) for f in paired_final]
            
            # Create Metric.Input object
            metric_input = Metric.Input(reference=reference_list, predictions=predictions_list)
            
            # Calculate Gwet's AC1
            calculation_result = gwet_ac1_calculator.calculate(metric_input)
            ac1_value = calculation_result.value # Get value from the result object

            self._log(f"Gwet's AC1 for {score_id_info}: {ac1_value}")
            
            # Calculate accuracy
            mismatches = sum(1 for i, f in zip(paired_initial, paired_final) if i != f)
            accuracy_percentage = ((valid_pairs_count - mismatches) / valid_pairs_count) * 100 if valid_pairs_count > 0 else None
            
            accuracy_str = f"{accuracy_percentage:.2f}%" if accuracy_percentage is not None else "N/A"
            self._log(f"Analysis results for {score_id_info}: Gwet's AC1={ac1_value}, Items={valid_pairs_count}, Mismatches={mismatches}, Accuracy={accuracy_str}, Classes={num_classes}")
            
            # Generate confusion matrix
            confusion_matrix = self._build_confusion_matrix(paired_initial, paired_final)
            
            # Generate class distribution for visualization
            class_distribution = self._format_class_distribution(label_distribution)
            
            # Generate predicted class distribution for visualization
            predicted_class_distribution = self._format_class_distribution(initial_label_distribution)
            
            # Calculate precision and recall metrics if there are multiple classes
            precision_recall = self._calculate_precision_recall(paired_initial, paired_final, label_distribution.keys())
            
            return {
                "ac1": ac1_value,
                "item_count": valid_pairs_count,
                "mismatches": mismatches,
                "accuracy": accuracy_percentage,
                "classes_count": num_classes,
                "label_distribution": label_distribution,
                "confusion_matrix": confusion_matrix,
                "class_distribution": class_distribution,
                "predicted_class_distribution": predicted_class_distribution,
                "precision": precision_recall.get("precision"),
                "recall": precision_recall.get("recall"),
                "discussion": self._generate_discussion(ac1_value, accuracy_percentage, precision_recall, confusion_matrix)
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
                count = sum(1 for ref, pred in zip(reference_values, predicted_values) 
                           if str(ref) == str(true_class) and str(pred) == str(pred_class))
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
    
    def _generate_discussion(self, ac1: Optional[float], accuracy: Optional[float], 
                            precision_recall: Dict[str, float], confusion_matrix: Dict[str, Any]) -> Optional[str]:
        """
        Generate a discussion text based on the analysis results.
        
        Args:
            ac1: Gwet's AC1 value
            accuracy: Raw agreement percentage
            precision_recall: Dictionary with precision and recall values
            confusion_matrix: Confusion matrix data
            
        Returns:
            Discussion text or None if there's insufficient data
        """
        if ac1 is None or accuracy is None:
            return None
            
        discussion_parts = []
        
        # AC1 interpretation
        if ac1 >= 0.8:
            discussion_parts.append("The agreement level is strong, indicating high consistency between initial and final assessments.")
        elif ac1 >= 0.6:
            discussion_parts.append("The agreement level is moderate, showing reasonable consistency between assessments.")
        elif ac1 >= 0.4:
            discussion_parts.append("The agreement level is fair, with some inconsistency between initial and final assessments.")
        elif ac1 >= 0.0:
            discussion_parts.append("The agreement level is slight, suggesting substantial inconsistency between assessments.")
        else:
            discussion_parts.append("The agreement level is poor, indicating systematic disagreement beyond chance.")
        
        # Accuracy context
        raw_agreement_text = f"The raw agreement rate is {accuracy:.1f}%."
        discussion_parts.append(raw_agreement_text)
        
        # Precision/recall if available
        if precision_recall.get("precision") is not None and precision_recall.get("recall") is not None:
            precision = precision_recall["precision"]
            recall = precision_recall["recall"]
            precision_recall_text = f"Precision is {precision:.1f}% and recall is {recall:.1f}%."
            
            if precision < 70 or recall < 70:
                precision_recall_text += " This suggests potential issues with consistent application of assessment criteria."
            
            discussion_parts.append(precision_recall_text)
        
        # Confusion matrix analysis
        if confusion_matrix and confusion_matrix.get("matrix") and confusion_matrix.get("labels"):
            # Identify most common confusion patterns
            labels = confusion_matrix["labels"]
            matrix_rows = confusion_matrix["matrix"]
            
            # Find off-diagonal maximum (indicating the most common confusion)
            max_confusion = 0
            max_confusion_pair = None
            
            for i, row in enumerate(matrix_rows):
                actual_class = row["actualClassLabel"]
                for j, predicted_class in enumerate(labels):
                    # Skip diagonal (when actual == predicted)
                    if actual_class == predicted_class:
                        continue
                    
                    # Get count from predictedClassCounts dictionary
                    value = row["predictedClassCounts"].get(predicted_class, 0)
                    
                    if value > max_confusion:
                        max_confusion = value
                        max_confusion_pair = (actual_class, predicted_class)
            
            if max_confusion_pair and max_confusion > 0:
                confusion_text = f"The most common confusion occurs between '{max_confusion_pair[0]}' and '{max_confusion_pair[1]}', occurring {max_confusion} times."
                discussion_parts.append(confusion_text)
        
        return " ".join(discussion_parts)

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

# Example of how this block might be configured in a ReportConfiguration:
"""
```block name="Feedback Agreement Analysis"
class: FeedbackAnalysis
scorecard: "1438" # Call Criteria Scorecard ID
days: 30 # Analyze feedback from the last 30 days
# score_id: "44246" # Optional: Call Criteria Question ID to analyze a specific score
```
""" 