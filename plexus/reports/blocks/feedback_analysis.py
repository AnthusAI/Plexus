from typing import Any, Dict, Optional, Tuple, List
import logging
import asyncio
from datetime import datetime, timedelta

from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric
from plexus.dashboard.api.models.feedback_item import FeedbackItem

from .base import BaseReportBlock

logger = logging.getLogger(__name__)


class FeedbackAnalysis(BaseReportBlock):
    """
    Analyzes feedback data using Gwet's AC1 agreement coefficient.
    
    This block retrieves FeedbackItem records and compares initial and final answer values
    to calculate agreement scores using Gwet's AC1, which is more robust than Cohen's Kappa
    for highly imbalanced class distributions.
    
    Config:
        scorecard (str): The ID or name of the Scorecard to analyze.
        days (int, optional): Number of days in the past to analyze (default: 14).
        start_date (str, optional): Start date for analysis in YYYY-MM-DD format.
                                   If provided, overrides 'days'.
        end_date (str, optional): End date for analysis in YYYY-MM-DD format.
                                 Defaults to today if not specified.
        score_id (str, optional): Specific Score ID to analyze.
                                 If specified, only this score will be analyzed.
    """

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetches feedback data and performs agreement analysis using Gwet's AC1."""
        self.log_messages = []  # Reset logs for this run
        final_output_data = None  # Default to None

        try:
            self._log("Starting FeedbackAnalysis block generation.")
            
            # Extract configuration parameters with defaults
            scorecard_id = self.config.get("scorecard")
            if not scorecard_id:
                self._log("ERROR: 'scorecard' identifier missing in block configuration.")
                raise ValueError("'scorecard' is required in the block configuration.")
            
            days = int(self.config.get("days", 14))
            
            # Parse date strings if provided
            start_date = self.config.get("start_date")
            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                # Calculate based on days
                start_date = datetime.now() - timedelta(days=days)
                
            end_date = self.config.get("end_date")
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
            else:
                end_date = datetime.now()
                
            # Optional score filter
            score_id = self.config.get("score_id")
            
            self._log(f"Analyzing feedback for scorecard: {scorecard_id}")
            self._log(f"Date range: {start_date.date()} to {end_date.date()}")
            if score_id:
                self._log(f"Filtering by score ID: {score_id}")
            
            # Fetch FeedbackItem records from the API
            feedback_items = await self._fetch_feedback_items(scorecard_id, score_id)
            self._log(f"Retrieved {len(feedback_items)} feedback items for analysis")
            
            if not feedback_items:
                self._log("No feedback items found for the specified criteria.")
                return {
                    "type": "FeedbackAnalysis",
                    "data": {
                        "overall_ac1": None,
                        "question_ac1s": {},
                        "total_items": 0,
                        "analysis_date": datetime.now().isoformat(),
                        "scorecard_id": scorecard_id,
                        "date_range": {
                            "start": start_date.isoformat(),
                            "end": end_date.isoformat()
                        }
                    }
                }, "\n".join(self.log_messages)
            
            # Process and analyze the feedback data
            analysis_results = self._analyze_feedback(feedback_items)
            self._log("Feedback analysis completed successfully")
            
            # Structure the output data
            final_output_data = {
                "type": "FeedbackAnalysis",
                "data": {
                    "overall_ac1": analysis_results.get("overall_ac1"),
                    "question_ac1s": analysis_results.get("question_ac1s", {}),
                    "total_items": len(feedback_items),
                    "total_mismatches": analysis_results.get("total_mismatches", 0),
                    "mismatch_percentage": analysis_results.get("mismatch_percentage", 0),
                    "analysis_date": datetime.now().isoformat(),
                    "scorecard_id": scorecard_id,
                    "date_range": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    }
                }
            }
            
            # Add score_id to the output if one was specified
            if score_id:
                final_output_data["data"]["score_id"] = score_id

        except ValueError as ve:
            # Log specific config errors
            self._log(f"Configuration Error: {ve}")
            # final_output_data remains None
        except Exception as e:
            # Log unexpected errors during generation
            self._log(f"ERROR during FeedbackAnalysis generation: {str(e)}")
            import traceback
            self._log(traceback.format_exc())
            # final_output_data remains None

        # Format and Return
        log_string = "\n".join(self.log_messages) if self.log_messages else None
        return final_output_data, log_string
    
    async def _fetch_feedback_items(self, scorecard_id: str, score_id: Optional[str] = None) -> List[FeedbackItem]:
        """
        Fetch FeedbackItem records from the API.
        
        Args:
            scorecard_id: ID of the scorecard to analyze
            score_id: Optional ID of the specific score to analyze
            
        Returns:
            List of FeedbackItem objects
        """
        self._log(f"Fetching feedback items for scorecard ID: {scorecard_id}")
        
        # Start with an empty list
        all_items = []
        next_token = None
        
        # Get the account_id from the current configuration
        account_id = self.params.get("account_id")
        if not account_id:
            # Try to get it from the API client if available
            try:
                account_id = self.api_client.account_id
            except Exception:
                self._log("WARNING: No account_id available. Using default filter.")
        
        # Make paginated API calls to get all feedback items
        while True:
            try:
                items, next_token = FeedbackItem.list(
                    client=self.api_client,
                    account_id=account_id,
                    scorecard_id=scorecard_id,
                    score_id=score_id,
                    limit=100,
                    next_token=next_token
                )
                all_items.extend(items)
                self._log(f"Fetched {len(items)} items (total so far: {len(all_items)})")
                
                if not next_token:
                    break
            except Exception as e:
                self._log(f"Error fetching feedback items: {str(e)}")
                break
                
        return all_items
    
    def _analyze_feedback(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """
        Analyze feedback items using Gwet's AC1.
        
        Args:
            feedback_items: List of FeedbackItem objects to analyze
            
        Returns:
            Dictionary with analysis results
        """
        # Initialize results
        results = {
            "overall_ac1": None,
            "question_ac1s": {},
            "total_mismatches": 0,
            "mismatch_percentage": 0
        }
        
        if not feedback_items:
            self._log("No feedback items to analyze")
            return results
            
        # Organize data by question/score
        items_by_score = {}
        for item in feedback_items:
            score_id = item.scoreId
            if score_id not in items_by_score:
                items_by_score[score_id] = []
            items_by_score[score_id].append(item)
        
        # Prepare data for overall AC1 calculation
        all_initial_values = []
        all_final_values = []
        total_mismatches = 0
        
        # Process each question/score
        for score_id, items in items_by_score.items():
            # Get score name if available (future enhancement)
            score_name = f"Score {score_id}"
            
            # Extract values for this score
            initial_values = [item.initialAnswerValue for item in items if item.initialAnswerValue is not None]
            final_values = [item.finalAnswerValue for item in items if item.finalAnswerValue is not None]
            
            # Ensure we have matching data points
            valid_items = min(len(initial_values), len(final_values))
            if valid_items < len(items):
                self._log(f"Warning: {len(items) - valid_items} items for {score_name} have missing values")
                
            if valid_items > 0:
                # Take only the valid range that has both initial and final values
                initial_values = initial_values[:valid_items]
                final_values = final_values[:valid_items]
                
                # Count mismatches
                score_mismatches = sum(1 for i, f in zip(initial_values, final_values) if i != f)
                total_mismatches += score_mismatches
                
                # Add to overall data
                all_initial_values.extend(initial_values)
                all_final_values.extend(final_values)
                
                # Calculate AC1 for this score
                if len(initial_values) >= 2:  # Need at least 2 ratings
                    try:
                        # Create a GwetAC1 instance
                        gwet_ac1 = GwetAC1()
                        
                        # Create a Metric.Input object
                        metric_input = Metric.Input(
                            reference=initial_values,
                            predictions=final_values
                        )
                        
                        # Calculate Gwet's AC1
                        result = gwet_ac1.calculate(metric_input)
                        
                        # Store results for this score
                        results["question_ac1s"][score_id] = {
                            "ac1": result.value,
                            "name": score_name,
                            "total_comparisons": valid_items,
                            "mismatches": score_mismatches,
                            "mismatch_percentage": (score_mismatches / valid_items) * 100 if valid_items > 0 else 0
                        }
                        
                        self._log(f"Score {score_id}: Gwet AC1 = {result.value:.4f}, mismatches: {score_mismatches}/{valid_items}")
                    except Exception as e:
                        self._log(f"Error calculating Gwet AC1 for score {score_id}: {str(e)}")
                else:
                    self._log(f"Skipping Gwet AC1 calculation for score {score_id} - insufficient data ({valid_items} items)")
        
        # Calculate overall AC1
        total_items = len(all_initial_values)
        if total_items >= 2:
            try:
                # Create a GwetAC1 instance
                gwet_ac1 = GwetAC1()
                
                # Create a Metric.Input object
                metric_input = Metric.Input(
                    reference=all_initial_values,
                    predictions=all_final_values
                )
                
                # Calculate overall Gwet's AC1
                result = gwet_ac1.calculate(metric_input)
                
                # Store overall results
                results["overall_ac1"] = result.value
                results["total_mismatches"] = total_mismatches
                results["mismatch_percentage"] = (total_mismatches / total_items) * 100 if total_items > 0 else 0
                
                self._log(f"Overall Gwet AC1 = {result.value:.4f}, total mismatches: {total_mismatches}/{total_items}")
            except Exception as e:
                self._log(f"Error calculating overall Gwet AC1: {str(e)}")
        else:
            self._log(f"Skipping overall Gwet AC1 calculation - insufficient data ({total_items} items)")
        
        return results 