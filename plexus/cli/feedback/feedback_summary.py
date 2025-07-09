"""
Command for generating feedback summary analysis with metrics and confusion matrix.
"""

import click
import logging
import traceback
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from collections import Counter
import yaml

from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.cli.reports.utils import resolve_account_id_for_command
from plexus.cli.memoized_resolvers import memoized_resolve_scorecard_identifier, memoized_resolve_score_identifier
from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric

logger = logging.getLogger(__name__)


class FeedbackSummaryAnalyzer:
    """
    Standalone analyzer for feedback summary statistics.
    Extracted from the FeedbackAnalysis report block for CLI use.
    """
    
    def __init__(self, client):
        self.api_client = client
        self.log_messages = []
    
    def _log(self, message: str, level="INFO"):
        """Helper method to log messages."""
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"[FeedbackSummary] {message}")
        self.log_messages.append(f"{datetime.now().isoformat()} - {level}: {message}")
    
    async def fetch_feedback_items_for_score(self, account_id: str, scorecard_id: str, score_id: str, 
                                           start_date: datetime, end_date: datetime) -> List[FeedbackItem]:
        """
        Fetch feedback items for a specific score within a date range.
        Uses the same GSI query approach as the FeedbackAnalysis report block.
        """
        self._log(f"Fetching feedback items for Scorecard ID: {scorecard_id}, Score ID: {score_id}")
        self._log(f"Date range: {start_date.isoformat()} to {end_date.isoformat()}")
        
        all_items_for_score = []
        
        try:
            # Use the optimized GSI directly with GraphQL (same approach as FeedbackAnalysis report block)
            self._log("Using direct GraphQL query with GSI", level="DEBUG")
            
            # Construct a direct GraphQL query using the GSI
            query = """
            query ListFeedbackItemsByGSI(
                $accountId: String!,
                $composite_sk_condition: ModelFeedbackItemByAccountScorecardScoreUpdatedAtCompositeKeyConditionInput,
                $limit: Int,
                $nextToken: String,
                $sortDirection: ModelSortDirection
            ) {
                listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt(
                    accountId: $accountId,
                    scorecardIdScoreIdUpdatedAt: $composite_sk_condition,
                    limit: $limit,
                    nextToken: $nextToken,
                    sortDirection: $sortDirection
                ) {
                    items {
                        id
                        accountId
                        scorecardId
                        scoreId
                        itemId
                        cacheKey
                        initialAnswerValue
                        finalAnswerValue
                        initialCommentValue
                        finalCommentValue
                        editCommentValue
                        editedAt
                        editorName
                        isAgreement
                        createdAt
                        updatedAt
                        item {
                            id
                            identifiers
                            externalId
                        }
                    }
                    nextToken
                }
            }
            """
            
            # Prepare variables for the query
            variables = {
                "accountId": account_id,
                "composite_sk_condition": {
                    "between": [
                        {
                            "scorecardId": str(scorecard_id),
                            "scoreId": str(score_id),
                            "updatedAt": start_date.isoformat()
                        },
                        {
                            "scorecardId": str(scorecard_id),
                            "scoreId": str(score_id),
                            "updatedAt": end_date.isoformat()
                        }
                    ]
                },
                "limit": 100,
                "nextToken": None,
                "sortDirection": "DESC"
            }
            
            self._log(f"GraphQL variables: {variables}", level="DEBUG")
            
            next_token = None
            
            while True:
                if next_token:
                    variables["nextToken"] = next_token
                
                try:
                    response = await asyncio.to_thread(self.api_client.execute, query, variables)
                    
                    if response and 'errors' in response:
                        self._log(f"GraphQL errors: {response.get('errors')}", level="ERROR")
                        # Fall back to the original simple filter approach if GSI fails
                        return await self._fetch_feedback_items_fallback(account_id, scorecard_id, score_id, start_date, end_date)
                    
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
                        # Fall back to the original approach
                        return await self._fetch_feedback_items_fallback(account_id, scorecard_id, score_id, start_date, end_date)
                        
                except Exception as e:
                    self._log(f"Error during GSI query execution: {e}. Falling back to simple filter approach.", level="WARNING")
                    return await self._fetch_feedback_items_fallback(account_id, scorecard_id, score_id, start_date, end_date)
                    
        except Exception as e:
            self._log(f"Error during feedback item fetch for score {score_id}: {str(e)}", level="ERROR")
            return await self._fetch_feedback_items_fallback(account_id, scorecard_id, score_id, start_date, end_date)
        
        self._log(f"Total items fetched for score {score_id}: {len(all_items_for_score)}")
        return all_items_for_score

    async def _fetch_feedback_items_fallback(self, account_id: str, scorecard_id: str, score_id: str, 
                                           start_date: datetime, end_date: datetime) -> List[FeedbackItem]:
        """
        Fallback method using the simple filter approach (original implementation).
        """
        self._log("Using fallback simple filter approach", level="WARNING")
        
        filter_condition = {
            "and": [
                {"accountId": {"eq": account_id}},
                {"scorecardId": {"eq": scorecard_id}},
                {"scoreId": {"eq": score_id}},
                {"updatedAt": {"ge": start_date.isoformat()}},
                {"updatedAt": {"le": end_date.isoformat()}}
            ]
        }
        
        try:
            feedback_items, _ = FeedbackItem.list(
                client=self.api_client,
                limit=1000,  # Use a large limit to get all matching items
                filter=filter_condition,
                fields=FeedbackItem.GRAPHQL_BASE_FIELDS
            )
            
            self._log(f"Retrieved {len(feedback_items)} feedback items using fallback approach")
            return feedback_items
            
        except Exception as e:
            self._log(f"Error fetching feedback items with fallback: {e}", level="ERROR")
            return []
    
    def analyze_feedback_data_gwet(self, feedback_items: List[FeedbackItem], score_id: str) -> Dict[str, Any]:
        """
        Analyze feedback items using Gwet's AC1 and generate summary statistics.
        """
        self._log(f"Analyzing {len(feedback_items)} feedback items")
        
        if not feedback_items:
            return {
                "ac1": None, "item_count": 0, "mismatches": 0, "agreements": 0, "accuracy": None,
                "classes_count": 2, "label_distribution": {}, "confusion_matrix": None,
                "class_distribution": [], "predicted_class_distribution": [],
                "precision": None, "recall": None, "warning": "No data."
            }
        
        # Extract valid pairs
        valid_pairs_count = 0
        paired_initial = []
        paired_final = []
        
        for item in feedback_items:
            if item.initialAnswerValue is not None and item.finalAnswerValue is not None:
                paired_initial.append(item.initialAnswerValue)
                paired_final.append(item.finalAnswerValue)
                valid_pairs_count += 1
        
        self._log(f"Found {valid_pairs_count} valid initial/final pairs")
        
        if valid_pairs_count == 0:
            return {
                "ac1": None, "item_count": 0, "mismatches": 0, "agreements": 0, "accuracy": None,
                "classes_count": 2, "label_distribution": {}, "confusion_matrix": None,
                "class_distribution": [], "predicted_class_distribution": [],
                "precision": None, "recall": None, "warning": "No data."
            }
        
        # Calculate distributions
        label_distribution = dict(Counter(paired_final))
        initial_label_distribution = dict(Counter(paired_initial))
        
        # Get number of classes from score configuration
        num_classes = 2  # Default to binary
        try:
            # Try to get the champion version configuration to determine valid classes
            query = """
            query GetScore($id: ID!) {
                getScore(id: $id) {
                    id
                    name
                    championVersion {
                        id
                        configuration
                    }
                }
            }
            """
            result = self.api_client.execute(query, {'id': score_id})
            if result and 'getScore' in result and result['getScore']:
                score_data = result['getScore']
                if score_data.get('championVersion') and score_data['championVersion'].get('configuration'):
                    try:
                        import yaml
                        config = yaml.safe_load(score_data['championVersion']['configuration'])
                        if config and 'validValues' in config:
                            valid_values = config['validValues']
                            num_classes = len(valid_values) if isinstance(valid_values, list) else 2
                            self._log(f"Found {num_classes} valid classes in score configuration")
                    except (yaml.YAMLError, TypeError, KeyError):
                        self._log("Error parsing score configuration YAML, defaulting to 2", level="WARNING")
        except Exception as e:
            self._log(f"Error getting valid classes count, defaulting to 2: {e}", level="WARNING")
        
        # Calculate Gwet's AC1
        try:
            gwet_ac1_calculator = GwetAC1()
            
            # Final answer is reference (ground truth), Initial answer is prediction
            reference_list = [str(f) for f in paired_final]
            predictions_list = [str(i) for i in paired_initial]
            
            metric_input = Metric.Input(reference=reference_list, predictions=predictions_list)
            calculation_result = gwet_ac1_calculator.calculate(metric_input)
            ac1_value = calculation_result.value
            
            # Calculate accuracy
            mismatches = sum(1 for i, f in zip(paired_initial, paired_final) if i != f)
            agreements = valid_pairs_count - mismatches
            accuracy_percentage = (agreements / valid_pairs_count) * 100 if valid_pairs_count > 0 else None
            
            # Generate confusion matrix
            confusion_matrix = self._build_confusion_matrix(paired_final, paired_initial)
            
            # Generate class distributions for visualization
            class_distribution = self._format_class_distribution(label_distribution)
            predicted_class_distribution = self._format_class_distribution(initial_label_distribution)
            
            # Calculate precision and recall
            precision_recall = self._calculate_precision_recall(paired_final, paired_initial, label_distribution.keys())
            
            # Generate warnings
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
                "warning": warnings
            }
            
        except Exception as e:
            self._log(f"Error calculating Gwet's AC1: {e}", level="ERROR")
            raise
    
    def _build_confusion_matrix(self, reference_values: List, predicted_values: List) -> Dict[str, Any]:
        """Build a confusion matrix from reference and predicted values."""
        # Get unique classes and ensure they are strings
        all_classes = sorted(list(set(str(v) for v in reference_values + predicted_values)))
        
        matrix_result = {
            "labels": all_classes,
            "matrix": []
        }
        
        # Build matrix rows
        for true_class in all_classes:
            row = {
                "actualClassLabel": true_class,
                "predictedClassCounts": {}
            }
            
            # Add counts for each predicted class
            for pred_class in all_classes:
                count = 0
                for ref_val, pred_val in zip(reference_values, predicted_values):
                    if str(ref_val) == str(true_class) and str(pred_val) == str(pred_class):
                        count += 1
                row["predictedClassCounts"][pred_class] = count
            
            matrix_result["matrix"].append(row)
        
        return matrix_result
    
    def _format_class_distribution(self, distribution: Dict[Any, int]) -> List[Dict[str, Any]]:
        """Format class distribution for visualization."""
        if not distribution:
            return []
        
        result = [
            {
                "label": str(label),
                "count": count
            }
            for label, count in distribution.items()
        ]
        
        # Sort by count descending
        result.sort(key=lambda x: x["count"], reverse=True)
        return result
    
    def _calculate_precision_recall(self, reference_values: List, predicted_values: List, classes: Any) -> Dict[str, float]:
        """Calculate precision and recall metrics."""
        result = {"precision": None, "recall": None}
        
        try:
            str_reference = [str(v) for v in reference_values]
            str_predicted = [str(v) for v in predicted_values]
            str_classes = [str(c) for c in classes]
            
            if len(str_classes) == 2:
                # Binary classification
                positive_class = str_classes[0]
                
                true_positives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                   if ref == positive_class and pred == positive_class)
                false_positives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                    if ref != positive_class and pred == positive_class)
                false_negatives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                    if ref == positive_class and pred != positive_class)
                
                precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
                recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
                
                result = {"precision": precision * 100, "recall": recall * 100}
            else:
                # Multiclass - macro averaging
                precisions = []
                recalls = []
                
                for cls in str_classes:
                    true_positives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                       if ref == cls and pred == cls)
                    false_positives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                        if ref != cls and pred == cls)
                    false_negatives = sum(1 for ref, pred in zip(str_reference, str_predicted) 
                                        if ref == cls and pred != cls)
                    
                    class_precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
                    class_recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
                    
                    precisions.append(class_precision)
                    recalls.append(class_recall)
                
                macro_precision = sum(precisions) / len(precisions) if precisions else 0
                macro_recall = sum(recalls) / len(recalls) if recalls else 0
                
                result = {"precision": macro_precision * 100, "recall": macro_recall * 100}
        
        except Exception as e:
            self._log(f"Error calculating precision/recall: {e}", level="WARNING")
        
        return result
    
    def _generate_warnings(self, ac1: Optional[float], label_distribution: Dict[Any, int]) -> Optional[str]:
        """Generate warnings based on analysis conditions."""
        warnings = []
        
        if ac1 is not None and ac1 < 0:
            warnings.append("Systematic disagreement.")
        elif ac1 is not None and ac1 == 0:
            warnings.append("Random chance.")
        
        if label_distribution and len(label_distribution) == 1:
            single_class = list(label_distribution.keys())[0]
            warnings.append(f"Single class ({single_class}).")
        elif label_distribution and len(label_distribution) > 1:
            if not self._is_distribution_balanced(label_distribution):
                warnings.append("Imbalanced classes.")
        
        return " ".join(warnings) if warnings else None
    
    def _is_distribution_balanced(self, label_distribution: Dict[Any, int]) -> bool:
        """Check if class distribution is balanced using 20% tolerance."""
        if not label_distribution or len(label_distribution) <= 1:
            return True
        
        total = sum(label_distribution.values())
        expected_count = total / len(label_distribution)
        tolerance = 0.2  # 20% tolerance
        
        return all(
            abs(count - expected_count) <= expected_count * tolerance 
            for count in label_distribution.values()
        )


