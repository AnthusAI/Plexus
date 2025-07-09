"""
Tests for the FeedbackService.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

from plexus.cli.feedback.feedback_service import (
    FeedbackService, 
    FeedbackItemSummary,
    FeedbackSearchContext,
    FeedbackSearchResult,
    FeedbackSummaryResult
)
from plexus.dashboard.api.models.feedback_item import FeedbackItem


class TestFeedbackItemSummary:
    """Test the FeedbackItemSummary dataclass."""
    
    def test_feedback_item_summary_creation(self):
        """Test creating a FeedbackItemSummary with all fields."""
        summary = FeedbackItemSummary(
            item_id="item123",
            initial_value="No",
            final_value="Yes", 
            initial_explanation="AI thought this was negative",
            final_explanation="Actually this is positive",
            edit_comment="Changed due to context"
        )
        
        assert summary.item_id == "item123"
        assert summary.initial_value == "No"
        assert summary.final_value == "Yes"
        assert summary.initial_explanation == "AI thought this was negative"
        assert summary.final_explanation == "Actually this is positive"
        assert summary.edit_comment == "Changed due to context"
    
    def test_feedback_item_summary_with_none_values(self):
        """Test creating a FeedbackItemSummary with None values."""
        summary = FeedbackItemSummary(
            item_id="item123",
            initial_value=None,
            final_value=None,
            initial_explanation=None,
            final_explanation=None,
            edit_comment=None
        )
        
        assert summary.item_id == "item123"
        assert summary.initial_value is None
        assert summary.final_value is None
        assert summary.initial_explanation is None
        assert summary.final_explanation is None
        assert summary.edit_comment is None


class TestFeedbackSearchContext:
    """Test the FeedbackSearchContext dataclass."""
    
    def test_feedback_search_context_creation(self):
        """Test creating a FeedbackSearchContext."""
        context = FeedbackSearchContext(
            scorecard_name="Test Scorecard",
            score_name="Test Score",
            scorecard_id="sc123",
            score_id="score123",
            account_id="acc123",
            filters={"days": 7, "limit": 10},
            total_found=5
        )
        
        assert context.scorecard_name == "Test Scorecard"
        assert context.score_name == "Test Score"
        assert context.scorecard_id == "sc123"
        assert context.score_id == "score123"
        assert context.account_id == "acc123"
        assert context.filters == {"days": 7, "limit": 10}
        assert context.total_found == 5


class TestFeedbackSearchResult:
    """Test the FeedbackSearchResult dataclass."""
    
    def test_feedback_search_result_creation(self):
        """Test creating a FeedbackSearchResult."""
        context = FeedbackSearchContext(
            scorecard_name="Test Scorecard",
            score_name="Test Score", 
            scorecard_id="sc123",
            score_id="score123",
            account_id="acc123",
            filters={"days": 7},
            total_found=1
        )
        
        items = [FeedbackItemSummary(
            item_id="item123",
            initial_value="No",
            final_value="Yes",
            initial_explanation="Initial explanation",
            final_explanation="Final explanation", 
            edit_comment="Edit comment"
        )]
        
        result = FeedbackSearchResult(context=context, feedback_items=items)
        
        assert result.context == context
        assert len(result.feedback_items) == 1
        assert result.feedback_items[0].item_id == "item123"


class TestFeedbackService:
    """Test suite for FeedbackService functionality."""
    
    def test_convert_feedback_item_to_summary(self):
        """Test conversion of FeedbackItem to summary format."""
        # Create mock feedback item
        feedback_item = Mock(spec=FeedbackItem)
        feedback_item.itemId = "test-item-123"
        feedback_item.initialAnswerValue = "No"
        feedback_item.finalAnswerValue = "Yes"
        feedback_item.initialCommentValue = "Initial explanation"
        feedback_item.finalCommentValue = "Final explanation"
        feedback_item.editCommentValue = "Human correction comment"
        
        # Convert to summary
        summary = FeedbackService._convert_feedback_item_to_summary(feedback_item)
        
        # Verify conversion
        assert isinstance(summary, FeedbackItemSummary)
        assert summary.item_id == "test-item-123"
        assert summary.initial_value == "No"
        assert summary.final_value == "Yes"
        assert summary.initial_explanation == "Initial explanation"
        assert summary.final_explanation == "Final explanation"
        assert summary.edit_comment == "Human correction comment"
    
    def test_build_confusion_matrix_binary(self):
        """Test confusion matrix building for binary classification."""
        reference_values = ["Yes", "No", "Yes", "No", "Yes"]
        predicted_values = ["Yes", "Yes", "No", "No", "Yes"]
        
        result = FeedbackService._build_confusion_matrix(reference_values, predicted_values)
        
        # Verify structure
        assert "labels" in result
        assert "matrix" in result
        assert set(result["labels"]) == {"Yes", "No"}
        
        # Find the matrix rows
        yes_row = next(row for row in result["matrix"] if row["actualClassLabel"] == "Yes")
        no_row = next(row for row in result["matrix"] if row["actualClassLabel"] == "No")
        
        # Verify confusion matrix values
        # Yes->Yes: 2, Yes->No: 1
        assert yes_row["predictedClassCounts"]["Yes"] == 2
        assert yes_row["predictedClassCounts"]["No"] == 1
        
        # No->Yes: 1, No->No: 1
        assert no_row["predictedClassCounts"]["Yes"] == 1
        assert no_row["predictedClassCounts"]["No"] == 1
    
    def test_build_confusion_matrix_multiclass(self):
        """Test confusion matrix building for multiclass classification."""
        reference_values = ["A", "B", "C", "A", "B"]
        predicted_values = ["A", "A", "C", "B", "B"]
        
        result = FeedbackService._build_confusion_matrix(reference_values, predicted_values)
        
        # Verify structure
        assert set(result["labels"]) == {"A", "B", "C"}
        assert len(result["matrix"]) == 3
        
        # Find specific matrix values
        a_row = next(row for row in result["matrix"] if row["actualClassLabel"] == "A")
        b_row = next(row for row in result["matrix"] if row["actualClassLabel"] == "B")
        c_row = next(row for row in result["matrix"] if row["actualClassLabel"] == "C")
        
        # A actual: A->A=1, A->B=1, A->C=0
        assert a_row["predictedClassCounts"]["A"] == 1
        assert a_row["predictedClassCounts"]["B"] == 1
        assert a_row["predictedClassCounts"]["C"] == 0
        
        # B actual: B->A=1, B->B=1, B->C=0
        assert b_row["predictedClassCounts"]["A"] == 1
        assert b_row["predictedClassCounts"]["B"] == 1
        assert b_row["predictedClassCounts"]["C"] == 0
        
        # C actual: C->A=0, C->B=0, C->C=1
        assert c_row["predictedClassCounts"]["A"] == 0
        assert c_row["predictedClassCounts"]["B"] == 0
        assert c_row["predictedClassCounts"]["C"] == 1
    
    def test_calculate_precision_recall_binary(self):
        """Test precision and recall calculation for binary classification."""
        reference_values = ["Positive", "Negative", "Positive", "Negative", "Positive"]
        predicted_values = ["Positive", "Positive", "Negative", "Negative", "Positive"]
        classes = ["Positive", "Negative"]
        
        result = FeedbackService._calculate_precision_recall(reference_values, predicted_values, classes)
        
        # For "Positive" class:
        # TP=2 (correctly predicted positive), FP=1 (false positive), FN=1 (false negative)
        # Precision = TP/(TP+FP) = 2/3 = 66.67%
        # Recall = TP/(TP+FN) = 2/3 = 66.67%
        
        assert "precision" in result
        assert "recall" in result
        assert abs(result["precision"] - 66.67) < 0.1
        assert abs(result["recall"] - 66.67) < 0.1
    
    def test_analyze_feedback_items_empty(self):
        """Test analysis with no feedback items."""
        result = FeedbackService._analyze_feedback_items([])
        
        assert result["ac1"] is None
        assert result["accuracy"] is None
        assert result["total_items"] == 0
        assert result["agreements"] == 0
        assert result["disagreements"] == 0
        assert result["confusion_matrix"] is None
        assert result["warning"] == "No feedback items found"
    
    def test_analyze_feedback_items_with_data(self):
        """Test analysis with actual feedback items."""
        # Create mock feedback items
        items = []
        for i, (initial, final) in enumerate([("Yes", "Yes"), ("No", "Yes"), ("Yes", "No"), ("No", "No")]):
            item = Mock(spec=FeedbackItem)
            item.itemId = f"item-{i}"
            item.initialAnswerValue = initial
            item.finalAnswerValue = final
            items.append(item)
        
        result = FeedbackService._analyze_feedback_items(items)
        
        # Verify basic statistics
        assert result["total_items"] == 4
        assert result["agreements"] == 2  # (Yes,Yes) and (No,No)
        assert result["disagreements"] == 2  # (No,Yes) and (Yes,No)
        assert result["accuracy"] == 50.0  # 2/4 * 100
        
        # Verify confusion matrix exists
        assert result["confusion_matrix"] is not None
        assert "labels" in result["confusion_matrix"]
        assert "matrix" in result["confusion_matrix"]
        
        # Verify class distributions
        assert len(result["class_distribution"]) == 2  # Yes and No
        assert len(result["predicted_class_distribution"]) == 2
    
    @patch('plexus.cli.feedback.feedback_service.GwetAC1')
    def test_analyze_feedback_items_ac1_calculation(self, mock_gwet_class):
        """Test AC1 calculation integration."""
        # Mock the GwetAC1 calculator
        mock_calculator = Mock()
        mock_result = Mock()
        mock_result.value = 0.75
        mock_calculator.calculate.return_value = mock_result
        mock_gwet_class.return_value = mock_calculator
        
        # Create mock feedback items
        items = []
        for initial, final in [("Yes", "Yes"), ("No", "No")]:
            item = Mock(spec=FeedbackItem)
            item.initialAnswerValue = initial
            item.finalAnswerValue = final
            items.append(item)
        
        result = FeedbackService._analyze_feedback_items(items)
        
        # Verify AC1 was calculated
        assert result["ac1"] == 0.75
        mock_calculator.calculate.assert_called_once()
    
    def test_generate_recommendation_no_data(self):
        """Test recommendation generation with no data."""
        analysis = {"total_items": 0}
        recommendation = FeedbackService._generate_recommendation(analysis)
        
        assert "No feedback data available" in recommendation
    
    def test_generate_recommendation_low_accuracy(self):
        """Test recommendation generation for low accuracy."""
        analysis = {
            "total_items": 100,
            "accuracy": 65.0,
            "ac1": 0.3,
            "warning": "Imbalanced classes"
        }
        recommendation = FeedbackService._generate_recommendation(analysis)
        
        assert "Low accuracy detected" in recommendation
        assert "find" in recommendation  # Should recommend using find command
        assert "false positives and negatives" in recommendation  # Specific to imbalanced classes
    
    def test_generate_recommendation_good_performance(self):
        """Test recommendation generation for good performance."""
        analysis = {
            "total_items": 100,
            "accuracy": 92.0,
            "ac1": 0.85,
            "warning": None
        }
        recommendation = FeedbackService._generate_recommendation(analysis)
        
        assert "Good performance" in recommendation
        assert "edge cases" in recommendation
    
    @pytest.mark.asyncio
    async def test_summarize_feedback_integration(self):
        """Test the complete summarize_feedback method."""
        # Mock the find_feedback_items method
        mock_items = []
        for initial, final in [("Yes", "Yes"), ("No", "Yes"), ("Yes", "No")]:
            item = Mock(spec=FeedbackItem)
            item.initialAnswerValue = initial
            item.finalAnswerValue = final
            mock_items.append(item)
        
        with patch.object(FeedbackService, 'find_feedback_items', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_items
            
            result = await FeedbackService.summarize_feedback(
                client=Mock(),
                scorecard_name="Test Scorecard",
                score_name="Test Score",
                scorecard_id="scorecard-123",
                score_id="score-456",
                account_id="account-789",
                days=14
            )
        
        # Verify result structure
        assert isinstance(result, FeedbackSummaryResult)
        assert result.context.scorecard_name == "Test Scorecard"
        assert result.context.score_name == "Test Score"
        assert result.context.total_found == 3
        
        # Verify analysis contains expected fields
        assert "accuracy" in result.analysis
        assert "confusion_matrix" in result.analysis
        assert "ac1" in result.analysis
        
        # Verify recommendation is provided
        assert isinstance(result.recommendation, str)
        assert len(result.recommendation) > 0
    
    def test_format_summary_result_as_dict(self):
        """Test formatting of summary result as dictionary."""
        # Create test data
        context = FeedbackSearchContext(
            scorecard_name="Test Scorecard",
            score_name="Test Score",
            scorecard_id="scorecard-123",
            score_id="score-456",
            account_id="account-789",
            filters={"days": 14},
            total_found=5
        )
        
        analysis = {
            "accuracy": 85.0,
            "ac1": 0.75,
            "total_items": 5,
            "confusion_matrix": {"labels": ["Yes", "No"], "matrix": []}
        }
        
        result = FeedbackSummaryResult(
            context=context,
            analysis=analysis,
            recommendation="Test recommendation"
        )
        
        # Format as dictionary
        formatted = FeedbackService.format_summary_result_as_dict(result)
        
        # Verify structure
        assert "context" in formatted
        assert "analysis" in formatted
        assert "recommendation" in formatted
        
        # Verify content
        assert formatted["context"]["scorecard_name"] == "Test Scorecard"
        assert formatted["analysis"]["accuracy"] == 85.0
        assert formatted["recommendation"] == "Test recommendation"
    
    def test_prioritize_feedback_with_edit_comments(self):
        """Test prioritization of feedback items with edit comments."""
        # Create items with and without edit comments
        items_with_comments = []
        items_without_comments = []
        
        for i in range(3):
            item = Mock(spec=FeedbackItem)
            item.editCommentValue = f"Edit comment {i}"
            items_with_comments.append(item)
        
        for i in range(5):
            item = Mock(spec=FeedbackItem)
            item.editCommentValue = None
            items_without_comments.append(item)
        
        all_items = items_with_comments + items_without_comments
        
        # Test prioritization with limit
        result = FeedbackService.prioritize_feedback_with_edit_comments(
            all_items, limit=4, prioritize_edit_comments=True
        )
        
        # Should get all 3 items with comments plus 1 without
        assert len(result) == 4
        
        # Count items with comments in result
        with_comments_count = sum(1 for item in result if item.editCommentValue)
        assert with_comments_count == 3  # All items with comments should be included
    
    def test_prioritize_feedback_no_limit(self):
        """Test prioritization without limit returns all items."""
        items = [Mock(spec=FeedbackItem) for _ in range(5)]
        
        result = FeedbackService.prioritize_feedback_with_edit_comments(
            items, limit=None, prioritize_edit_comments=True
        )
        
        assert len(result) == 5
        assert result == items
    
    def test_prioritize_feedback_no_prioritization(self):
        """Test prioritization when prioritize_edit_comments is False."""
        items = [Mock(spec=FeedbackItem) for _ in range(10)]
        
        result = FeedbackService.prioritize_feedback_with_edit_comments(
            items, limit=5, prioritize_edit_comments=False
        )
        
        assert len(result) == 5
        # Should be a subset of original items (order may be different due to shuffle) 