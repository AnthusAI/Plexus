"""
Tests for the feedback_analyzer module.
"""

import pytest
from unittest.mock import MagicMock
from plexus.analysis.feedback_analyzer import (
    analyze_feedback_items,
    build_confusion_matrix,
    calculate_precision_recall,
    generate_recommendation
)
from plexus.dashboard.api.models.feedback_item import FeedbackItem


@pytest.fixture
def mock_feedback_items():
    """Create mock feedback items for testing."""
    items = []
    
    # Create 10 items - 7 agreements, 3 disagreements (70% accuracy)
    for i in range(10):
        is_mismatch = i < 3  # 3 out of 10 are mismatches
        item = MagicMock(spec=FeedbackItem)
        item.id = f"item-{i}"
        item.initialAnswerValue = "Yes" if is_mismatch else "No"
        item.finalAnswerValue = "No"  # All final values are "No"
        items.append(item)
    
    return items


@pytest.fixture
def empty_feedback_items():
    """Create empty list of feedback items."""
    return []


@pytest.fixture
def invalid_feedback_items():
    """Create feedback items with None values."""
    items = []
    for i in range(5):
        item = MagicMock(spec=FeedbackItem)
        item.id = f"item-{i}"
        item.initialAnswerValue = None
        item.finalAnswerValue = None
        items.append(item)
    return items


class TestAnalyzeFeedbackItems:
    """Tests for analyze_feedback_items function."""
    
    def test_analyze_with_valid_items(self, mock_feedback_items):
        """Test analyzing feedback items with valid data."""
        result = analyze_feedback_items(mock_feedback_items, score_id="test-score")
        
        assert result is not None
        assert result["total_items"] == 10
        assert result["agreements"] == 7
        assert result["disagreements"] == 3
        assert result["accuracy"] == 70.0
        assert result["ac1"] is not None
        assert isinstance(result["ac1"], float)
        assert result["confusion_matrix"] is not None
        assert result["precision"] is not None
        assert result["recall"] is not None
        assert len(result["class_distribution"]) > 0
        assert len(result["predicted_class_distribution"]) > 0
    
    def test_analyze_with_empty_items(self, empty_feedback_items):
        """Test analyzing with no feedback items."""
        result = analyze_feedback_items(empty_feedback_items)
        
        assert result is not None
        assert result["total_items"] == 0
        assert result["agreements"] == 0
        assert result["disagreements"] == 0
        assert result["accuracy"] is None
        assert result["ac1"] is None
        assert result["confusion_matrix"] is None
        assert result["warning"] == "No feedback items found"
    
    def test_analyze_with_invalid_items(self, invalid_feedback_items):
        """Test analyzing with items that have None values."""
        result = analyze_feedback_items(invalid_feedback_items)
        
        assert result is not None
        assert result["total_items"] == 0
        assert result["warning"] == "No valid feedback pairs found"
    
    def test_analyze_perfect_agreement(self):
        """Test analyzing with perfect agreement."""
        items = []
        for i in range(5):
            item = MagicMock(spec=FeedbackItem)
            item.id = f"item-{i}"
            item.initialAnswerValue = "Yes"
            item.finalAnswerValue = "Yes"
            items.append(item)
        
        result = analyze_feedback_items(items)
        
        assert result["total_items"] == 5
        assert result["agreements"] == 5
        assert result["disagreements"] == 0
        assert result["accuracy"] == 100.0
        assert result["ac1"] is not None
    
    def test_analyze_multiclass(self):
        """Test analyzing with multiple classes."""
        items = []
        classes = ["Low", "Medium", "High"]
        
        for i in range(15):
            item = MagicMock(spec=FeedbackItem)
            item.id = f"item-{i}"
            # Distribute across classes
            initial_class = classes[i % 3]
            final_class = classes[(i + 1) % 3]  # Some mismatches
            item.initialAnswerValue = initial_class
            item.finalAnswerValue = final_class
            items.append(item)
        
        result = analyze_feedback_items(items)
        
        assert result["total_items"] == 15
        assert len(result["class_distribution"]) == 3
        assert len(result["predicted_class_distribution"]) == 3
        assert result["confusion_matrix"] is not None
        assert len(result["confusion_matrix"]["labels"]) == 3