@click.command(name="summary")
@click.option('--scorecard', required=True, help='The scorecard to analyze feedback for (accepts ID, name, key, or external ID).')
@click.option('--score', required=True, help='The score to analyze feedback for (accepts ID, name, key, or external ID).')
@click.option('--days', type=int, default=30, help='Number of days to look back for feedback items.')
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
def feedback_summary(
    scorecard: str,
    score: str,
    days: int,
    account_identifier: Optional[str]
):
    """
    Generate a summary analysis of feedback data for a scorecard and score.
    
    This command provides high-level metrics including:
    - Total feedback items analyzed
    - Gwet's AC1 agreement coefficient
    - Accuracy percentage
    - Confusion matrix
    - Class distributions
    - Precision and recall metrics
    - Warnings about data quality issues
    
    The output is formatted as YAML for easy parsing and integration with other tools.
    """
    client = create_client()
    account_id = resolve_account_id_for_command(client, account_identifier)
    
    try:
        # Resolve scorecard identifier to ID
        scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard)
        if not scorecard_id:
            console.print(f"[bold red]Error:[/bold red] No scorecard found with identifier: {scorecard}")
            return
        
        # Resolve score identifier to ID within the scorecard
        score_id = memoized_resolve_score_identifier(client, scorecard_id, score)
        if not score_id:
            console.print(f"[bold red]Error:[/bold red] No score found with identifier: {score} in scorecard: {scorecard}")
            return
        
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Create analyzer and run analysis
        analyzer = FeedbackSummaryAnalyzer(client)
        
        # Fetch feedback items
        feedback_items = asyncio.run(analyzer.fetch_feedback_items_for_score(
            account_id, scorecard_id, score_id, start_date, end_date
        ))
        
        # Analyze the data
        analysis_result = analyzer.analyze_feedback_data_gwet(feedback_items, score_id)
        
        # Build output structure
        output_data = {
            'context': {
                'command': f'plexus feedback summary --scorecard "{scorecard}" --score "{score}" --days {days}',
                'scorecard': scorecard,
                'scorecard_id': scorecard_id,
                'score': score,
                'score_id': score_id,
                'account_id': account_id,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': days
                }
            },
            'summary': {
                'total_items': analysis_result['item_count'],
                'agreements': analysis_result['agreements'],
                'mismatches': analysis_result['mismatches'],
                'accuracy_percent': analysis_result['accuracy'],
                'gwet_ac1': analysis_result['ac1'],
                'classes_count': analysis_result['classes_count'],
                'warning': analysis_result['warning']
            },
            'metrics': {
                'precision_percent': analysis_result['precision'],
                'recall_percent': analysis_result['recall']
            },
            'confusion_matrix': analysis_result['confusion_matrix'],
            'class_distributions': {
                'actual_classes': analysis_result['class_distribution'],
                'predicted_classes': analysis_result['predicted_class_distribution']
            },
            'raw_distributions': {
                'final_values': analysis_result['label_distribution'],
                'initial_values': dict(Counter(
                    item.initialAnswerValue for item in feedback_items 
                    if item.initialAnswerValue is not None
                ))
            }
        }
        
        # Output as YAML with header comment
        print("# Plexus Feedback Summary Analysis")
        print("# ")
        print("# This summary provides key metrics for feedback analysis including:")
        print("# - Agreement statistics (Gwet's AC1, accuracy)")
        print("# - Confusion matrix showing prediction vs actual patterns")
        print("# - Class distribution analysis")
        print("# - Quality warnings and recommendations")
        print("# ")
        print("# Use this summary to identify which confusion matrix cells to investigate")
        print("# with 'plexus feedback find' for detailed examples.")
        print("")
        
        yaml_output = yaml.dump(
            output_data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            indent=2
        )
        print(yaml_output)
        
    except Exception as e:
        error_msg = f"Failed to generate feedback summary: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        console.print(f"[bold red]{error_msg}[/bold red]") 