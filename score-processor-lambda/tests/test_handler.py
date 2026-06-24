"""Unit tests for Lambda handler"""
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock


class TestLambdaJobProcessor:
    """Tests for LambdaJobProcessor class"""

    def test_init_success(self):
        """Test successful initialization of LambdaJobProcessor"""
        import handler

        processor = handler.LambdaJobProcessor()

        assert processor.client is not None
        assert processor.sqs_client is not None
        # Just verify these are set (not empty), don't check exact values
        # since they may come from actual .env file during development
        assert processor.request_queue_url is not None
        assert processor.request_queue_url != ''
        assert processor.response_queue_url is not None
        assert processor.response_queue_url != ''
        assert processor.account_key is not None
        assert processor.account_key != ''

    def test_init_missing_env_vars(self, monkeypatch):
        """Test initialization fails with missing environment variables"""
        import handler

        # Remove required env var
        monkeypatch.delenv('PLEXUS_ACCOUNT_KEY', raising=False)

        with pytest.raises(ValueError, match="Missing required environment variables"):
            handler.LambdaJobProcessor()

    @pytest.mark.asyncio
    async def test_process_job_passes_item_attached_files_to_scoring_metadata(self):
        """Item attachment keys should be available to timestamp enrichment."""
        import handler

        processor = handler.LambdaJobProcessor.__new__(handler.LambdaJobProcessor)
        processor.client = MagicMock()
        processor.sqs_client = MagicMock()
        processor.request_queue_url = "request-queue"
        processor.response_queue_url = "response-queue"
        processor.account_id = "account-1"

        scoring_job = SimpleNamespace(update=MagicMock())
        item = SimpleNamespace(
            id="item-1",
            text="The customer said I need transportation.",
            attachedFiles=["items/report-123/deepgram.json"],
        )
        scoring_result = SimpleNamespace(
            value="Yes",
            explanation='The customer said "I need transportation."',
            metadata={},
            start_time_seconds=1.2,
            end_time_seconds=2.4,
        )
        scoring_outcome = SimpleNamespace(
            dependency_unmet=False,
            result=scoring_result,
        )

        with patch.object(handler.ScoringJob, "get_by_id", return_value=scoring_job), \
             patch.object(handler.Item, "get_by_id", return_value=item), \
             patch.object(handler, "resolve_scorecard_id", new_callable=AsyncMock, return_value="scorecard-dynamo-1"), \
             patch.object(handler, "resolve_score_id", new_callable=AsyncMock, return_value={"id": "score-dynamo-1", "name": "Target Score"}), \
             patch.object(handler, "get_metadata_from_item", new_callable=AsyncMock, return_value={}), \
             patch.object(handler, "get_external_id_from_item", new_callable=AsyncMock, return_value="external-1"), \
             patch.object(handler, "create_scorecard_instance_for_single_score", new_callable=AsyncMock, return_value=MagicMock()), \
             patch.object(handler, "score_single_target_with_dependencies", new_callable=AsyncMock, return_value=scoring_outcome) as score_single, \
             patch.object(handler, "create_score_result", new_callable=AsyncMock, return_value="score-result-1"):
            await processor.process_job(
                "job-1",
                "item-1",
                "scorecard-external-1",
                "score-external-1",
                receipt_handle=None,
            )

        scoring_metadata = score_single.call_args.kwargs["metadata"]
        assert scoring_metadata["item_id"] == "score-result-record--item-1"
        assert scoring_metadata["attachedFiles"] == ["items/report-123/deepgram.json"]


class TestLambdaHandler:
    """Tests for lambda_handler function"""

    def test_handler_exists(self):
        """Test that lambda_handler function exists"""
        import handler

        assert hasattr(handler, 'lambda_handler')
        assert callable(handler.lambda_handler)

    def test_handler_with_empty_event(self, lambda_context):
        """Test handler with empty event (manual invocation with no messages)"""
        import handler

        with patch.object(handler, 'async_handler', new_callable=AsyncMock) as mock_async:
            mock_async.return_value = {
                'statusCode': 200,
                'body': '{"message": "No messages in queue", "processed": false}'
            }

            result = handler.lambda_handler({}, lambda_context)

            assert result is not None
            mock_async.assert_called_once()


class TestEventParsing:
    """Tests for event parsing logic"""

    def test_sqs_event_detection(self, sample_sqs_event):
        """Test that SQS events are correctly detected"""
        assert 'Records' in sample_sqs_event
        assert len(sample_sqs_event['Records']) > 0
        assert sample_sqs_event['Records'][0]['eventSource'] == 'aws:sqs'

    def test_manual_event_detection(self, sample_manual_event):
        """Test that manual invocation events are correctly detected"""
        assert 'Records' not in sample_manual_event