class TestBuildConfusionMatrix:
    """Tests for build_confusion_matrix function."""
    
    def test_binary_confusion_matrix(self):
        """Test building confusion matrix for binary classification."""
        reference = ["Yes", "Yes", "No", "No", "Yes"]
        predicted = ["Yes", "No", "No", "No", "Yes"]
        
        result = build_confusion_matrix(reference, predicted)
        
        assert result is not None
        assert "labels" in result
        assert "matrix" in result
        assert len(result["labels"]) == 2
        assert len(result["matrix"]) == 2
        
        # Check structure
        for row in result["matrix"]:
            assert "actualClassLabel" in row
            assert "predictedClassCounts" in row
            assert isinstance(row["predictedClassCounts"], dict)
    
    def test_multiclass_confusion_matrix(self):
        """Test building confusion matrix for multiclass classification."""
        reference = ["A", "B", "C", "A", "B", "C"]
        predicted = ["A", "B", "A", "A", "C", "C"]
        
        result = build_confusion_matrix(reference, predicted)
        
        assert result is not None
        assert len(result["labels"]) == 3
        assert len(result["matrix"]) == 3
        
        # Verify counts
        total_count = sum(
            sum(row["predictedClassCounts"].values())
            for row in result["matrix"]
        )
        assert total_count == 6


class TestCalculatePrecisionRecall:
    """Tests for calculate_precision_recall function."""
    
    def test_binary_precision_recall(self):
        """Test precision and recall for binary classification."""
        reference = ["Yes", "Yes", "No", "No", "Yes"]
        predicted = ["Yes", "No", "No", "No", "Yes"]
        classes = ["Yes", "No"]
        
        result = calculate_precision_recall(reference, predicted, classes)
        
        assert result is not None
        assert "precision" in result
        assert "recall" in result
        assert result["precision"] is not None
        assert result["recall"] is not None
        assert 0 <= result["precision"] <= 100
        assert 0 <= result["recall"] <= 100
    
    def test_multiclass_precision_recall(self):
        """Test precision and recall for multiclass classification."""
        reference = ["A", "B", "C", "A", "B", "C"]
        predicted = ["A", "B", "A", "A", "C", "C"]
        classes = ["A", "B", "C"]
        
        result = calculate_precision_recall(reference, predicted, classes)
        
        assert result is not None
        assert result["precision"] is not None
        assert result["recall"] is not None
        assert 0 <= result["precision"] <= 100
        assert 0 <= result["recall"] <= 100
    
    def test_perfect_precision_recall(self):
        """Test precision and recall with perfect predictions."""
        reference = ["Yes", "No", "Yes", "No"]
        predicted = ["Yes", "No", "Yes", "No"]
        classes = ["Yes", "No"]
        
        result = calculate_precision_recall(reference, predicted, classes)
        
        assert result["precision"] == 100.0
        assert result["recall"] == 100.0


class TestGenerateRecommendation:
    """Tests for generate_recommendation function."""
    
    def test_recommendation_low_ac1(self):
        """Test recommendation with low AC1 score."""
        analysis = {
            "ac1": 0.3,
            "accuracy": 60.0,
            "total_items": 50,
            "warning": ""
        }
        
        result = generate_recommendation(analysis)
        
        assert result is not None
        assert "Critical" in result or "🔴" in result
        assert "0.3" in result or "0.30" in result
    
    def test_recommendation_good_ac1(self):
        """Test recommendation with good AC1 score."""
        analysis = {
            "ac1": 0.85,
            "accuracy": 90.0,
            "total_items": 100,
            "warning": ""
        }
        
        result = generate_recommendation(analysis)
        
        assert result is not None
        assert "Excellent" in result or "✅" in result
    
    def test_recommendation_limited_data(self):
        """Test recommendation with limited data."""
        analysis = {
            "ac1": 0.7,
            "accuracy": 80.0,
            "total_items": 10,
            "warning": ""
        }
        
        result = generate_recommendation(analysis)
        
        assert result is not None
        assert "Limited data" in result or "10" in result
    
    def test_recommendation_class_imbalance(self):
        """Test recommendation with class imbalance."""
        analysis = {
            "ac1": 0.75,
            "accuracy": 85.0,
            "total_items": 50,
            "warning": "Imbalanced classes"
        }
        
        result = generate_recommendation(analysis)
        
        assert result is not None
        assert "imbalance" in result.lower()


