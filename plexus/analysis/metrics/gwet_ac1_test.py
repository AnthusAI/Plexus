"""
Tests for Gwet's AC1 agreement coefficient implementation.

This module tests the GwetAC1 class using various test cases to ensure
the implementation is correct and robust.
"""

import unittest
import numpy as np
from .gwet_ac1 import GwetAC1
from .metric import Metric
import math


class TestGwetAC1(unittest.TestCase):
    """Test cases for the GwetAC1 class."""

    def setUp(self):
        """Set up the test environment."""
        self.gwet = GwetAC1()

    def test_perfect_agreement(self):
        """Test with perfect agreement between raters."""
        input_data = Metric.Input(
            reference=["Yes", "No", "Yes", "No", "Yes"],
            predictions=["Yes", "No", "Yes", "No", "Yes"]
        )
        result = self.gwet.calculate(input_data)
        
        self.assertEqual(result.name, "Gwet's AC1")
        self.assertEqual(result.value, 1.0)
        self.assertEqual(result.range, [-1.0, 1.0])

    def test_high_agreement(self):
        """Test with high but not perfect agreement."""
        input_data = Metric.Input(
            reference=["Yes", "No", "Yes", "No", "Yes"],
            predictions=["Yes", "No", "Yes", "No", "No"]
        )
        result = self.gwet.calculate(input_data)
        
        self.assertEqual(result.name, "Gwet's AC1")
        self.assertGreater(result.value, 0.5)  # High positive agreement
        self.assertLess(result.value, 1.0)     # But not perfect
        self.assertEqual(result.range, [-1.0, 1.0])

    def test_chance_agreement(self):
        """Test with agreement close to chance level."""
        # Create data where agreement is approximately at chance level
        # We'll use a specially constructed example that should result in AC1 near 0
        input_data = Metric.Input(
            reference=["A", "A", "B", "B", "C", "C"],
            predictions=["A", "C", "A", "C", "A", "B"]
        )
        result = self.gwet.calculate(input_data)
        
        self.assertEqual(result.name, "Gwet's AC1")
        # AC1 should be close to zero in this artificially constructed case
        self.assertAlmostEqual(result.value, 0.0, delta=0.3)
        self.assertEqual(result.range, [-1.0, 1.0])

    def test_negative_agreement(self):
        """Test with agreement worse than chance (negative AC1 value)."""
        # This is an extreme case designed to produce a negative AC1
        # It represents raters who systematically disagree
        input_data = Metric.Input(
            reference=["A", "A", "B", "B", "C", "C", "D", "D"],
            predictions=["B", "C", "A", "D", "D", "A", "C", "B"]
        )
        result = self.gwet.calculate(input_data)
        
        self.assertEqual(result.name, "Gwet's AC1")
        self.assertLess(result.value, 0.0)  # Should be negative
        self.assertEqual(result.range, [-1.0, 1.0])

    def test_single_category(self):
        """Test with only one category in the data."""
        input_data = Metric.Input(
            reference=["Yes", "Yes", "Yes", "Yes", "Yes"],
            predictions=["Yes", "Yes", "Yes", "Yes", "Yes"]
        )
        result = self.gwet.calculate(input_data)
        
        self.assertEqual(result.name, "Gwet's AC1")
        self.assertEqual(result.value, 1.0)  # Perfect agreement
        self.assertEqual(result.range, [-1.0, 1.0])

    def test_empty_inputs(self):
        """Test with empty input lists."""
        input_data = Metric.Input(
            reference=[],
            predictions=[]
        )
        result = self.gwet.calculate(input_data)
        
        self.assertEqual(result.name, "Gwet's AC1")
        self.assertTrue(math.isnan(result.value))  # Should be NaN
        self.assertEqual(result.range, [-1.0, 1.0])

    def test_unequal_length_inputs(self):
        """Test with input lists of different lengths."""
        input_data = Metric.Input(
            reference=["Yes", "No", "Yes"],
            predictions=["Yes", "No"]
        )
        
        with self.assertRaises(ValueError):
            self.gwet.calculate(input_data)

    def test_binary_imbalanced_data(self):
        """Test with highly imbalanced binary data where Kappa would have issues."""
        # Create data with high class imbalance where Cohen's Kappa typically fails
        input_data = Metric.Input(
            reference=["Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "No"],
            predictions=["Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "No", "No"]
        )
        result = self.gwet.calculate(input_data)
        
        self.assertEqual(result.name, "Gwet's AC1")
        # AC1 should still give high agreement despite imbalance
        self.assertGreater(result.value, 0.7)
        self.assertEqual(result.range, [-1.0, 1.0])

    def test_multiclass_data(self):
        """Test with multi-class data."""
        input_data = Metric.Input(
            reference=["A", "B", "C", "D", "E", "A", "B", "C", "D", "E"],
            predictions=["A", "B", "C", "D", "E", "A", "B", "D", "D", "C"]
        )
        result = self.gwet.calculate(input_data)
        
        self.assertEqual(result.name, "Gwet's AC1")
        # 7/10 agreements with 5 categories
        self.assertTrue(0 < result.value < 1)
        self.assertEqual(result.range, [-1.0, 1.0])


if __name__ == "__main__":
    unittest.main() 