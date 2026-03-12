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
        Calculate Gwet's AC1 agreement coefficient.
        
        Args:
            input_data: Metric.Input containing reference and prediction lists
        
        Returns:
            Metric.Result with the Gwet's AC1 value and metadata
        """
        rater1_ratings = input_data.reference
        rater2_ratings = input_data.predictions
        zero_division = 'warn'
        
        # Ensure inputs are the same length
        if len(rater1_ratings) != len(rater2_ratings):
            raise ValueError("Input lists must be of the same length")
        
        if len(rater1_ratings) == 0:
            if zero_division == 'warn':
                print("Warning: Empty input lists")
                return Metric.Result(
                    name="Gwet's AC1",
                    value=float('nan'),
                    range=[-1.0, 1.0]
                )
            elif zero_division == '0':
                ac1_value = 0.0
            else:  # 'nan'
                ac1_value = float('nan')
        else:
            # Convert ratings to a list of unique categories
            all_categories = sorted(list(set(rater1_ratings + rater2_ratings)))
            n_categories = len(all_categories)
            
            # If only one category exists, perfect agreement
            if n_categories <= 1:
                ac1_value = 1.0
            else:
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
                        ac1_value = float('nan')
                    elif zero_division == '0':
                        ac1_value = 0.0
                    else:  # 'nan'
                        ac1_value = float('nan')
                else:
                    ac1_value = (observed_agreement - pe) / denominator
        
        return Metric.Result(
            name="Gwet's AC1",
            value=ac1_value,
            range=[-1.0, 1.0]
        ) 