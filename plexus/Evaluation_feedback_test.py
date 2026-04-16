"""
Tests for FeedbackEvaluation class.
"""

import pytest
import json
from types import SimpleNamespace
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


@pytest.fixture(autouse=True)
def mock_rca_attachment_upload():
    """Prevent tests from calling real S3 for RCA attachment persistence."""
    with patch(
        "plexus.Evaluation.upload_evaluation_artifact_file",
        return_value="evaluations/eval-789/root_cause.full.json",
    ):
        yield


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
            account_id="account-123",
            account_key="test-account-key"
        )
        
        # Mock the API response
        mock_api_client.execute = MagicMock(return_value={
            'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt': {
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
            account_id="account-123",
            account_key="test-account-key"
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
                    with patch.object(
                        evaluation,
                        '_run_root_cause_analysis',
                        new_callable=AsyncMock,
                        return_value={"topics": [{"label": "topic-1"}]},
                    ):
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
    async def test_run_evaluation_maps_alignment_metric_to_percentage(self, mock_api_client, mock_feedback_items):
        """Alignment metric in evaluation payload should be mapped to [0, 100]."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            account_key="test-account-key"
        )

        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()

        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"

        mapped_analysis = {
            "ac1": -1.0,
            "accuracy": 75.0,
            "precision": 70.0,
            "recall": 65.0,
            "total_items": len(mock_feedback_items),
            "agreements": 0,
            "disagreements": len(mock_feedback_items),
            "confusion_matrix": {"yes": {"yes": 0}},
            "class_distribution": {"yes": 0, "no": len(mock_feedback_items)},
            "predicted_class_distribution": {"yes": 0, "no": len(mock_feedback_items)},
        }

        for item in mock_feedback_items:
            item.itemId = f"item-{item.id}"
            item.isAgreement = item.initialAnswerValue == item.finalAnswerValue
            item.editCommentValue = None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"

        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                with patch.object(evaluation, '_fetch_feedback_items', new_callable=AsyncMock, return_value=mock_feedback_items):
                    with patch('plexus.analysis.feedback_analyzer.analyze_feedback_items', return_value=mapped_analysis):
                        with patch('plexus.dashboard.api.models.score_result.ScoreResult.create', return_value=MagicMock(id="score-result-123")):
                            with patch.object(
                                evaluation,
                                '_run_root_cause_analysis',
                                new_callable=AsyncMock,
                                return_value={"topics": [{"label": "topic-1"}]},
                            ):
                                await evaluation.run()

        final_call = mock_eval_record.update.call_args_list[-1]
        metrics_payload = json.loads(final_call.kwargs["metrics"])
        alignment_metric = next((m for m in metrics_payload if m["name"] == "Alignment"), None)
        assert alignment_metric is not None
        assert alignment_metric["value"] == -1.0

    @pytest.mark.asyncio
    async def test_run_evaluation_persists_rca_attachment_and_compacts_parameters(self, mock_api_client, mock_feedback_items):
        """Feedback evaluation should persist full RCA to attachment and store compact pointer payload."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            account_key="test-account-key"
        )

        for item in mock_feedback_items:
            item.itemId = f"item-{item.id}"
            item.isAgreement = item.initialAnswerValue == item.finalAnswerValue
            item.editCommentValue = None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"

        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()
        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"

        root_cause_payload = {
            "overall_explanation": "summary",
            "topics": [],
            "misclassification_analysis": {
                "item_classifications_all": [
                    {
                        "feedback_item_id": "feedback-1",
                        "item_id": "item-1",
                        "primary_category": "score_configuration_problem",
                        "confidence": "high",
                        "rationale_paragraph": "rationale",
                        "evidence_quote": "quote",
                    }
                ]
            },
        }

        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                with patch.object(evaluation, '_fetch_feedback_items', new_callable=AsyncMock, return_value=mock_feedback_items):
                    with patch.object(evaluation, '_run_root_cause_analysis', new_callable=AsyncMock, return_value=root_cause_payload):
                        with patch(
                            "plexus.Evaluation.upload_evaluation_artifact_file",
                            return_value="evaluations/eval-789/root_cause.full.json",
                        ) as mock_upload:
                            await evaluation.run()

        mock_upload.assert_called_once()
        final_call = mock_eval_record.update.call_args_list[-1]
        params = json.loads(final_call.kwargs["parameters"])
        root_cause = params["root_cause"]
        assert root_cause["output_compacted"] is True
        assert root_cause["output_attachment"] == "evaluations/eval-789/root_cause.full.json"
        # misclassification_analysis summary must be present in the compact payload so the
        # dashboard category breakdown and downstream consumers (optimizer, Universal Code) can
        # read it without fetching the full S3 attachment.
        assert "misclassification_analysis" in root_cause
        # item_classifications_all is the large per-item array; it must NOT be in DynamoDB.
        assert "item_classifications_all" not in root_cause["misclassification_analysis"]

    @pytest.mark.asyncio
    async def test_run_evaluation_fails_when_rca_attachment_upload_fails(self, mock_api_client, mock_feedback_items):
        """Feedback evaluation must fail if full RCA attachment upload fails."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            account_key="test-account-key"
        )

        for item in mock_feedback_items:
            item.itemId = f"item-{item.id}"
            item.isAgreement = item.initialAnswerValue == item.finalAnswerValue
            item.editCommentValue = None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"

        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()
        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"

        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                with patch.object(evaluation, '_fetch_feedback_items', new_callable=AsyncMock, return_value=mock_feedback_items):
                    with patch.object(
                        evaluation,
                        '_run_root_cause_analysis',
                        new_callable=AsyncMock,
                        return_value={"overall_explanation": "summary", "topics": []},
                    ):
                        with patch(
                            "plexus.Evaluation.upload_evaluation_artifact_file",
                            side_effect=RuntimeError("attachment upload failed"),
                        ):
                            with pytest.raises(RuntimeError, match="attachment upload failed"):
                                await evaluation.run()

        failed_call = any(call.kwargs.get('status') == 'FAILED' for call in mock_eval_record.update.call_args_list)
        assert failed_call
    
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

                        with patch.object(
                            evaluation,
                            '_run_root_cause_analysis',
                            new_callable=AsyncMock,
                            return_value={"topics": [{"label": "topic-1"}]},
                        ):
                            result = await evaluation.run()
                        
                        # Verify ScoreResult.create was called for each feedback item
                        assert mock_create.call_count == len(mock_feedback_items)
                        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_run_evaluation_random_sampling_with_seed_is_deterministic(self, mock_api_client):
        """Random sampling with sample_seed should produce the same subset across runs."""
        feedback_items = []
        for i in range(10):
            item = MagicMock()
            item.id = f"item-{i}"
            item.itemId = f"raw-item-{i}"
            item.initialAnswerValue = "Yes" if i % 2 == 0 else "No"
            item.finalAnswerValue = "No" if i % 2 == 0 else "Yes"
            item.isAgreement = False
            item.editCommentValue = None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"
            feedback_items.append(item)

        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()

        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"

        sampled_id_sets = []

        async def _run_once():
            evaluation = FeedbackEvaluation(
                scorecard_name="Test Scorecard",
                scorecard=None,
                api_client=mock_api_client,
                days=7,
                scorecard_id="scorecard-123",
                score_id="score-456",
                evaluation_id="eval-789",
                account_id="account-123",
                account_key="test-account-key",
                max_items=5,
                sampling_mode="random",
                sample_seed=1337,
            )

            with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
                with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                    with patch.object(evaluation, '_fetch_feedback_items', new_callable=AsyncMock, return_value=feedback_items):
                        with patch.object(evaluation, '_create_score_results_from_feedback', new_callable=AsyncMock):
                            with patch('plexus.analysis.feedback_analyzer.analyze_feedback_items') as mock_analyze:
                                mock_analyze.return_value = {
                                    "ac1": 0.5,
                                    "accuracy": 50.0,
                                    "precision": 50.0,
                                    "recall": 50.0,
                                    "total_items": 5,
                                    "agreements": 0,
                                    "disagreements": 5,
                                    "confusion_matrix": {},
                                    "class_distribution": {},
                                    "predicted_class_distribution": {},
                                }
                                with patch.object(
                                    evaluation,
                                    '_run_root_cause_analysis',
                                    new_callable=AsyncMock,
                                    return_value={"topics": [{"label": "topic-1"}]},
                                ):
                                    await evaluation.run()
                                analyzed_items = mock_analyze.call_args.args[0]
                                sampled_id_sets.append({i.id for i in analyzed_items})

        await _run_once()
        await _run_once()

        assert len(sampled_id_sets[0]) == 5
        assert sampled_id_sets[0] == sampled_id_sets[1]

    @pytest.mark.asyncio
    async def test_root_cause_analysis_passes_max_exemplars_to_biblicus(self, mock_api_client, monkeypatch):
        """RCA should pass exemplar limits through to the current Biblicus constructor."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            account_key="test-account-key"
        )
        evaluation.dashboard_client = None

        feedback_items = []
        score_result_map = {}
        for i in range(5):
            item = MagicMock()
            item.id = f"feedback-{i}"
            item.itemId = f"item-{i}"
            item.initialAnswerValue = "No"
            item.finalAnswerValue = "Yes"
            item.editCommentValue = f"Comment {i}"
            item.editedAt = datetime.now(timezone.utc)
            feedback_items.append(item)
            score_result_map[item.id] = {
                "value": "No",
                "human_label": "Yes",
                "explanation": f"Explanation {i}",
            }

        import biblicus.analysis.reinforcement_memory as rm_mod
        captured = {}

        class FakeReinforcementMemory:
            def __init__(
                self,
                data_dir,
                vector_store,
                embed,
                label=None,
                infer_cause=None,
                synthesize_cause=None,
                min_topic_size=10,
                embedding_dim=384,
                max_exemplars=5,
            ):
                self.data_dir = data_dir
                captured["max_exemplars"] = max_exemplars

            def ingest(self, texts):
                self.texts = texts

            def analyze(self, group_id, min_topic_size=3):
                return SimpleNamespace(topics=[])

        monkeypatch.setattr(rm_mod, "ReinforcementMemory", FakeReinforcementMemory)
        monkeypatch.setattr(rm_mod, "LocalVectorStore", lambda store_dir: object())
        monkeypatch.setattr(
            rm_mod,
            "sentence_transformer_embedder",
            lambda model_id: (lambda texts: [[0.0] * 384 for _ in texts]),
        )
        monkeypatch.setattr(rm_mod, "bedrock_labeler", lambda: None)
        monkeypatch.setattr(rm_mod, "bedrock_causal", lambda: None)
        monkeypatch.setattr(rm_mod, "bedrock_synthesizer", lambda: None)
        import plexus.rca_analysis as rca_mod
        monkeypatch.setattr(
            rca_mod,
            "extract_misclassification_evidence_flags",
            lambda *, item_context: {
                "external_information_missing_or_degraded": False,
                "guideline_or_policy_ambiguity": False,
                "missing_required_context_due_system": False,
                "runtime_or_parsing_failure": False,
                "invalid_output_class_signal": False,
                "best_evidence_source": "none",
                "best_evidence_quote": "",
            },
        )
        monkeypatch.setattr(
            rca_mod,
            "explain_misclassification_item_classification",
            lambda **kwargs: {
                "rationale_paragraph": "Score logic likely fix surface.",
                "evidence_quote": "Explanation",
                "config_fixability": "likely_fixable",
            },
        )

        result = await evaluation._run_root_cause_analysis(
            feedback_items,
            score_result_map=score_result_map,
            original_explanations={},
            max_report_exemplars=20,
        )

        assert captured["max_exemplars"] == 20
        assert result["topics"] == []

    @pytest.mark.asyncio
    async def test_run_fails_when_incorrect_items_and_rca_missing(self, mock_api_client, mock_feedback_items):
        """Feedback-backed runs with incorrect items must fail if RCA payload is missing."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            account_key="test-account-key",
        )

        for item in mock_feedback_items:
            item.itemId = f"item-{item.id}"
            item.isAgreement = item.initialAnswerValue == item.finalAnswerValue
            item.editCommentValue = None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"

        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()
        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"

        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                with patch.object(evaluation, '_fetch_feedback_items', new_callable=AsyncMock, return_value=mock_feedback_items):
                    with patch.object(evaluation, '_run_root_cause_analysis', new_callable=AsyncMock, return_value={}):
                        with pytest.raises(RuntimeError, match="no usable RCA payload"):
                            await evaluation.run()

        failed_call = any(call.kwargs.get('status') == 'FAILED' for call in mock_eval_record.update.call_args_list)
        assert failed_call

    @pytest.mark.asyncio
    async def test_run_succeeds_without_rca_when_no_incorrect_items(self, mock_api_client):
        """RCA is not required when there are zero incorrect items."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            account_key="test-account-key",
        )

        perfect_items = []
        for i in range(3):
            item = MagicMock()
            item.id = f"item-{i}"
            item.itemId = f"raw-item-{i}"
            item.initialAnswerValue = "Yes"
            item.finalAnswerValue = "Yes"
            item.isAgreement = True
            item.editCommentValue = None
            item.initialCommentValue = None
            item.finalCommentValue = None
            item.editedAt = datetime.now(timezone.utc)
            item.editorName = "Test Editor"
            perfect_items.append(item)

        mock_eval_record = MagicMock()
        mock_eval_record.id = "eval-789"
        mock_eval_record.update = MagicMock()
        mock_scorecard = MagicMock()
        mock_scorecard.id = "scorecard-123"

        with patch('plexus.dashboard.api.models.evaluation.Evaluation.get_by_id', return_value=mock_eval_record):
            with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id', return_value=mock_scorecard):
                with patch.object(evaluation, '_fetch_feedback_items', new_callable=AsyncMock, return_value=perfect_items):
                    with patch.object(evaluation, '_run_root_cause_analysis', new_callable=AsyncMock, return_value={}):
                        result = await evaluation.run()

        assert result["status"] == "success"
        final_call = mock_eval_record.update.call_args_list[-1]
        assert final_call.kwargs.get("status") == "COMPLETED"

    @pytest.mark.asyncio
    async def test_small_set_path_invoked_for_fewer_than_five_items(self, mock_api_client):
        """_run_root_cause_analysis should delegate to small-set RCA when candidate count < 5."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            account_key="test-account-key",
        )

        feedback_items = []
        score_result_map = {}
        for i in range(3):
            item = MagicMock()
            item.id = f"feedback-{i}"
            item.itemId = f"item-{i}"
            item.initialAnswerValue = "No"
            item.finalAnswerValue = "Yes"
            item.editCommentValue = f"comment-{i}"
            item.editedAt = datetime.now(timezone.utc)
            feedback_items.append(item)
            score_result_map[item.id] = {"value": "No", "human_label": "Yes", "explanation": f"exp-{i}"}

        expected = {
            "topics": [{"label": "Small-set RCA Summary"}],
            "overall_explanation": "summary",
            "overall_improvement_suggestion": "improve",
        }

        with patch.object(
            evaluation,
            "_run_small_set_root_cause_analysis",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_small:
            result = await evaluation._run_root_cause_analysis(
                feedback_items=feedback_items,
                score_result_map=score_result_map,
                original_explanations={},
            )

        assert result == expected
        assert mock_small.await_count == 1

    @pytest.mark.asyncio
    async def test_small_set_path_returns_empty_when_no_candidates(self, mock_api_client):
        """_run_root_cause_analysis should return empty payload when no incorrect candidates exist."""
        evaluation = FeedbackEvaluation(
            scorecard_name="Test Scorecard",
            scorecard=None,
            api_client=mock_api_client,
            days=7,
            scorecard_id="scorecard-123",
            score_id="score-456",
            evaluation_id="eval-789",
            account_id="account-123",
            account_key="test-account-key",
        )

        result = await evaluation._run_root_cause_analysis(
            feedback_items=[],
            score_result_map={},
            original_explanations={},
        )


class TestCompactRootCauseForParameters:
    """Unit tests for FeedbackEvaluation._compact_root_cause_for_parameters."""

    ATTACHMENT = "evaluations/eval-1/root_cause.full.json"

    def _make_full_payload(self, **overrides):
        payload = {
            "overall_explanation": "explanation text",
            "overall_improvement_suggestion": "suggestion text",
            "topics": [{"topic_id": "t1", "label": "Topic A", "member_count": 3}],
            "misclassification_analysis": {
                "category_totals": {
                    "score_configuration_problem": 4,
                    "information_gap": 2,
                    "guideline_gap_requires_sme": 1,
                    "mechanical_malfunction": 0,
                },
                "category_shares": {
                    "score_configuration_problem": 0.571,
                    "information_gap": 0.286,
                    "guideline_gap_requires_sme": 0.143,
                    "mechanical_malfunction": 0.0,
                },
                "overall_assessment": {
                    "total_items": 7,
                    "predominant_category": "score_configuration_problem",
                    "score_fix_candidate_items": 4,
                },
                "primary_next_action": {
                    "action": "score_configuration_optimization",
                    "confidence": "medium",
                    "reasons": ["Score-configuration problems remain the most actionable fix surface."],
                },
                "optimization_applicability": {
                    "status": "applicable",
                    "reason": "Misclassification mix supports direct score-configuration optimization.",
                },
                "mechanical_subtype_totals": {},
                "evaluation_red_flags": [],
                "category_diagnostics": {},
                "category_summaries": {
                    "score_configuration_problem": {
                        "category_summary_text": "4 item(s) classified as score configuration problem.",
                        "top_patterns": [],
                        "representative_evidence": [],
                        "item_count": 4,
                    }
                },
                "topic_category_breakdown": [],
                "max_category_summary_items_used": 20,
                "item_classifications_all": [
                    {"item_id": "item-1", "primary_category": "score_configuration_problem"},
                    {"item_id": "item-2", "primary_category": "information_gap"},
                ],
            },
        }
        payload.update(overrides)
        return payload

    def test_pointer_fields_always_present(self):
        result = FeedbackEvaluation._compact_root_cause_for_parameters(
            self._make_full_payload(), self.ATTACHMENT
        )
        assert result["output_compacted"] is True
        assert result["output_attachment"] == self.ATTACHMENT

    def test_narrative_fields_preserved(self):
        result = FeedbackEvaluation._compact_root_cause_for_parameters(
            self._make_full_payload(), self.ATTACHMENT
        )
        assert result["overall_explanation"] == "explanation text"
        assert result["overall_improvement_suggestion"] == "suggestion text"

    def test_misclassification_analysis_included(self):
        result = FeedbackEvaluation._compact_root_cause_for_parameters(
            self._make_full_payload(), self.ATTACHMENT
        )
        assert "misclassification_analysis" in result

    def test_item_classifications_all_excluded(self):
        result = FeedbackEvaluation._compact_root_cause_for_parameters(
            self._make_full_payload(), self.ATTACHMENT
        )
        assert "item_classifications_all" not in result["misclassification_analysis"]

    def test_category_totals_preserved(self):
        result = FeedbackEvaluation._compact_root_cause_for_parameters(
            self._make_full_payload(), self.ATTACHMENT
        )
        totals = result["misclassification_analysis"]["category_totals"]
        assert totals["score_configuration_problem"] == 4
        assert totals["information_gap"] == 2

    def test_overall_assessment_preserved(self):
        result = FeedbackEvaluation._compact_root_cause_for_parameters(
            self._make_full_payload(), self.ATTACHMENT
        )
        overall = result["misclassification_analysis"]["overall_assessment"]
        assert overall["total_items"] == 7
        assert overall["predominant_category"] == "score_configuration_problem"

    def test_primary_next_action_preserved(self):
        result = FeedbackEvaluation._compact_root_cause_for_parameters(
            self._make_full_payload(), self.ATTACHMENT
        )
        action = result["misclassification_analysis"]["primary_next_action"]
        assert action["action"] == "score_configuration_optimization"
        assert action["confidence"] == "medium"

    def test_optimization_applicability_preserved(self):
        result = FeedbackEvaluation._compact_root_cause_for_parameters(
            self._make_full_payload(), self.ATTACHMENT
        )
        applicability = result["misclassification_analysis"]["optimization_applicability"]
        assert applicability["status"] == "applicable"

    def test_missing_misclassification_analysis_is_tolerated(self):
        payload = self._make_full_payload()
        del payload["misclassification_analysis"]
        result = FeedbackEvaluation._compact_root_cause_for_parameters(payload, self.ATTACHMENT)
        assert "misclassification_analysis" not in result

    def test_raises_on_non_dict_payload(self):
        with pytest.raises(ValueError, match="root_cause_payload must be a dictionary"):
            FeedbackEvaluation._compact_root_cause_for_parameters("not a dict", self.ATTACHMENT)

    def test_raises_on_missing_attachment(self):
        with pytest.raises(ValueError, match="output_attachment is required"):
            FeedbackEvaluation._compact_root_cause_for_parameters(self._make_full_payload(), "")
