"""
Tests for the Precision metric implementation.

This module tests the Precision class using various test cases to ensure
the implementation is correct and robust.
"""

import unittest
import math
from .precision import Precision
from .metric import Metric


class TestPrecision(unittest.TestCase):
    """Test cases for the Precision class."""

    def setUp(self):
        """Set up the test environment."""
        self.precision = Precision()

    def test_perfect_precision(self):
        """Test with perfect precision (all positive predictions are correct)."""
        input_data = Metric.Input(
            reference=["yes", "no", "yes", "no", "yes"],
            predictions=["yes", "no", "yes", "no", "yes"]
        )
        result = self.precision.calculate(input_data)
        
        self.assertEqual(result.name, "Precision")
        self.assertEqual(result.value, 1.0)
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 3)
        self.assertEqual(result.metadata["false_positives"], 0)
        self.assertEqual(result.metadata["total_predicted_positive"], 3)

    def test_zero_precision(self):
        """Test with zero precision (all positive predictions are incorrect)."""
        input_data = Metric.Input(
            reference=["no", "no", "no", "no", "no"],
            predictions=["yes", "yes", "yes", "no", "no"]
        )
        result = self.precision.calculate(input_data)
        
        self.assertEqual(result.name, "Precision")
        self.assertEqual(result.value, 0.0)
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 0)
        self.assertEqual(result.metadata["false_positives"], 3)
        self.assertEqual(result.metadata["total_predicted_positive"], 3)

    def test_partial_precision(self):
        """Test with partial precision."""
        input_data = Metric.Input(
            reference=["yes", "no", "yes", "no", "yes"],
            predictions=["yes", "yes", "yes", "no", "yes"]
        )
        result = self.precision.calculate(input_data)
        
        self.assertEqual(result.name, "Precision")
        self.assertEqual(result.value, 0.75)  # 3 TP out of 4 positive predictions
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 3)
        self.assertEqual(result.metadata["false_positives"], 1)
        self.assertEqual(result.metadata["total_predicted_positive"], 4)

    def test_no_positive_predictions(self):
        """Test with no positive predictions."""
        input_data = Metric.Input(
            reference=["yes", "no", "yes", "no", "yes"],
            predictions=["no", "no", "no", "no", "no"]
        )
        result = self.precision.calculate(input_data)
        
        self.assertEqual(result.name, "Precision")
        self.assertEqual(result.value, 0.0)  # No positive predictions means precision is 0
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 0)
        self.assertEqual(result.metadata["false_positives"], 0)
        self.assertEqual(result.metadata["total_predicted_positive"], 0)

    def test_empty_inputs(self):
        """Test with empty input lists."""
        input_data = Metric.Input(
            reference=[],
            predictions=[]
        )
        result = self.precision.calculate(input_data)
        
        self.assertEqual(result.name, "Precision")
        self.assertTrue(math.isnan(result.value))  # Should be NaN
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertIn("error", result.metadata)

    def test_unequal_length_inputs(self):
        """Test with input lists of different lengths."""
        input_data = Metric.Input(
            reference=["yes", "no", "yes"],
            predictions=["yes", "no"]
        )
        
        with self.assertRaises(ValueError):
            self.precision.calculate(input_data)

    def test_custom_positive_labels(self):
        """Test with custom positive labels."""
        custom_precision = Precision(positive_labels=["true", 1])
        
        input_data = Metric.Input(
            reference=["true", "false", "true", "false", 1],
            predictions=["true", "true", "false", "false", 1]
        )
        result = custom_precision.calculate(input_data)
        
        self.assertEqual(result.name, "Precision")
        self.assertEqual(result.value, 0.6666666666666666)  # 2 TP out of 3 positive predictions
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 2)
        self.assertEqual(result.metadata["false_positives"], 1)
        self.assertEqual(result.metadata["total_predicted_positive"], 3)

    def test_case_insensitivity(self):
        """Test that the metric is case insensitive."""
        input_data = Metric.Input(
            reference=["YES", "no", "Yes", "NO", "yes"],
            predictions=["yes", "YES", "YES", "no", "Yes"]
        )
        result = self.precision.calculate(input_data)
        
        self.assertEqual(result.name, "Precision")
        self.assertEqual(result.value, 0.75)  # 3 TP out of 4 positive predictions
        self.assertEqual(result.metadata["true_positives"], 3)
        self.assertEqual(result.metadata["false_positives"], 1)
        self.assertEqual(result.metadata["total_predicted_positive"], 4)


if __name__ == "__main__":
    unittest.main() 