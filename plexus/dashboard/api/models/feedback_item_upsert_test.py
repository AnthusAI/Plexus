import pytest
from unittest.mock import Mock, MagicMock, patch
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.client import PlexusDashboardClient


class TestFeedbackItemUpsertByCacheKey:
    """Test suite for FeedbackItem.upsert_by_cache_key functionality."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_client = Mock(spec=PlexusDashboardClient)
        self.test_account_id = "test-account-123"
        self.test_scorecard_id = "test-scorecard-456"
        self.test_score_id = "test-score-789"
        self.test_cache_key = "test-score-789:12345"
        self.test_feedback_data = {
            "initial_answer_value": "Yes",
            "final_answer_value": "No",
            "initial_comment_value": "Initial comment",
            "final_comment_value": "Final comment",
            "edit_comment_value": "Edit comment",
            "is_agreement": False,
            "edited_at": "2023-01-01T12:00:00Z",
            "editor_name": "Test Editor",
            "item_id": "test-item-001"
        }

    def test_upsert_creates_new_feedback_item_when_none_exists(self):
        """Test that upsert creates a new FeedbackItem when none exists."""
        # Mock the lookup to return None (no existing item)
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=None):
            # Mock the create to return a new item
            mock_created_item = Mock()
            mock_created_item.id = "new-feedback-item-123"
            
            with patch.object(FeedbackItem, '_create_feedback_item', return_value=mock_created_item):
                # Call upsert
                feedback_item_id, was_created, error = FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=self.test_score_id,
                    cache_key=self.test_cache_key,
                    **self.test_feedback_data
                )
                
                # Verify results
                assert feedback_item_id == "new-feedback-item-123"
                assert was_created is True
                assert error is None

    def test_upsert_updates_existing_feedback_item_when_found(self):
        """Test that upsert updates an existing FeedbackItem when found."""
        # Mock existing item
        mock_existing_item = Mock()
        mock_existing_item.id = "existing-feedback-item-456"
        
        # Mock the lookup to return existing item
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=mock_existing_item):
            # Mock the update to return updated item
            mock_updated_item = Mock()
            mock_updated_item.id = "existing-feedback-item-456"
            
            with patch.object(FeedbackItem, '_update_feedback_item', return_value=mock_updated_item):
                # Call upsert
                feedback_item_id, was_created, error = FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=self.test_score_id,
                    cache_key=self.test_cache_key,
                    **self.test_feedback_data
                )
                
                # Verify results
                assert feedback_item_id == "existing-feedback-item-456"
                assert was_created is False
                assert error is None

    def test_upsert_handles_creation_failure(self):
        """Test that upsert handles creation failures gracefully."""
        # Mock the lookup to return None (no existing item)
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=None):
            # Mock the create to return None (failure)
            with patch.object(FeedbackItem, '_create_feedback_item', return_value=None):
                # Call upsert
                feedback_item_id, was_created, error = FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=self.test_score_id,
                    cache_key=self.test_cache_key,
                    **self.test_feedback_data
                )
                
                # Verify results
                assert feedback_item_id is None
                assert was_created is False
                assert error == "Failed to create new FeedbackItem"

    def test_upsert_handles_update_failure(self):
        """Test that upsert handles update failures gracefully."""
        # Mock existing item
        mock_existing_item = Mock()
        mock_existing_item.id = "existing-feedback-item-456"
        
        # Mock the lookup to return existing item
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=mock_existing_item):
            # Mock the update to return None (failure)
            with patch.object(FeedbackItem, '_update_feedback_item', return_value=None):
                # Call upsert
                feedback_item_id, was_created, error = FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=self.test_score_id,
                    cache_key=self.test_cache_key,
                    **self.test_feedback_data
                )
                
                # Verify results
                assert feedback_item_id is None
                assert was_created is False
                assert error == "Failed to update existing FeedbackItem"

    def test_upsert_handles_exception_gracefully(self):
        """Test that upsert handles exceptions gracefully."""
        # Mock the lookup to raise an exception
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', side_effect=Exception("Lookup failed")):
            # Call upsert
            feedback_item_id, was_created, error = FeedbackItem.upsert_by_cache_key(
                client=self.mock_client,
                account_id=self.test_account_id,
                scorecard_id=self.test_scorecard_id,
                score_id=self.test_score_id,
                cache_key=self.test_cache_key,
                **self.test_feedback_data
            )
            
            # Verify results
            assert feedback_item_id is None
            assert was_created is False
            assert "Exception during FeedbackItem upsert" in error

    def test_upsert_builds_correct_payload(self):
        """Test that upsert builds the correct data payload."""
        # Mock the lookup to return None (no existing item)
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=None):
            # Mock the create method to capture the data passed to it
            mock_created_item = Mock()
            mock_created_item.id = "new-feedback-item-123"
            
            with patch.object(FeedbackItem, '_create_feedback_item', return_value=mock_created_item) as mock_create:
                # Call upsert
                FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=self.test_score_id,
                    cache_key=self.test_cache_key,
                    **self.test_feedback_data
                )
                
                # Extract the data that was passed to create
                mock_create.assert_called_once()
                args, kwargs = mock_create.call_args
                data_passed = args[1]  # Second argument is the feedback_data
                
                # Verify the payload structure
                assert data_passed["accountId"] == self.test_account_id
                assert data_passed["scorecardId"] == self.test_scorecard_id
                assert data_passed["scoreId"] == self.test_score_id
                assert data_passed["cacheKey"] == self.test_cache_key
                assert data_passed["initialAnswerValue"] == "Yes"
                assert data_passed["finalAnswerValue"] == "No"
                assert data_passed["isAgreement"] is False

    def test_upsert_handles_optional_fields_correctly(self):
        """Test that upsert handles optional fields correctly."""
        # Test with minimal data (only required fields)
        minimal_data = {}
        
        # Mock the lookup to return None (no existing item)
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=None):
            mock_created_item = Mock()
            mock_created_item.id = "new-feedback-item-123"
            
            with patch.object(FeedbackItem, '_create_feedback_item', return_value=mock_created_item) as mock_create:
                # Call upsert with minimal data
                FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=self.test_score_id,
                    cache_key=self.test_cache_key,
                    **minimal_data
                )
                
                # Extract the data that was passed to create
                args, kwargs = mock_create.call_args
                data_passed = args[1]
                
                # Verify only required fields are present
                required_fields = {"accountId", "scorecardId", "scoreId", "cacheKey"}
                assert set(data_passed.keys()) == required_fields


class TestFeedbackItemLookupByCacheKey:
    """Test suite for FeedbackItem._lookup_feedback_item_by_cache_key."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_client = Mock(spec=PlexusDashboardClient)
        self.test_cache_key = "test-score-789:12345"

    def test_lookup_returns_feedback_item_when_found(self):
        """Test that lookup returns FeedbackItem when found."""
        # Mock successful GraphQL response
        mock_response = {
            "listFeedbackItemByCacheKey": {
                "items": [{
                    "id": "found-feedback-item-123",
                    "accountId": "test-account",
                    "cacheKey": self.test_cache_key,
                    "scoreId": "test-score-789"
                }]
            }
        }
        self.mock_client.execute.return_value = mock_response
        
        # Mock from_dict to return a FeedbackItem
        mock_feedback_item = Mock(spec=FeedbackItem)
        mock_feedback_item.id = "found-feedback-item-123"
        
        with patch.object(FeedbackItem, 'from_dict', return_value=mock_feedback_item):
            # Call lookup
            result = FeedbackItem._lookup_feedback_item_by_cache_key(
                self.mock_client, self.test_cache_key
            )
            
            # Verify results
            assert result == mock_feedback_item
            self.mock_client.execute.assert_called_once()

    def test_lookup_returns_none_when_not_found(self):
        """Test that lookup returns None when no item found."""
        # Mock empty GraphQL response
        mock_response = {
            "listFeedbackItemByCacheKey": {
                "items": []
            }
        }
        self.mock_client.execute.return_value = mock_response
        
        # Call lookup
        result = FeedbackItem._lookup_feedback_item_by_cache_key(
            self.mock_client, self.test_cache_key
        )
        
        # Verify results
        assert result is None

    def test_lookup_handles_exception_gracefully(self):
        """Test that lookup handles exceptions gracefully."""
        # Mock the client to raise an exception
        self.mock_client.execute.side_effect = Exception("GraphQL error")
        
        # Call lookup
        result = FeedbackItem._lookup_feedback_item_by_cache_key(
            self.mock_client, self.test_cache_key
        )
        
        # Verify results
        assert result is None


