from typing import Any, Dict, Optional, Tuple, List
import logging
import asyncio
from datetime import datetime, timedelta

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
            
            # Store the scorecard_id in the instance for later use in Score lookups
            self.scorecard_id = scorecard_id
            self._log(f"Set scorecard_id for lookups: {self.scorecard_id}")
            
            days = int(self.config.get("days", 14))
            
            # Parse date strings if provided
            start_date = self.config.get("start_date")
            if start_date:
                if isinstance(start_date, str):
                    start_date = datetime.strptime(start_date, "%Y-%m-%d")
                elif not isinstance(start_date, datetime):
                    self._log(f"WARNING: start_date has unexpected type: {type(start_date)}")
                    # Try to convert to string first
                    start_date = str(start_date)
                    start_date = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                # Calculate based on days
                start_date = datetime.now() - timedelta(days=days)
                
            end_date = self.config.get("end_date")
            if end_date:
                if isinstance(end_date, str):
                    end_date = datetime.strptime(end_date, "%Y-%m-%d")
                elif not isinstance(end_date, datetime):
                    self._log(f"WARNING: end_date has unexpected type: {type(end_date)}")
                    # Try to convert to string first
                    end_date = str(end_date)
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
                    "overall_ac1": None,
                    "scores": [],
                    "total_items": 0,
                    "total_mismatches": 0,
                    "accuracy": 0,
                    "date_range": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    }
                }, "\n".join(self.log_messages)
            
            # Process and analyze the feedback data
            analysis_results = self._analyze_feedback(feedback_items)
            self._log("Feedback analysis completed successfully")
            
            # Structure the output data with the new format
            final_output_data = {
                "overall_ac1": analysis_results.get("overall_ac1"),
                "scores": analysis_results.get("scores", []),
                "total_items": len(feedback_items),
                "total_mismatches": analysis_results.get("total_mismatches", 0),
                "accuracy": analysis_results.get("accuracy", 0),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

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
            "question_ac1s": {},  # Keep using question_ac1s internally for processing
            "total_mismatches": 0,
            "accuracy": 0
        }
        
        if not feedback_items:
            self._log("No feedback items to analyze")
            # Convert to new format before returning
            return {
                "overall_ac1": None,
                "scores": [],
                "total_mismatches": 0,
                "accuracy": 0
            }
            
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
                        
                        # Calculate mismatch percentage and accuracy
                        mismatch_percentage = (score_mismatches / valid_items) * 100 if valid_items > 0 else 0
                        accuracy = 100 - mismatch_percentage
                        
                        # Store results for this score
                        results["question_ac1s"][score_id] = {
                            "ac1": result.value,
                            "name": score_name,
                            "total_comparisons": valid_items,
                            "mismatches": score_mismatches,
                            "accuracy": accuracy
                        }
                        
                        self._log(f"Score {score_id}: Gwet AC1 = {result.value:.4f}, mismatches: {score_mismatches}/{valid_items}, accuracy: {accuracy:.1f}%")
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
                
                # Calculate mismatch_percentage and then convert to accuracy
                mismatch_percentage = (total_mismatches / total_items) * 100 if total_items > 0 else 0
                accuracy = 100 - mismatch_percentage
                
                # Store overall results
                results["overall_ac1"] = result.value
                results["total_mismatches"] = total_mismatches
                results["accuracy"] = accuracy
                
                self._log(f"Overall Gwet AC1 = {result.value:.4f}, total mismatches: {total_mismatches}/{total_items}")
                self._log(f"Accuracy: {accuracy:.1f}%")
            except Exception as e:
                self._log(f"Error calculating overall Gwet AC1: {str(e)}")
        else:
            self._log(f"Skipping overall Gwet AC1 calculation - insufficient data ({total_items} items)")
        
        # At the end of the method, before returning
        # Convert question_ac1s to scores list and lookup actual score details
        scores_list = []
        
        for score_id, score_data in results["question_ac1s"].items():
            # Store the original metrics for later use
            ac1_value = score_data.get("ac1")
            total_comparisons = score_data.get("total_comparisons")
            mismatches = score_data.get("mismatches")
            accuracy = score_data.get("accuracy")
            
            # Log the original values
            self._log(f"Original score metrics for {score_id}: ac1={ac1_value}, " +
                     f"total_comparisons={total_comparisons}, " +
                     f"mismatches={mismatches}, " +
                     f"accuracy={accuracy}")
            
            # Look up the actual Score record to get the real name and externalId
            score_name = score_data.get("name", f"Score {score_id}")
            external_id = score_id
            
            try:
                self._log(f"Attempting to look up Score record for ID: {score_id}")
                
                # Add API client check
                if not self.api_client:
                    self._log("WARNING: No API client available for Score lookup")
                else:
                    # Attempt the lookup with detailed logging
                    try:
                        # Execute the GraphQL query directly to help diagnose any issues
                        query = """
                        query GetScore($id: ID!) {
                            getScore(id: $id) {
                                id
                                name
                                externalId
                            }
                        }
                        """
                        
                        self._log(f"Executing GraphQL query for Score {score_id}")
                        result = self.api_client.execute(query, {'id': score_id})
                        self._log(f"GraphQL result: {result}")
                        
                        if result and 'getScore' in result and result['getScore']:
                            api_score_data = result['getScore']
                            score_name = api_score_data.get('name', score_name)
                            external_id = api_score_data.get('externalId', external_id)
                            self._log(f"Successfully found score: {score_name} (external ID: {external_id})")
                        else:
                            self._log(f"Score lookup returned no data for ID {score_id}")
                            
                            # Fall back to using the Score model
                            self._log("Trying fallback with Score.get_by_id")
                            try:
                                score_record = Score.get_by_id(score_id, self.api_client)
                                score_name = score_record.name
                                external_id = score_record.externalId
                                self._log(f"Fallback succeeded - found score: {score_name} (external ID: {external_id})")
                            except Exception as e:
                                self._log(f"Score.get_by_id failed: {str(e)}")
                                
                                # If still not found, try alternative lookup methods
                                if not score_name or score_name == f"Score {score_id}":
                                    self._log("Direct lookup failed, trying alternative lookup methods")
                                    
                                    # Check if we have the scorecard_id stored from generate method
                                    if hasattr(self, 'scorecard_id') and self.scorecard_id:
                                        scorecard_id = self.scorecard_id
                                        self._log(f"Using scorecard_id for lookup: {scorecard_id}")
                                        
                                        # Try getting scores for the section
                                        try:
                                            self._log("Attempting to list all scores for this scorecard")
                                            
                                            # Query to get score details (first try direct score search)
                                            score_search_query = """
                                            query GetScoresByName($name: String!) {
                                                listScoreByName(name: $name) {
                                                    items {
                                                        id
                                                        name
                                                        externalId
                                                        sectionId
                                                    }
                                                }
                                            }
                                            """
                                            
                                            # Try searching by ID as name (sometimes IDs are used as names)
                                            score_search_result = self.api_client.execute(score_search_query, {'name': score_id})
                                            self._log(f"Score search by name result: {score_search_result}")
                                            
                                            # Process search results
                                            if (score_search_result and 'listScoreByName' in score_search_result and 
                                                    score_search_result['listScoreByName']['items']):
                                                for s in score_search_result['listScoreByName']['items']:
                                                    if s['id'] == score_id:
                                                        score_name = s['name']
                                                        external_id = s['externalId']
                                                        self._log(f"Found score via name search: {score_name} (external ID: {external_id})")
                                                        break
                                            
                                            # Also try external ID search
                                            if score_name == f"Score {score_id}":
                                                external_id_query = """
                                                query GetScoresByExternalId($externalId: String!) {
                                                    listScoreByExternalId(externalId: $externalId) {
                                                        items {
                                                            id
                                                            name
                                                            externalId
                                                        }
                                                    }
                                                }
                                                """
                                                
                                                # Try searching by ID as externalId (sometimes IDs are used as externalIds)
                                                ext_id_result = self.api_client.execute(external_id_query, {'externalId': score_id})
                                                self._log(f"Score search by externalId result: {ext_id_result}")
                                                
                                                if (ext_id_result and 'listScoreByExternalId' in ext_id_result and 
                                                        ext_id_result['listScoreByExternalId']['items']):
                                                    for s in ext_id_result['listScoreByExternalId']['items']:
                                                        if s['id'] == score_id:
                                                            score_name = s['name']
                                                            external_id = s['externalId']
                                                            self._log(f"Found score via externalId search: {score_name} (external ID: {external_id})")
                                                            break
                                            
                                            # Last resort: try direct listing of all scores
                                            if score_name == f"Score {score_id}":
                                                self._log("Falling back to direct score query")
                                                direct_query = """
                                                query ListAllScores {
                                                    listScores(limit: 100) {
                                                        items {
                                                            id
                                                            name
                                                            externalId
                                                        }
                                                    }
                                                }
                                                """
                                                direct_result = self.api_client.execute(direct_query, {})
                                                self._log(f"Direct score listing result: {direct_result}")
                                                
                                                if direct_result and 'listScores' in direct_result:
                                                    scores = direct_result['listScores']['items']
                                                    for s in scores:
                                                        if s['id'] == score_id:
                                                            score_name = s['name']
                                                            external_id = s['externalId']
                                                            self._log(f"Found score via direct listing: {score_name} (external ID: {external_id})")
                                                            break
                                        except Exception as section_e:
                                            self._log(f"Error listing scores for scorecard: {str(section_e)}")
                    except Exception as inner_e:
                        self._log(f"Error during Score lookup: {str(inner_e)}")
                        import traceback
                        self._log(traceback.format_exc())
            except Exception as e:
                self._log(f"Could not retrieve score record for ID {score_id}: {str(e)}")
                self._log(f"Using fallback values: name='{score_name}', external_id='{external_id}'")
            
            score_entry = {
                "id": score_id,
                "name": score_name,
                "external_id": external_id,
                "ac1": ac1_value,
                "total_comparisons": total_comparisons,
                "mismatches": mismatches,
                "accuracy": accuracy
            }
            
            # Log the metric values to verify they're being preserved
            self._log(f"Score metrics for {score_id}: ac1={ac1_value}, " +
                     f"total_comparisons={total_comparisons}, " +
                     f"mismatches={mismatches}, " +
                     f"accuracy={accuracy}")
            
            scores_list.append(score_entry)
        
        # Replace question_ac1s with scores in the results
        results["scores"] = scores_list
        del results["question_ac1s"]
        
        return results 