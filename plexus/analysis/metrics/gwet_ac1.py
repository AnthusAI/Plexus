"""
Implementation of Gwet's AC1 agreement coefficient.

This module provides the implementation of Gwet's AC1 statistic for measuring 
inter-rater agreement, which is more robust than Cohen's Kappa when dealing with
highly imbalanced class distributions.
"""

import numpy as np
from typing import List, Union, Optional

from .metric import Metric


class GwetAC1(Metric):
    """
    Implementation of Gwet's AC1 statistic for measuring inter-rater agreement.
    
    Gwet's AC1 is an alternative to Cohen's Kappa and Fleiss' Kappa that is more
    robust to the "Kappa paradox" where high observed agreement can result in low
    or negative Kappa values when there is high class imbalance.
    
    References:
    - Gwet, K. L. (2008). Computing inter-rater reliability and its variance in the
      presence of high agreement. British Journal of Mathematical and Statistical Psychology,
      61(1), 29-48.
    """
    
    def calculate(self, input_data: Metric.Input) -> Metric.Result:
        """
        Calculate Gwet's AC1 statistic for measuring agreement between two raters.
        
        Args:
            input_data: Metric.Input containing reference and prediction lists
            
        Returns:
            Metric.Result with the Gwet's AC1 value and metadata
        """
        ac1_value = self._calculate_ac1(
            input_data.reference,
            input_data.predictions,
            zero_division='warn'
        )
        
        return Metric.Result(
            name="Gwet's AC1",
            value=ac1_value,
            range=[-1.0, 1.0],
            metadata={
                "interpretation": {
                    "1.0": "Perfect agreement",
                    "0.0": "Agreement no better than chance",
                    "<0": "Agreement worse than chance (rare)"
                }
            }
        )
    
    @staticmethod
    def _calculate_ac1(
        rater1_ratings: List[str],
        rater2_ratings: List[str],
        zero_division: str = 'warn'
    ) -> float:
        """
        Internal method to calculate Gwet's AC1 statistic.
        
        Args:
            rater1_ratings: List of ratings from the first rater
            rater2_ratings: List of ratings from the second rater
            zero_division: How to handle division by zero ('warn', '0', or 'nan')
        
        Returns:
            The Gwet's AC1 value, ranging from -1 to 1 where:
            - 1: Perfect agreement
            - 0: Agreement is no better than chance
            - <0: Agreement is worse than chance (rare)
        """
        # Ensure inputs are the same length
        if len(rater1_ratings) != len(rater2_ratings):
            raise ValueError("Input lists must be of the same length")
        
        if len(rater1_ratings) == 0:
            if zero_division == 'warn':
                print("Warning: Empty input lists")
                return float('nan')
            elif zero_division == '0':
                return 0.0
            else:  # 'nan'
                return float('nan')
        
        # Convert ratings to a list of unique categories
        all_categories = sorted(list(set(rater1_ratings + rater2_ratings)))
        n_categories = len(all_categories)
        
        # If only one category exists, perfect agreement
        if n_categories <= 1:
            return 1.0
        
        # Create a mapping from category to index
        category_to_idx = {cat: idx for idx, cat in enumerate(all_categories)}
        
        # Convert ratings to indices
        rater1_indices = [category_to_idx[r] for r in rater1_ratings]
        rater2_indices = [category_to_idx[r] for r in rater2_ratings]
        
        # Count total number of items
        n_items = len(rater1_ratings)
        
        # Calculate observed agreement
        observed_agreement = sum(r1 == r2 for r1, r2 in zip(rater1_indices, rater2_indices)) / n_items
        
        # Calculate probability of chance agreement using Gwet's method
        # First, calculate the distribution of ratings across categories
        category_counts = np.zeros(n_categories)
        for r1, r2 in zip(rater1_indices, rater2_indices):
            category_counts[r1] += 1
            category_counts[r2] += 1
        
        # Average probability for each category
        pi_values = category_counts / (2 * n_items)
        
        # Calculate expected chance agreement using Gwet's formula
        # This is different from Cohen's/Fleiss' approach
        pe = sum(pi_values * (1 - pi_values)) / (n_categories - 1)
        
        # Calculate AC1
        denominator = 1 - pe
        
        if denominator == 0:
            if zero_division == 'warn':
                print("Warning: Division by zero in Gwet's AC1 calculation")
                return float('nan')
            elif zero_division == '0':
                return 0.0
            else:  # 'nan'
                return float('nan')
        
        ac1 = (observed_agreement - pe) / denominator
        
        return ac1 