class TestFeedbackItemUpdateFeedbackItem:
    """Test suite for FeedbackItem._update_feedback_item."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_client = Mock(spec=PlexusDashboardClient)
        self.test_feedback_item_id = "test-feedback-item-123"
        self.test_feedback_data = {
            "accountId": "test-account",
            "scoreId": "test-score-789",
            "initialAnswerValue": "Yes"
        }

    def test_update_returns_updated_feedback_item_on_success(self):
        """Test that update returns updated FeedbackItem on success."""
        # Mock successful GraphQL response
        mock_response = {
            "updateFeedbackItem": {
                "id": self.test_feedback_item_id,
                "accountId": "test-account",
                "scoreId": "test-score-789",
                "initialAnswerValue": "Yes"
            }
        }
        self.mock_client.execute.return_value = mock_response
        
        # Mock from_dict to return a FeedbackItem
        mock_feedback_item = Mock(spec=FeedbackItem)
        mock_feedback_item.id = self.test_feedback_item_id
        
        with patch.object(FeedbackItem, 'from_dict', return_value=mock_feedback_item):
            # Call update
            result = FeedbackItem._update_feedback_item(
                self.mock_client, self.test_feedback_item_id, self.test_feedback_data
            )
            
            # Verify results
            assert result == mock_feedback_item
            self.mock_client.execute.assert_called_once()

    def test_update_returns_none_on_failure(self):
        """Test that update returns None on failure."""
        # Mock failed GraphQL response
        mock_response = {
            "updateFeedbackItem": None
        }
        self.mock_client.execute.return_value = mock_response
        
        # Call update
        result = FeedbackItem._update_feedback_item(
            self.mock_client, self.test_feedback_item_id, self.test_feedback_data
        )
        
        # Verify results
        assert result is None

    def test_update_handles_exception_gracefully(self):
        """Test that update handles exceptions gracefully."""
        # Mock the client to raise an exception
        self.mock_client.execute.side_effect = Exception("GraphQL error")
        
        # Call update
        result = FeedbackItem._update_feedback_item(
            self.mock_client, self.test_feedback_item_id, self.test_feedback_data
        )
        
        # Verify results
        assert result is None


class TestFeedbackItemCreateFeedbackItem:
    """Test suite for FeedbackItem._create_feedback_item."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_client = Mock(spec=PlexusDashboardClient)
        self.test_feedback_data = {
            "accountId": "test-account",
            "scoreId": "test-score-789",
            "initialAnswerValue": "Yes"
        }

    def test_create_returns_created_feedback_item_on_success(self):
        """Test that create returns created FeedbackItem on success."""
        # Mock successful creation
        mock_created_item = Mock(spec=FeedbackItem)
        mock_created_item.id = "new-feedback-item-123"
        
        with patch.object(FeedbackItem, 'create', return_value=mock_created_item):
            # Call create
            result = FeedbackItem._create_feedback_item(
                self.mock_client, self.test_feedback_data
            )
            
            # Verify results
            assert result == mock_created_item

    def test_create_returns_none_on_failure(self):
        """Test that create returns None on failure."""
        # Mock failed creation
        with patch.object(FeedbackItem, 'create', return_value=None):
            # Call create
            result = FeedbackItem._create_feedback_item(
                self.mock_client, self.test_feedback_data
            )
            
            # Verify results
            assert result is None

    def test_create_handles_exception_gracefully(self):
        """Test that create handles exceptions gracefully."""
        # Mock the create method to raise an exception
        with patch.object(FeedbackItem, 'create', side_effect=Exception("Creation failed")):
            # Call create
            result = FeedbackItem._create_feedback_item(
                self.mock_client, self.test_feedback_data
            )
            
            # Verify results
            assert result is None


