"""
Core feedback analysis functionality for analyzing feedback items.

This module provides reusable functions for analyzing feedback items to calculate
metrics like accuracy, Gwet's AC1 agreement, confusion matrix, precision, and recall.

This code is shared between:
- FeedbackAnalysis report block
- Feedback evaluation type
- CLI feedback analysis tools
"""

import logging
from typing import List, Dict, Any, Optional
from collections import Counter
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric

logger = logging.getLogger(__name__)


def analyze_feedback_items(
    feedback_items: List[FeedbackItem],
    score_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze feedback items to produce summary statistics including confusion matrix,
    accuracy, AC1 agreement, precision/recall.
    
    This is the core feedback analysis function that should be used by all components
    that need to analyze feedback data.
    
    Args:
        feedback_items: List of FeedbackItem objects to analyze
        score_id: Optional score ID for logging purposes
        
    Returns:
        Dictionary with analysis results including:
        - ac1: Gwet's AC1 agreement coefficient (float or None)
        - accuracy: Accuracy percentage (float or None)
        - total_items: Number of valid feedback pairs (int)
        - agreements: Number of agreements (int)
        - disagreements: Number of disagreements (int)
        - confusion_matrix: Confusion matrix data structure
        - precision: Precision percentage (float or None)
        - recall: Recall percentage (float or None)
        - class_distribution: List of dicts with label and count
        - predicted_class_distribution: List of dicts with label and count
        - warning: Warning message if applicable (str or None)
    """
    score_info = f"score {score_id}" if score_id else "feedback items"
    logger.debug(f"Analyzing {len(feedback_items)} feedback items for {score_info}")
    
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
    
    # Extract valid pairs (both initial and final values must be non-None)
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
    confusion_matrix = build_confusion_matrix(final_values, initial_values)
    
    # Calculate precision and recall
    all_classes = list(final_distribution.keys())
    precision_recall = calculate_precision_recall(final_values, initial_values, all_classes)
    
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
        logger.warning(f"Error calculating Gwet's AC1 for {score_info}: {e}")
    
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


def build_confusion_matrix(
    reference_values: List,
    predicted_values: List
) -> Dict[str, Any]:
    """
    Build a confusion matrix from reference and predicted values.
    
    Args:
        reference_values: List of reference (ground truth) values
        predicted_values: List of predicted values
        
    Returns:
        Dictionary representation of confusion matrix with:
        - labels: List of class labels
        - matrix: List of row objects with actualClassLabel and predictedClassCounts
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


def calculate_precision_recall(
    reference_values: List,
    predicted_values: List,
    classes: List[str]
) -> Dict[str, Optional[float]]:
    """
    Calculate precision and recall metrics.
    
    Args:
        reference_values: List of reference (ground truth) values
        predicted_values: List of predicted values
        classes: List of class labels
        
    Returns:
        Dictionary with precision and recall percentages (or None if cannot be calculated)
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


def generate_recommendation(analysis: Dict[str, Any]) -> str:
    """
    Generate actionable recommendations based on feedback analysis.
    
    Args:
        analysis: Dictionary containing analysis results
        
    Returns:
        String with actionable recommendations
    """
    recommendations = []
    
    ac1 = analysis.get("ac1")
    accuracy = analysis.get("accuracy")
    total_items = analysis.get("total_items", 0)
    
    # Check sample size
    if total_items < 20:
        recommendations.append(
            f"⚠️ Limited data: Only {total_items} feedback items. "
            "Collect more feedback for statistically significant results."
        )
    
    # Check AC1 agreement
    if ac1 is not None:
        if ac1 < 0.4:
            recommendations.append(
                f"🔴 Critical: AC1 score of {ac1:.2f} indicates poor agreement. "
                "Review score criteria and consider retraining or redesigning the score."
            )
        elif ac1 < 0.6:
            recommendations.append(
                f"🟡 Warning: AC1 score of {ac1:.2f} shows moderate agreement. "
                "Review mismatched cases and refine score guidelines."
            )
        elif ac1 < 0.8:
            recommendations.append(
                f"🟢 Good: AC1 score of {ac1:.2f} shows substantial agreement. "
                "Minor refinements may improve performance."
            )
        else:
            recommendations.append(
                f"✅ Excellent: AC1 score of {ac1:.2f} indicates strong agreement. "
                "Score is performing well."
            )
    
    # Check accuracy
    if accuracy is not None:
        if accuracy < 70:
            recommendations.append(
                f"Accuracy is {accuracy:.1f}%. Review false positives and false negatives "
                "in the confusion matrix to identify patterns."
            )
    
    # Check for class imbalance
    warning = analysis.get("warning", "")
    if "Imbalanced classes" in warning:
        recommendations.append(
            "Class imbalance detected. Consider collecting more diverse feedback "
            "or adjusting score thresholds."
        )
    
    if not recommendations:
        recommendations.append("No specific recommendations. Continue monitoring feedback.")
    
    return "\n\n".join(recommendations)


