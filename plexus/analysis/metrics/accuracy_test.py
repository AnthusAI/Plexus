"""
Tests for the Accuracy metric implementation.

This module tests the Accuracy class using various test cases to ensure
the implementation is correct and robust.
"""

import unittest
import numpy as np
import math
from .accuracy import Accuracy
from .metric import Metric


class TestAccuracy(unittest.TestCase):
    """Test cases for the Accuracy class."""

    def setUp(self):
        """Set up the test environment."""
        self.accuracy = Accuracy()

    def test_perfect_accuracy(self):
        """Test with perfect accuracy between predictions and references."""
        input_data = Metric.Input(
            reference=["Yes", "No", "Yes", "No", "Yes"],
            predictions=["Yes", "No", "Yes", "No", "Yes"]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertEqual(result.value, 1.0)
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["matches"], 5)
        self.assertEqual(result.metadata["total"], 5)

    def test_partial_accuracy(self):
        """Test with partial accuracy."""
        input_data = Metric.Input(
            reference=["Yes", "No", "Yes", "No", "Yes"],
            predictions=["Yes", "No", "No", "No", "Yes"]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertEqual(result.value, 0.8)  # 4 out of 5 correct
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["matches"], 4)
        self.assertEqual(result.metadata["total"], 5)

    def test_zero_accuracy(self):
        """Test with zero accuracy."""
        input_data = Metric.Input(
            reference=["Yes", "No", "Yes", "No", "Yes"],
            predictions=["No", "Yes", "No", "Yes", "No"]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertEqual(result.value, 0.0)
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["matches"], 0)
        self.assertEqual(result.metadata["total"], 5)

    def test_empty_inputs(self):
        """Test with empty input lists."""
        input_data = Metric.Input(
            reference=[],
            predictions=[]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertTrue(math.isnan(result.value))  # Should be NaN
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertIn("error", result.metadata)

    def test_unequal_length_inputs(self):
        """Test with input lists of different lengths."""
        input_data = Metric.Input(
            reference=["Yes", "No", "Yes"],
            predictions=["Yes", "No"]
        )
        
        with self.assertRaises(ValueError):
            self.accuracy.calculate(input_data)

    def test_mixed_types(self):
        """Test with mixed data types."""
        input_data = Metric.Input(
            reference=["Yes", 1, True, None, 3.14],
            predictions=["Yes", 1, True, None, 3.14]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertEqual(result.value, 1.0)  # All match
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["matches"], 5)
        self.assertEqual(result.metadata["total"], 5)


if __name__ == "__main__":
    unittest.main() 