class TestFeedbackItemGenerateCacheKey:
    """Test suite for FeedbackItem.generate_cache_key."""

    def test_generate_cache_key_creates_correct_format(self):
        """Test that generate_cache_key creates the correct format."""
        score_id = "test-score-789"
        form_id = "12345"
        
        result = FeedbackItem.generate_cache_key(score_id, form_id)
        
        assert result == "test-score-789:12345"

    def test_generate_cache_key_handles_different_inputs(self):
        """Test that generate_cache_key handles different input types."""
        # Test with string inputs
        result1 = FeedbackItem.generate_cache_key("abc", "123")
        assert result1 == "abc:123"
        
        # Test with numeric string inputs
        result2 = FeedbackItem.generate_cache_key("789", "456")
        assert result2 == "789:456"


class TestFeedbackItemUpsertIntegration:
    """Integration tests for FeedbackItem upsert functionality."""

    def setup_method(self):
        """Set up test fixtures before each integration test."""
        self.mock_client = Mock(spec=PlexusDashboardClient)
        self.test_account_id = "integration-account-123"
        self.test_scorecard_id = "integration-scorecard-456"
        self.test_score_id = "integration-score-789"
        self.test_form_id = "12345"
        self.test_cache_key = FeedbackItem.generate_cache_key(self.test_score_id, self.test_form_id)

    def test_end_to_end_deduplication_scenario(self):
        """Test end-to-end deduplication scenario."""
        # First call - should create new item
        mock_new_item = Mock()
        mock_new_item.id = "new-feedback-item-123"
        
        # Mock lookup to return None first (no existing item)
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=None):
            with patch.object(FeedbackItem, '_create_feedback_item', return_value=mock_new_item):
                # First upsert call
                feedback_item_id1, was_created1, error1 = FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=self.test_score_id,
                    cache_key=self.test_cache_key,
                    initial_answer_value="Yes",
                    final_answer_value="No"
                )
                
                # Verify first call created new item
                assert feedback_item_id1 == "new-feedback-item-123"
                assert was_created1 is True
                assert error1 is None

        # Second call - should update existing item
        mock_existing_item = Mock()
        mock_existing_item.id = "new-feedback-item-123"  # Same ID as created item
        
        mock_updated_item = Mock()
        mock_updated_item.id = "new-feedback-item-123"
        
        # Mock lookup to return existing item
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=mock_existing_item):
            with patch.object(FeedbackItem, '_update_feedback_item', return_value=mock_updated_item):
                # Second upsert call with same cache key
                feedback_item_id2, was_created2, error2 = FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=self.test_score_id,
                    cache_key=self.test_cache_key,
                    initial_answer_value="Yes",
                    final_answer_value="Yes"  # Changed value
                )
                
                # Verify second call updated existing item
                assert feedback_item_id2 == "new-feedback-item-123"  # Same ID
                assert was_created2 is False  # Was updated, not created
                assert error2 is None

    def test_cache_key_generation_and_usage(self):
        """Test that cache key generation and usage work correctly together."""
        score_id = "test-score-999"
        form_id = "67890"
        
        # Generate cache key
        cache_key = FeedbackItem.generate_cache_key(score_id, form_id)
        assert cache_key == "test-score-999:67890"
        
        # Use generated cache key in upsert
        mock_created_item = Mock()
        mock_created_item.id = "cache-key-test-item"
        
        with patch.object(FeedbackItem, '_lookup_feedback_item_by_cache_key', return_value=None):
            with patch.object(FeedbackItem, '_create_feedback_item', return_value=mock_created_item) as mock_create:
                # Call upsert with generated cache key
                feedback_item_id, was_created, error = FeedbackItem.upsert_by_cache_key(
                    client=self.mock_client,
                    account_id=self.test_account_id,
                    scorecard_id=self.test_scorecard_id,
                    score_id=score_id,
                    cache_key=cache_key
                )
                
                # Verify the cache key was used correctly
                args, kwargs = mock_create.call_args
                data_passed = args[1]
                assert data_passed["cacheKey"] == cache_key
                assert data_passed["scoreId"] == score_id