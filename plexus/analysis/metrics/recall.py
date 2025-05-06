"""
Recall metric implementation.

This module provides a recall metric that calculates
the ratio of true positives to all actual positive instances.
"""

from typing import List, Any
from .metric import Metric


class Recall(Metric):
    """
    Implementation of recall metric for binary classification tasks.
    
    Recall is calculated as the number of true positives divided by
    the total number of actual positive instances (true positives + false negatives).
    It represents the ability of a classifier to find all positive samples.
    
    For binary classification, labels must be strings like 'yes'/'no' or 'true'/'false'.
    The first label in self.positive_labels is considered the "positive" class.
    """
    
    def __init__(self, positive_labels=None):
        """
        Initialize the Recall metric with specified positive labels.
        
        Args:
            positive_labels: List of values to consider as positive class.
                If None, defaults to ['yes', 'true', '1', 1, True]
        """
        self.positive_labels = positive_labels or ['yes', 'true', '1', 1, True]
    
    def calculate(self, input_data: Metric.Input) -> Metric.Result:
        """
        Calculate recall between prediction and reference data.
        
        Args:
            input_data: Metric.Input containing reference and prediction lists
            
        Returns:
            Metric.Result with the recall value and metadata
        """
        if len(input_data.reference) == 0:
            return Metric.Result(
                name="Recall",
                value=float('nan'),
                range=[0.0, 1.0],
                metadata={"error": "Empty input lists"}
            )
            
        if len(input_data.reference) != len(input_data.predictions):
            raise ValueError("Input lists must be of the same length")
        
        # Standardize inputs to handle case and whitespace variations
        reference = [str(r).lower().strip() if r is not None else 'none' for r in input_data.reference]
        predictions = [str(p).lower().strip() if p is not None else 'none' for p in input_data.predictions]
        
        # Convert positive labels to lowercase strings for comparison
        positive_labels = [str(label).lower().strip() if label is not None else 'none' 
                          for label in self.positive_labels]
        
        # Count true positives and false negatives
        true_positives = sum(1 for r, p in zip(reference, predictions) 
                           if p in positive_labels and r in positive_labels)
        
        false_negatives = sum(1 for r, p in zip(reference, predictions) 
                            if r in positive_labels and p not in positive_labels)
        
        # Calculate recall
        if true_positives + false_negatives == 0:
            recall = 0.0  # No actual positives, recall is 0
        else:
            recall = true_positives / (true_positives + false_negatives)
        
        return Metric.Result(
            name="Recall",
            value=recall,
            range=[0.0, 1.0],
            metadata={
                "true_positives": true_positives,
                "false_negatives": false_negatives,
                "total_actual_positive": true_positives + false_negatives
            }
        ) 