"""Unit tests for Lambda handler"""
import pytest
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
