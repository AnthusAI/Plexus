"""
Tests for FeedbackEvaluation class.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from plexus.Evaluation import FeedbackEvaluation


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = MagicMock()
    client.account_id = "test-account-id"
    return client


@pytest.fixture
def mock_feedback_items():
    """Create mock feedback items."""
    items = []
    for i in range(10):
        item = MagicMock()
        item.id = f"item-{i}"
        item.initialAnswerValue = "Yes" if i < 3 else "No"
        item.finalAnswerValue = "No"
        items.append(item)
    return items


class TestFeedbackEvaluation:
    """Tests for FeedbackEvaluation class."""
    
    def test_initialization(self, mock_api_client):
        """Test FeedbackEvaluation initialization."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            task_id="task-999"
        )
        
        assert evaluation.days == 7
        assert evaluation.scorecard_id == "scorecard-123"
        assert evaluation.score_id == "score-456"
        assert evaluation.evaluation_id == "eval-789"
        assert evaluation.account_id == "account-123"
        assert evaluation.task_id == "task-999"
    
    @pytest.mark.asyncio
    async def test_fetch_feedback_items(self, mock_api_client, mock_feedback_items):
        """Test fetching feedback items."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123"
        )
        
        # Mock the API response
        mock_api_client.execute = MagicMock(return_value={
            'listFeedbackItems': {
                'items': [
                    {
                        'id': item.id,
                        'accountId': 'test-account',
                        'scorecardId': 'scorecard-123',
                        'scoreId': 'score-456',
                        'itemId': f'item-{i}',
                        'initialAnswerValue': item.initialAnswerValue,
                        'finalAnswerValue': item.finalAnswerValue,
                        'isMismatch': item.initialAnswerValue != item.finalAnswerValue,
                        'createdAt': datetime.now(timezone.utc).isoformat(),
                        'updatedAt': datetime.now(timezone.utc).isoformat()
                    }
                    for i, item in enumerate(mock_feedback_items)
                ],
                'nextToken': None
            }
        })
        
        # Fetch items
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        items = await evaluation._fetch_feedback_items(
            scorecard_id="scorecard-123",
            score_id="score-456",
            start_date=start_date,
            end_date=end_date
        )
        
        assert len(items) == 10
        assert mock_api_client.execute.called
    
    @pytest.mark.asyncio
    async def test_run_evaluation(self, mock_api_client, mock_feedback_items):
        """Test running a complete feedback evaluation."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123"
        )
        
        # Mock the evaluation record
        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()
        
        # Mock the scorecard
        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"
        
        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                with patch.object(evaluation, '_fetch_feedback_items', new_callable=AsyncMock, return_value=mock_feedback_items):
                    result = await evaluation.run()
                    
                    assert result["status"] == "success"
                    assert result["evaluation_id"] == "eval-789"
                    assert "metrics" in result
                    assert "analysis" in result
                    
                    # Check that metrics include AC1 first
                    metrics = result["metrics"]
                    assert "ac1" in metrics
                    assert "accuracy" in metrics
                    assert "precision" in metrics
                    assert "recall" in metrics
                    
                    # Verify evaluation record was updated
                    assert mock_eval_record.update.called
                    
                    # Check that status was updated to COMPLETED
                    update_calls = mock_eval_record.update.call_args_list
                    final_call = update_calls[-1]
                    assert final_call[1].get('status') == 'COMPLETED' or final_call[0][0] == 'status'
    
    @pytest.mark.asyncio
    async def test_run_evaluation_without_score_id(self, mock_api_client):
        """Test that feedback evaluation requires a score_id."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id=None,  # No score_id provided
            evaluation_id="eval-789",
            account_id="account-123"
        )
        
        # Mock the evaluation record
        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()
        
        # Mock the scorecard
        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"
        
        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                with pytest.raises(ValueError) as exc_info:
                    await evaluation.run()
                
                assert "score_id is required" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_run_evaluation_error_handling(self, mock_api_client):
        """Test error handling in feedback evaluation."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123"
        )
        
        # Mock the evaluation record
        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()
        
        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', side_effect=Exception("Test error")):
                with pytest.raises(Exception) as exc_info:
                    await evaluation.run()
                
                assert "Test error" in str(exc_info.value)
                
                # Verify evaluation record was updated with error
                assert mock_eval_record.update.called
                update_calls = mock_eval_record.update.call_args_list
                # Check if any call has status='FAILED'
                failed_call = any(
                    call[1].get('status') == 'FAILED' or (len(call[0]) > 0 and call[0][0] == 'status' and 'FAILED' in str(call))
                    for call in update_calls
                )
                assert failed_call
    
    @pytest.mark.asyncio
    async def test_create_score_results_from_feedback(self, mock_api_client):
        """Test creating ScoreResult records from FeedbackItems."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123"
        )
        
        # Create mock feedback items with different agreement statuses
        mock_items = []
        for i in range(5):
            item = MagicMock()
            item.id = f"feedback-{i}"
            item.itemId = f"item-{i}"
            item.initialAnswerValue = "Yes" if i < 2 else "No"
            item.finalAnswerValue = "Yes" if i < 3 else "No"  # First 2 agree, 3rd disagrees
            item.isAgreement = item.initialAnswerValue == item.finalAnswerValue
            item.editCommentValue = f"Comment {i}" if i % 2 == 0 else None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"
            mock_items.append(item)
        
        # Mock Item.get_by_id to return item with text
        mock_item = MagicMock()
        mock_item.text = "Sample transcript text"
        
        # Mock the GraphQL query for production ScoreResults
        # This will be called once per feedback item
        mock_api_client.execute.return_value = {
            'listScoreResults': {
                'items': [{
                    'id': 'prod-result-123',
                    'evaluationId': None,  # Production results don't have evaluationId
                    'explanation': 'Test explanation from production',
                    'trace': '{"step": "test"}'
                }]
            }
        }
        
        # Mock ScoreResult.create and Item.get_by_id
        with patch('plexus.dashboard.api.models.score_result.ScoreResult.create') as mock_create:
            with patch('plexus.dashboard.api.models.item.Item.get_by_id', return_value=mock_item):
                mock_create.return_value = MagicMock(id="score-result-123")
                
                await evaluation._create_score_results_from_feedback(
                    feedback_items=mock_items,
                    evaluation_id="eval-789",
                    scorecard_id="scorecard-123",
                    score_id="score-456",
                    account_id="account-123"
                )
                
                # Verify ScoreResult.create was called for each item
                assert mock_create.call_count == 5
                
                # Check the first call's arguments
                first_call = mock_create.call_args_list[0]
                call_kwargs = first_call[1]
                
                assert call_kwargs['evaluationId'] == "eval-789"
                assert call_kwargs['itemId'] == "item-0"
                assert call_kwargs['accountId'] == "account-123"
                assert call_kwargs['scorecardId'] == "scorecard-123"
                assert call_kwargs['scoreId'] == "score-456"
                assert call_kwargs['feedbackItemId'] == "feedback-0"
                assert call_kwargs['value'] == "Yes"  # initialAnswerValue (predicted)
                assert call_kwargs['explanation'] == 'Test explanation from production'  # From production ScoreResult
                assert call_kwargs['trace'] == {"step": "test"}  # From production ScoreResult
                assert call_kwargs['confidence'] is None  # No confidence for feedback evaluations
                assert call_kwargs['correct'] is True  # First item agrees
                assert call_kwargs['type'] == 'evaluation'
                assert call_kwargs['status'] == 'COMPLETED'
                
                # Check metadata structure
                metadata = call_kwargs['metadata']
                assert metadata['feedback_item_id'] == "feedback-0"
                assert metadata['initial_value'] == "Yes"
                assert metadata['final_value'] == "Yes"
                assert metadata['human_label'] == "Yes"  # Frontend expects this field
                assert metadata['text'] == "Sample transcript text"  # From Item
                assert metadata['is_agreement'] is True
                assert metadata['correct'] is True
                assert metadata['evaluation_type'] == 'feedback'
                assert 'edit_comment' in metadata  # Should be present for item 0
                
                # Check the third call (disagreement case)
                third_call = mock_create.call_args_list[2]
                third_kwargs = third_call[1]
                assert third_kwargs['correct'] is False  # Third item disagrees
                assert third_kwargs['confidence'] is None  # No confidence for feedback evaluations
    
    @pytest.mark.asyncio
    async def test_create_score_results_handles_errors(self, mock_api_client):
        """Test that ScoreResult creation handles errors gracefully."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123"
        )
        
        # Create mock feedback items
        mock_items = []
        for i in range(3):
            item = MagicMock()
            item.id = f"feedback-{i}"
            item.itemId = f"item-{i}"
            item.initialAnswerValue = "Yes"
            item.finalAnswerValue = "No"
            item.isAgreement = False
            item.editCommentValue = None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"
            mock_items.append(item)
        
        # Mock ScoreResult.create to fail on second item
        with patch('plexus.dashboard.api.models.score_result.ScoreResult.create') as mock_create:
            def create_side_effect(*args, **kwargs):
                if kwargs['feedbackItemId'] == "feedback-1":
                    raise Exception("Database error")
                return MagicMock(id="score-result-123")
            
            mock_create.side_effect = create_side_effect
            
            # Should not raise exception, but should log errors
            await evaluation._create_score_results_from_feedback(
                feedback_items=mock_items,
                evaluation_id="eval-789",
                scorecard_id="scorecard-123",
                score_id="score-456",
                account_id="account-123"
            )
            
            # Verify all items were attempted
            assert mock_create.call_count == 3
    
    @pytest.mark.asyncio
    async def test_run_evaluation_creates_score_results(self, mock_api_client, mock_feedback_items):
        """Test that running evaluation creates ScoreResult records."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123"
        )
        
        # Add required attributes to mock items
        for item in mock_feedback_items:
            item.itemId = f"item-{item.id}"
            item.isAgreement = item.initialAnswerValue == item.finalAnswerValue
            item.editCommentValue = None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"
        
        # Mock the evaluation record
        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()
        
        # Mock the scorecard
        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"
        
        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                with patch.object(evaluation, '_fetch_feedback_items', new_callable=AsyncMock, return_value=mock_feedback_items):
                    with patch('plexus.dashboard.api.models.score_result.ScoreResult.create') as mock_create:
                        mock_create.return_value = MagicMock(id="score-result-123")
                        
                        result = await evaluation.run()
                        
                        # Verify ScoreResult.create was called for each feedback item
                        assert mock_create.call_count == len(mock_feedback_items)
                        assert result["status"] == "success"

