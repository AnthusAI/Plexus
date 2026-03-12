"""
Tests for the Recall metric implementation.

This module tests the Recall class using various test cases to ensure
the implementation is correct and robust.
"""

import unittest
import math
from .recall import Recall
from .metric import Metric


class TestRecall(unittest.TestCase):
    """Test cases for the Recall class."""

    def setUp(self):
        """Set up the test environment."""
        self.recall = Recall()

    def test_perfect_recall(self):
        """Test with perfect recall (all actual positives are correctly identified)."""
        input_data = Metric.Input(
            reference=["yes", "no", "yes", "no", "yes"],
            predictions=["yes", "no", "yes", "no", "yes"]
        )
        result = self.recall.calculate(input_data)
        
        self.assertEqual(result.name, "Recall")
        self.assertEqual(result.value, 1.0)
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 3)
        self.assertEqual(result.metadata["false_negatives"], 0)
        self.assertEqual(result.metadata["total_actual_positive"], 3)

    def test_zero_recall(self):
        """Test with zero recall (no actual positives are correctly identified)."""
        input_data = Metric.Input(
            reference=["yes", "yes", "yes", "no", "no"],
            predictions=["no", "no", "no", "no", "no"]
        )
        result = self.recall.calculate(input_data)
        
        self.assertEqual(result.name, "Recall")
        self.assertEqual(result.value, 0.0)
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 0)
        self.assertEqual(result.metadata["false_negatives"], 3)
        self.assertEqual(result.metadata["total_actual_positive"], 3)

    def test_partial_recall(self):
        """Test with partial recall."""
        input_data = Metric.Input(
            reference=["yes", "no", "yes", "no", "yes"],
            predictions=["yes", "no", "no", "no", "yes"]
        )
        result = self.recall.calculate(input_data)
        
        self.assertEqual(result.name, "Recall")
        self.assertEqual(result.value, 0.6666666666666666)  # 2 TP out of 3 actual positives
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 2)
        self.assertEqual(result.metadata["false_negatives"], 1)
        self.assertEqual(result.metadata["total_actual_positive"], 3)

    def test_no_actual_positives(self):
        """Test with no actual positive instances."""
        input_data = Metric.Input(
            reference=["no", "no", "no", "no", "no"],
            predictions=["yes", "no", "yes", "no", "yes"]
        )
        result = self.recall.calculate(input_data)
        
        self.assertEqual(result.name, "Recall")
        self.assertEqual(result.value, 0.0)  # No actual positives, recall is 0
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 0)
        self.assertEqual(result.metadata["false_negatives"], 0)
        self.assertEqual(result.metadata["total_actual_positive"], 0)

    def test_empty_inputs(self):
        """Test with empty input lists."""
        input_data = Metric.Input(
            reference=[],
            predictions=[]
        )
        result = self.recall.calculate(input_data)
        
        self.assertEqual(result.name, "Recall")
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
            self.recall.calculate(input_data)

    def test_custom_positive_labels(self):
        """Test with custom positive labels."""
        custom_recall = Recall(positive_labels=["true", 1])
        
        input_data = Metric.Input(
            reference=["true", "false", "true", "false", 1],
            predictions=["true", "false", "false", "false", 1]
        )
        result = custom_recall.calculate(input_data)
        
        self.assertEqual(result.name, "Recall")
        self.assertEqual(result.value, 0.6666666666666666)  # 2 TP out of 3 actual positives
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["true_positives"], 2)
        self.assertEqual(result.metadata["false_negatives"], 1)
        self.assertEqual(result.metadata["total_actual_positive"], 3)

    def test_case_insensitivity(self):
        """Test that the metric is case insensitive."""
        input_data = Metric.Input(
            reference=["YES", "no", "Yes", "NO", "yes"],
            predictions=["yes", "no", "no", "no", "YES"]
        )
        result = self.recall.calculate(input_data)
        
        self.assertEqual(result.name, "Recall")
        self.assertEqual(result.value, 0.6666666666666666)  # 2 TP out of 3 actual positives
        self.assertEqual(result.metadata["true_positives"], 2)
        self.assertEqual(result.metadata["false_negatives"], 1)
        self.assertEqual(result.metadata["total_actual_positive"], 3)


if __name__ == "__main__":
    unittest.main() 