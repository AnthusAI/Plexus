"""
Tests for Accuracy metric implementation.

This module tests the Accuracy class to ensure correct calculation
of accuracy values.
"""

import unittest
import math
from .accuracy import Accuracy
from .metric import Metric


class TestAccuracy(unittest.TestCase):
    """Test cases for the Accuracy class."""

    def setUp(self):
        """Set up the test environment."""
        self.accuracy = Accuracy()

    def test_perfect_accuracy(self):
        """Test with perfect agreement between predictions and reference."""
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
        """Test with partial agreement."""
        input_data = Metric.Input(
            reference=["Yes", "No", "Yes", "No", "Yes"],
            predictions=["Yes", "No", "No", "No", "Yes"]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertEqual(result.value, 0.8)  # 4/5 correct
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["matches"], 4)
        self.assertEqual(result.metadata["total"], 5)

    def test_zero_accuracy(self):
        """Test with no agreement at all."""
        input_data = Metric.Input(
            reference=["Yes", "Yes", "Yes"],
            predictions=["No", "No", "No"]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertEqual(result.value, 0.0)
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["matches"], 0)
        self.assertEqual(result.metadata["total"], 3)

    def test_empty_inputs(self):
        """Test with empty input lists."""
        input_data = Metric.Input(
            reference=[],
            predictions=[]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertTrue(math.isnan(result.value))
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

    def test_multiclass_data(self):
        """Test with multi-class data."""
        input_data = Metric.Input(
            reference=["A", "B", "C", "D", "E", "A", "B", "C", "D", "E"],
            predictions=["A", "B", "C", "D", "E", "B", "C", "D", "E", "A"]
        )
        result = self.accuracy.calculate(input_data)
        
        self.assertEqual(result.name, "Accuracy")
        self.assertEqual(result.value, 0.5)  # 5/10 correct
        self.assertEqual(result.range, [0.0, 1.0])
        self.assertEqual(result.metadata["matches"], 5)
        self.assertEqual(result.metadata["total"], 10)


if __name__ == "__main__":
    unittest.main() 