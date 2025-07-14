"""
Shared service for feedback item operations.
This service provides a consistent interface for fetching feedback items
that can be used by both CLI commands and MCP tools.
"""

import logging
import asyncio
import random
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from collections import Counter

from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric

logger = logging.getLogger(__name__)


@dataclass
class FeedbackItemSummary:
    """Token-efficient summary of a feedback item for alignment work."""
    item_id: str
    external_id: Optional[str]
    initial_value: Optional[str]
    final_value: Optional[str]
    initial_explanation: Optional[str]
    final_explanation: Optional[str]
    edit_comment: Optional[str]


@dataclass
class FeedbackSearchContext:
    """Context information for feedback search results."""
    scorecard_name: str
    score_name: str
    scorecard_id: str
    score_id: str
    account_id: str
    filters: Dict[str, Any]
    total_found: int


@dataclass
class FeedbackSearchResult:
    """Complete feedback search result with context and items."""
    context: FeedbackSearchContext
    feedback_items: List[FeedbackItemSummary]


@dataclass
class FeedbackSummaryResult:
    """Complete feedback summary with context and analysis."""
    context: FeedbackSearchContext
    analysis: Dict[str, Any]
    recommendation: str


class FeedbackService:
    """
    Service class for feedback item operations.
    Provides consistent querying logic that can be shared between CLI and MCP tools.
    """
    
    @staticmethod
    def _convert_feedback_item_to_summary(item: FeedbackItem) -> FeedbackItemSummary:
        """
        Convert a FeedbackItem to a token-efficient summary.
        
        Args:
            item: The FeedbackItem to convert
            
        Returns:
            FeedbackItemSummary with only the fields needed for alignment work
        """
        # Extract external_id from the related item if available
        external_id = None
        if hasattr(item, 'item') and item.item and hasattr(item.item, 'externalId'):
            external_id = item.item.externalId
        
        return FeedbackItemSummary(
            item_id=item.itemId,
            external_id=external_id,
            initial_value=item.initialAnswerValue,
            final_value=item.finalAnswerValue,
            initial_explanation=item.initialCommentValue,
            final_explanation=item.finalCommentValue,
            edit_comment=item.editCommentValue
        )

    @staticmethod
    def _build_confusion_matrix(reference_values: List, predicted_values: List) -> Dict[str, Any]:
        """
        Build a confusion matrix from reference and predicted values.
        
        Args:
            reference_values: List of reference (ground truth) values (final values)
            predicted_values: List of predicted values (initial values)
            
        Returns:
            Dictionary representation of confusion matrix
        """
        # Get unique classes from both lists and ensure they are strings
        all_classes = sorted(list(set(str(v) for v in reference_values + predicted_values)))
        
        # Initialize matrix structure
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

    @staticmethod
    def _calculate_precision_recall(reference_values: List, predicted_values: List, classes: List[str]) -> Dict[str, float]:
        """
        Calculate precision and recall metrics.
        
        Args:
            reference_values: List of reference (ground truth) values
            predicted_values: List of predicted values
            classes: List of class labels
            
        Returns:
            Dictionary with precision and recall values
        """
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
            logger.warning(f"Error calculating precision/recall: {e}")
        
        return result

    @staticmethod
    def _analyze_feedback_items(feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """
        Analyze feedback items to produce summary statistics including confusion matrix,
        accuracy, AC1 agreement, precision/recall.
        
        Args:
            feedback_items: List of FeedbackItem objects to analyze
            
        Returns:
            Dictionary with analysis results including confusion matrix and metrics
        """
        if not feedback_items:
            return {
                "ac1": None,
                "accuracy": None,
                "total_items": 0,
                "agreements": 0,
                "disagreements": 0,
                "confusion_matrix": None,
                "precision": None,
                "recall": None,
                "class_distribution": [],
                "predicted_class_distribution": [],
                "warning": "No feedback items found"
            }
        
        # Extract valid pairs
        valid_pairs = []
        for item in feedback_items:
            if item.initialAnswerValue is not None and item.finalAnswerValue is not None:
                valid_pairs.append((item.initialAnswerValue, item.finalAnswerValue))
        
        if not valid_pairs:
            return {
                "ac1": None,
                "accuracy": None,
                "total_items": 0,
                "agreements": 0,
                "disagreements": 0,
                "confusion_matrix": None,
                "precision": None,
                "recall": None,
                "class_distribution": [],
                "predicted_class_distribution": [],
                "warning": "No valid feedback pairs found"
            }
        
        # Separate into lists for analysis
        # Final values are the "reference" (ground truth from human reviewers)
        # Initial values are the "predictions" (AI predictions being evaluated)
        initial_values = [pair[0] for pair in valid_pairs]  # AI predictions
        final_values = [pair[1] for pair in valid_pairs]    # Human corrections (ground truth)
        
        # Calculate basic statistics
        total_items = len(valid_pairs)
        agreements = sum(1 for i, f in valid_pairs if i == f)
        disagreements = total_items - agreements
        accuracy = (agreements / total_items * 100) if total_items > 0 else 0
        
        # Calculate distributions
        final_distribution = dict(Counter(final_values))
        initial_distribution = dict(Counter(initial_values))
        
        # Format distributions for visualization
        class_distribution = [
            {"label": str(label), "count": count}
            for label, count in final_distribution.items()
        ]
        class_distribution.sort(key=lambda x: x["count"], reverse=True)
        
        predicted_class_distribution = [
            {"label": str(label), "count": count}
            for label, count in initial_distribution.items()
        ]
        predicted_class_distribution.sort(key=lambda x: x["count"], reverse=True)
        
        # Build confusion matrix
        confusion_matrix = FeedbackService._build_confusion_matrix(final_values, initial_values)
        
        # Calculate precision and recall
        all_classes = list(final_distribution.keys())
        precision_recall = FeedbackService._calculate_precision_recall(final_values, initial_values, all_classes)
        
        # Calculate Gwet's AC1
        ac1_value = None
        try:
            gwet_ac1_calculator = GwetAC1()
            reference_list = [str(f) for f in final_values]
            predictions_list = [str(i) for i in initial_values]
            metric_input = Metric.Input(reference=reference_list, predictions=predictions_list)
            calculation_result = gwet_ac1_calculator.calculate(metric_input)
            ac1_value = calculation_result.value
        except Exception as e:
            logger.warning(f"Error calculating Gwet's AC1: {e}")
        
        # Generate warnings
        warnings = []
        if ac1_value is not None and ac1_value < 0:
            warnings.append("Systematic disagreement")
        elif ac1_value is not None and ac1_value == 0:
            warnings.append("Random chance agreement")
        
        if len(final_distribution) == 1:
            single_class = list(final_distribution.keys())[0]
            warnings.append(f"Single class ({single_class})")
        elif len(final_distribution) > 1:
            # Check for imbalanced distribution
            total = sum(final_distribution.values())
            expected_count = total / len(final_distribution)
            tolerance = 0.2  # 20% tolerance
            is_balanced = all(
                abs(count - expected_count) <= expected_count * tolerance 
                for count in final_distribution.values()
            )
            if not is_balanced:
                warnings.append("Imbalanced classes")
        
        warning = "; ".join(warnings) if warnings else None
        
        return {
            "ac1": ac1_value,
            "accuracy": accuracy,
            "total_items": total_items,
            "agreements": agreements,
            "disagreements": disagreements,
            "confusion_matrix": confusion_matrix,
            "precision": precision_recall.get("precision"),
            "recall": precision_recall.get("recall"),
            "class_distribution": class_distribution,
            "predicted_class_distribution": predicted_class_distribution,
            "warning": warning
        }

    @staticmethod
    def _generate_recommendation(analysis: Dict[str, Any]) -> str:
        """
        Generate a recommendation based on the analysis results.
        
        Args:
            analysis: Dictionary containing analysis results
            
        Returns:
            String recommendation for next steps
        """
        if analysis["total_items"] == 0:
            return "No feedback data available. No further analysis possible."
        
        accuracy = analysis.get("accuracy", 0)
        ac1 = analysis.get("ac1")
        warning = analysis.get("warning") or ""
        
        recommendations = []
        
        # Accuracy-based recommendations
        if accuracy < 70:
            recommendations.append("Low accuracy detected")
            if "Single class" in warning:
                recommendations.append("Use `find` to examine why predictions are all wrong")
            elif "Imbalanced" in warning:
                recommendations.append("Use `find` with specific value filters to examine false positives and negatives")
            else:
                recommendations.append("Use `find` to examine disagreement patterns")
        elif accuracy < 85:
            recommendations.append("Moderate accuracy - room for improvement")
            recommendations.append("Use `find` to examine specific error patterns")
        
        # AC1-based recommendations
        if ac1 is not None:
            if ac1 < 0:
                recommendations.append("Systematic disagreement requires immediate attention")
            elif ac1 < 0.4:
                recommendations.append("Poor agreement between AI and human reviewers")
            elif ac1 < 0.6:
                recommendations.append("Fair agreement - investigate borderline cases")
        
        # Warning-based recommendations
        if "Single class" in warning:
            recommendations.append("Examine why AI predictions lack diversity")
        elif "Imbalanced" in warning:
            recommendations.append("Focus on minority class prediction accuracy")
        
        if not recommendations:
            recommendations.append("Good performance - use `find` to examine edge cases for further improvement")
        
        return ". ".join(recommendations) + "."
    
    @staticmethod
    async def summarize_feedback(
        client,
        scorecard_name: str,
        score_name: str,
        scorecard_id: str,
        score_id: str,
        account_id: str,
        days: int
    ) -> FeedbackSummaryResult:
        """
        Generate a comprehensive feedback summary including confusion matrix, accuracy,
        AC1 agreement, and actionable recommendations.
        
        Args:
            client: The GraphQL client instance
            scorecard_name: Human-readable scorecard name
            score_name: Human-readable score name
            scorecard_id: The scorecard ID to filter by
            score_id: The score ID to filter by  
            account_id: The account ID to filter by
            days: Number of days back to search
            
        Returns:
            FeedbackSummaryResult with context, analysis, and recommendations
        """
        # Find all feedback items for the specified period
        feedback_items = await FeedbackService.find_feedback_items(
            client=client,
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=account_id,
            days=days,
            initial_value=None,
            final_value=None,
            limit=None,
            prioritize_edit_comments=False  # Get all items for comprehensive analysis
        )
        
        # Analyze the feedback items
        analysis = FeedbackService._analyze_feedback_items(feedback_items)
        
        # Generate actionable recommendation
        recommendation = FeedbackService._generate_recommendation(analysis)
        
        # Build context
        context = FeedbackSearchContext(
            scorecard_name=scorecard_name,
            score_name=score_name,
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=account_id,
            filters={"days": days},
            total_found=analysis["total_items"]
        )
        
        return FeedbackSummaryResult(
            context=context,
            analysis=analysis,
            recommendation=recommendation
        )

    @staticmethod
    def format_summary_result_as_dict(result: FeedbackSummaryResult) -> Dict[str, Any]:
        """
        Convert a FeedbackSummaryResult to a dictionary for JSON/YAML serialization.
        
        Args:
            result: The FeedbackSummaryResult to convert
            
        Returns:
            Dictionary representation suitable for JSON/YAML output
        """
        return {
            "context": {
                "scorecard_name": result.context.scorecard_name,
                "score_name": result.context.score_name,
                "scorecard_id": result.context.scorecard_id,
                "score_id": result.context.score_id,
                "account_id": result.context.account_id,
                "filters": result.context.filters,
                "total_found": result.context.total_found
            },
            "analysis": result.analysis,
            "recommendation": result.recommendation
        }
    
    @staticmethod
    def prioritize_feedback_with_edit_comments(
        feedback_items: List[FeedbackItem], 
        limit: Optional[int] = None,
        prioritize_edit_comments: bool = True
    ) -> List[FeedbackItem]:
        """
        Prioritize feedback items that have edit comments when applying a limit.
        
        Args:
            feedback_items: List of FeedbackItem objects
            limit: Maximum number of items to return (None for no limit)
            prioritize_edit_comments: Whether to prioritize items with edit comments
            
        Returns:
            List of prioritized and optionally limited feedback items
        """
        if not limit or len(feedback_items) <= limit:
            return feedback_items
        
        if not prioritize_edit_comments:
            # Just shuffle and return the limit
            items_copy = feedback_items.copy()
            random.shuffle(items_copy)
            return items_copy[:limit]
        
        # Separate items with and without edit comments
        items_with_comments = [item for item in feedback_items if item.editCommentValue]
        items_without_comments = [item for item in feedback_items if not item.editCommentValue]
        
        # Shuffle both groups for randomness when applying limits
        random.shuffle(items_with_comments)
        random.shuffle(items_without_comments)
        
        # Prioritize items with edit comments
        result = []
        
        # Add as many items with comments as possible
        comments_to_add = min(len(items_with_comments), limit)
        result.extend(items_with_comments[:comments_to_add])
        
        # Fill remaining slots with items without comments
        remaining_slots = limit - len(result)
        if remaining_slots > 0:
            result.extend(items_without_comments[:remaining_slots])
        
        return result
    
    @staticmethod
    async def find_feedback_items(
        client,
        scorecard_id: str,
        score_id: str,
        account_id: str,
        days: int,
        initial_value: Optional[str] = None,
        final_value: Optional[str] = None,
        limit: Optional[int] = None,
        prioritize_edit_comments: bool = True
    ) -> List[FeedbackItem]:
        """
        Find feedback items using the efficient GSI approach.
        
        Args:
            client: The GraphQL client instance
            scorecard_id: The scorecard ID to filter by
            score_id: The score ID to filter by  
            account_id: The account ID to filter by
            days: Number of days back to search
            initial_value: Optional filter for initial answer value
            final_value: Optional filter for final answer value
            limit: Optional limit on number of items to return
            prioritize_edit_comments: Whether to prioritize items with edit comments when limiting
            
        Returns:
            List of FeedbackItem objects matching the criteria
        """
        logger.info(f"Finding feedback items for scorecard {scorecard_id}, score {score_id}, last {days} days")
        
        try:
            # Calculate date range
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            end_date = datetime.now(timezone.utc)
            
            # Use the GSI query for efficient retrieval (same as reporting system)
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
                            description
                            text
                        }
                    }
                    nextToken
                }
            }
            """
            
            variables = {
                "accountId": account_id,
                "composite_sk_condition": {
                    "between": [
                        {
                            "scorecardId": scorecard_id,
                            "scoreId": score_id,
                            "updatedAt": start_date.isoformat()
                        },
                        {
                            "scorecardId": scorecard_id,
                            "scoreId": score_id,
                            "updatedAt": end_date.isoformat()
                        }
                    ]
                },
                "limit": 100,
                "nextToken": None,
                "sortDirection": "DESC"
            }
            
            # Handle pagination to get all items
            all_feedback_items = []
            next_token = None
            
            while True:
                if next_token:
                    variables["nextToken"] = next_token
                
                # Execute the query (async operation)
                response = await asyncio.to_thread(client.execute, query, variables)
                
                if 'errors' in response:
                    logger.error(f"GraphQL errors in GSI query: {response['errors']}")
                    # Fall back to the standard method if GSI fails
                    raise Exception(f"GSI query failed: {response['errors']}")
                
                result_data = response.get('listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt', {})
                items_data = result_data.get('items', [])
                
                # Convert to FeedbackItem objects
                batch_items = [FeedbackItem.from_dict(item_dict, client=client) for item_dict in items_data]
                all_feedback_items.extend(batch_items)
                
                logger.debug(f"Fetched {len(batch_items)} items (total: {len(all_feedback_items)})")
                
                # Check for more pages
                next_token = result_data.get('nextToken')
                if not next_token:
                    break
            
            logger.info(f"Retrieved {len(all_feedback_items)} feedback items from GSI")
            
        except Exception as e:
            logger.warning(f"GSI query failed, falling back to standard query: {str(e)}")
            
            # Fallback to the original method
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            filter_condition = {
                "and": [
                    {"accountId": {"eq": account_id}},
                    {"scorecardId": {"eq": scorecard_id}},
                    {"scoreId": {"eq": score_id}},
                    {"updatedAt": {"ge": cutoff_date}}
                ]
            }
            
            all_feedback_items, _ = FeedbackItem.list(
                client=client,
                limit=1000,  # Use a large limit to get all matching items
                filter=filter_condition,
                fields=FeedbackItem.GRAPHQL_BASE_FIELDS
            )
            
            logger.info(f"Retrieved {len(all_feedback_items)} feedback items from fallback query")
        
        # Apply value filters if specified
        if initial_value or final_value:
            filtered_items = []
            for item in all_feedback_items:
                matches = True
                if initial_value and item.initialAnswerValue != initial_value:
                    matches = False
                if final_value and item.finalAnswerValue != final_value:
                    matches = False
                if matches:
                    filtered_items.append(item)
            all_feedback_items = filtered_items
            logger.info(f"After value filtering: {len(all_feedback_items)} items")
        
        # Apply prioritization and limit if specified
        if limit:
            all_feedback_items = FeedbackService.prioritize_feedback_with_edit_comments(
                all_feedback_items, 
                limit=limit, 
                prioritize_edit_comments=prioritize_edit_comments
            )
            logger.info(f"After prioritization and limit: {len(all_feedback_items)} items")
        
        # Items are already sorted by the GSI query in DESC order
        logger.info(f"Final result: {len(all_feedback_items)} feedback items")
        return all_feedback_items
    
    @staticmethod
    async def search_feedback(
        client,
        scorecard_name: str,
        score_name: str,
        scorecard_id: str,
        score_id: str,
        account_id: str,
        days: int,
        initial_value: Optional[str] = None,
        final_value: Optional[str] = None,
        limit: Optional[int] = None,
        prioritize_edit_comments: bool = True
    ) -> FeedbackSearchResult:
        """
        High-level search method that returns a structured result with context.
        
        Args:
            client: The GraphQL client instance
            scorecard_name: Human-readable scorecard name
            score_name: Human-readable score name
            scorecard_id: The scorecard ID to filter by
            score_id: The score ID to filter by  
            account_id: The account ID to filter by
            days: Number of days back to search
            initial_value: Optional filter for initial answer value
            final_value: Optional filter for final answer value
            limit: Optional limit on number of items to return
            prioritize_edit_comments: Whether to prioritize items with edit comments when limiting
            
        Returns:
            FeedbackSearchResult with context and token-efficient summaries
        """
        # Find the feedback items
        feedback_items = await FeedbackService.find_feedback_items(
            client=client,
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=account_id,
            days=days,
            initial_value=initial_value,
            final_value=final_value,
            limit=limit,
            prioritize_edit_comments=prioritize_edit_comments
        )
        
        # Convert to token-efficient summaries
        summaries = [
            FeedbackService._convert_feedback_item_to_summary(item) 
            for item in feedback_items
        ]
        
        # Build context
        context = FeedbackSearchContext(
            scorecard_name=scorecard_name,
            score_name=score_name,
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=account_id,
            filters={
                "initial_value": initial_value,
                "final_value": final_value,
                "days": days,
                "limit": limit,
                "prioritize_edit_comments": prioritize_edit_comments
            },
            total_found=len(summaries)
        )
        
        return FeedbackSearchResult(context=context, feedback_items=summaries)
    
    @staticmethod
    def format_search_result_as_dict(result: FeedbackSearchResult) -> Dict[str, Any]:
        """
        Convert a FeedbackSearchResult to a dictionary for JSON/YAML serialization.
        
        Args:
            result: The FeedbackSearchResult to convert
            
        Returns:
            Dictionary representation suitable for JSON/YAML output
        """
        return {
            "context": {
                "scorecard_name": result.context.scorecard_name,
                "score_name": result.context.score_name,
                "scorecard_id": result.context.scorecard_id,
                "score_id": result.context.score_id,
                "account_id": result.context.account_id,
                "filters": result.context.filters,
                "total_found": result.context.total_found
            },
            "feedback_items": [
                {
                    "item_id": item.item_id,
                    "external_id": item.external_id,
                    "initial_value": item.initial_value,
                    "final_value": item.final_value,
                    "initial_explanation": item.initial_explanation,
                    "final_explanation": item.final_explanation,
                    "edit_comment": item.edit_comment
                }
                for item in result.feedback_items
            ]
        } 