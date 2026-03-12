"""
Accuracy metric implementation.

This module provides a simple accuracy metric that calculates
the percentage of exact matches between predictions and reference values.
"""

from typing import List, Any
from .metric import Metric


class Accuracy(Metric):
    """
    Implementation of accuracy metric for classification tasks.
    
    Accuracy is calculated as the number of correct predictions divided by
    the total number of predictions, expressed as a value between 0 and 1.
    """
    
    def calculate(self, input_data: Metric.Input) -> Metric.Result:
        """
        Calculate accuracy between prediction and reference data.
        
        Args:
            input_data: Metric.Input containing reference and prediction lists
            
        Returns:
            Metric.Result with the accuracy value and metadata
        """
        if len(input_data.reference) == 0:
            return Metric.Result(
                name="Accuracy",
                value=float('nan'),
                range=[0.0, 1.0],
                metadata={"error": "Empty input lists"}
            )
            
        if len(input_data.reference) != len(input_data.predictions):
            raise ValueError("Input lists must be of the same length")
        
        # Count matches
        matches = sum(r == p for r, p in zip(input_data.reference, input_data.predictions))
        
        # Calculate accuracy
        accuracy = matches / len(input_data.reference)
        
        return Metric.Result(
            name="Accuracy",
            value=accuracy,
            range=[0.0, 1.0],
            metadata={
                "matches": matches,
                "total": len(input_data.reference)
            }
        ) 