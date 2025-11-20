"""
Tests for feedback_utils module.

Tests the shared utilities for identifying scorecards and scores with feedback items.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta, timezone

from plexus.reports.blocks import feedback_utils
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.feedback_item import FeedbackItem


@pytest.fixture
def mock_api_client():
    """Creates a mock API client."""
    client = MagicMock()
    client.account_id = "test-account-id"
    return client


@pytest.fixture
def sample_scorecards():
    """Creates sample scorecard objects."""
    scorecard1 = MagicMock(spec=Scorecard)
    scorecard1.id = "scorecard-1"
    scorecard1.name = "Test Scorecard 1"
    scorecard1.externalId = "sc1"
    
    scorecard2 = MagicMock(spec=Scorecard)
    scorecard2.id = "scorecard-2"
    scorecard2.name = "Test Scorecard 2"
    scorecard2.externalId = "sc2"
    
    return [scorecard1, scorecard2]


@pytest.fixture
def sample_feedback_items():
    """Creates sample feedback items."""
    items = []
    now = datetime.now(timezone.utc)
    
    for i in range(5):
        item = MagicMock(spec=FeedbackItem)
        item.id = f"feedback-item-{i}"
        item.accountId = "test-account-id"
        item.scorecardId = "scorecard-1"
        item.scoreId = "score-1"
        item.itemId = f"item-{i}"
        item.initialAnswerValue = "Yes" if i % 2 == 0 else "No"
        item.finalAnswerValue = "No"
        item.editedAt = now - timedelta(days=i)
        item.createdAt = now - timedelta(days=i+1)
        item.updatedAt = now - timedelta(days=i)
        items.append(item)
    
    return items


class TestFetchAllScorecards:
    """Tests for fetch_all_scorecards function."""
    
    @pytest.mark.asyncio
    async def test_fetch_all_scorecards_success(self, mock_api_client, sample_scorecards):
        """Test successfully fetching all scorecards."""
        # Mock the GraphQL response
        mock_response = {
            'listScorecards': {
                'items': [
                    {
                        'id': 'scorecard-1',
                        'name': 'Test Scorecard 1',
                        'key': 'sc1',
                        'externalId': 'sc1',
                        'accountId': 'test-account-id',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'updatedAt': '2024-01-01T00:00:00Z'
                    },
                    {
                        'id': 'scorecard-2',
                        'name': 'Test Scorecard 2',
                        'key': 'sc2',
                        'externalId': 'sc2',
                        'accountId': 'test-account-id',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'updatedAt': '2024-01-01T00:00:00Z'
                    }
                ]
            }
        }
        
        mock_api_client.execute = MagicMock(return_value=mock_response)
        
        with patch('plexus.dashboard.api.models.scorecard.Scorecard.from_dict', side_effect=sample_scorecards):
            result = await feedback_utils.fetch_all_scorecards(mock_api_client, "test-account-id")
        
        assert len(result) == 2
        assert result[0].id == "scorecard-1"
        assert result[1].id == "scorecard-2"
        mock_api_client.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_all_scorecards_empty(self, mock_api_client):
        """Test fetching scorecards when none exist."""
        mock_response = {
            'listScorecards': {
                'items': []
            }
        }
        
        mock_api_client.execute = MagicMock(return_value=mock_response)
        
        result = await feedback_utils.fetch_all_scorecards(mock_api_client, "test-account-id")
        
        assert len(result) == 0
        mock_api_client.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_all_scorecards_error(self, mock_api_client):
        """Test handling errors when fetching scorecards."""
        mock_api_client.execute = MagicMock(side_effect=Exception("GraphQL error"))
        
        result = await feedback_utils.fetch_all_scorecards(mock_api_client, "test-account-id")
        
        assert len(result) == 0


class TestFetchScoresForScorecard:
    """Tests for fetch_scores_for_scorecard function."""
    
    @pytest.mark.asyncio
    async def test_fetch_scores_success(self, mock_api_client):
        """Test successfully fetching scores for a scorecard."""
        mock_response = {
            'getScorecard': {
                'id': 'scorecard-1',
                'name': 'Test Scorecard',
                'sections': {
                    'items': [
                        {
                            'id': 'section-1',
                            'scores': {
                                'items': [
                                    {
                                        'id': 'score-1',
                                        'name': 'Score 1',
                                        'externalId': 'ext-1',
                                        'order': 1
                                    },
                                    {
                                        'id': 'score-2',
                                        'name': 'Score 2',
                                        'externalId': 'ext-2',
                                        'order': 2
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
        
        mock_api_client.execute = MagicMock(return_value=mock_response)
        
        result = await feedback_utils.fetch_scores_for_scorecard(mock_api_client, "scorecard-1")
        
        assert len(result) == 2
        assert result[0]['plexus_score_id'] == 'score-1'
        assert result[0]['plexus_score_name'] == 'Score 1'
        assert result[0]['cc_question_id'] == 'ext-1'
        assert result[1]['plexus_score_id'] == 'score-2'
    
    @pytest.mark.asyncio
    async def test_fetch_scores_no_external_ids(self, mock_api_client):
        """Test fetching scores when some don't have externalIds."""
        mock_response = {
            'getScorecard': {
                'id': 'scorecard-1',
                'name': 'Test Scorecard',
                'sections': {
                    'items': [
                        {
                            'id': 'section-1',
                            'scores': {
                                'items': [
                                    {
                                        'id': 'score-1',
                                        'name': 'Score 1',
                                        'externalId': 'ext-1',
                                        'order': 1
                                    },
                                    {
                                        'id': 'score-2',
                                        'name': 'Score 2',
                                        'externalId': None,  # No external ID
                                        'order': 2
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
        
        mock_api_client.execute = MagicMock(return_value=mock_response)
        
        result = await feedback_utils.fetch_scores_for_scorecard(mock_api_client, "scorecard-1")
        
        # Only score with externalId should be returned
        assert len(result) == 1
        assert result[0]['plexus_score_id'] == 'score-1'
    
    @pytest.mark.asyncio
    async def test_fetch_scores_empty(self, mock_api_client):
        """Test fetching scores when scorecard has none."""
        mock_response = {
            'getScorecard': {
                'id': 'scorecard-1',
                'name': 'Test Scorecard',
                'sections': {
                    'items': []
                }
            }
        }
        
        mock_api_client.execute = MagicMock(return_value=mock_response)
        
        result = await feedback_utils.fetch_scores_for_scorecard(mock_api_client, "scorecard-1")
        
        assert len(result) == 0


class TestFetchFeedbackItemsForScore:
    """Tests for fetch_feedback_items_for_score function."""
    
    @pytest.mark.asyncio
    async def test_fetch_feedback_items_with_data(self, mock_api_client, sample_feedback_items):
        """Test successfully fetching feedback items."""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        mock_response = {
            'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt': {
                'items': [
                    {
                        'id': f'feedback-item-{i}',
                        'accountId': 'test-account-id',
                        'scorecardId': 'scorecard-1',
                        'scoreId': 'score-1',
                        'itemId': f'item-{i}',
                        'cacheKey': f'cache-{i}',
                        'initialAnswerValue': 'Yes' if i % 2 == 0 else 'No',
                        'finalAnswerValue': 'No',
                        'initialCommentValue': None,
                        'finalCommentValue': None,
                        'editCommentValue': None,
                        'editedAt': (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                        'editorName': 'Test Editor',
                        'isAgreement': False,
                        'createdAt': (datetime.now(timezone.utc) - timedelta(days=i+1)).isoformat(),
                        'updatedAt': (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                        'item': {
                            'id': f'item-{i}',
                            'identifiers': f'id-{i}',
                            'externalId': f'ext-{i}'
                        }
                    }
                    for i in range(5)
                ],
                'nextToken': None
            }
        }
        
        mock_api_client.execute = MagicMock(return_value=mock_response)
        
        with patch('plexus.dashboard.api.models.feedback_item.FeedbackItem.from_dict', side_effect=sample_feedback_items):
            result = await feedback_utils.fetch_feedback_items_for_score(
                mock_api_client,
                "test-account-id",
                "scorecard-1",
                "score-1",
                start_date,
                end_date
            )
        
        assert len(result) == 5
        assert all(isinstance(item, MagicMock) for item in result)
    
    @pytest.mark.asyncio
    async def test_fetch_feedback_items_no_data(self, mock_api_client):
        """Test fetching feedback items when none exist."""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        mock_response = {
            'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt': {
                'items': [],
                'nextToken': None
            }
        }
        
        mock_api_client.execute = MagicMock(return_value=mock_response)
        
        result = await feedback_utils.fetch_feedback_items_for_score(
            mock_api_client,
            "test-account-id",
            "scorecard-1",
            "score-1",
            start_date,
            end_date
        )
        
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_feedback_items_pagination(self, mock_api_client, sample_feedback_items):
        """Test fetching feedback items with pagination."""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        # First page
        mock_response_page1 = {
            'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt': {
                'items': [
                    {
                        'id': f'feedback-item-{i}',
                        'accountId': 'test-account-id',
                        'scorecardId': 'scorecard-1',
                        'scoreId': 'score-1',
                        'itemId': f'item-{i}',
                        'cacheKey': f'cache-{i}',
                        'initialAnswerValue': 'Yes',
                        'finalAnswerValue': 'No',
                        'initialCommentValue': None,
                        'finalCommentValue': None,
                        'editCommentValue': None,
                        'editedAt': (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                        'editorName': 'Test Editor',
                        'isAgreement': False,
                        'createdAt': (datetime.now(timezone.utc) - timedelta(days=i+1)).isoformat(),
                        'updatedAt': (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                        'item': {
                            'id': f'item-{i}',
                            'identifiers': f'id-{i}',
                            'externalId': f'ext-{i}'
                        }
                    }
                    for i in range(3)
                ],
                'nextToken': 'page2-token'
            }
        }
        
        # Second page
        mock_response_page2 = {
            'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt': {
                'items': [
                    {
                        'id': f'feedback-item-{i}',
                        'accountId': 'test-account-id',
                        'scorecardId': 'scorecard-1',
                        'scoreId': 'score-1',
                        'itemId': f'item-{i}',
                        'cacheKey': f'cache-{i}',
                        'initialAnswerValue': 'No',
                        'finalAnswerValue': 'No',
                        'initialCommentValue': None,
                        'finalCommentValue': None,
                        'editCommentValue': None,
                        'editedAt': (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                        'editorName': 'Test Editor',
                        'isAgreement': True,
                        'createdAt': (datetime.now(timezone.utc) - timedelta(days=i+1)).isoformat(),
                        'updatedAt': (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                        'item': {
                            'id': f'item-{i}',
                            'identifiers': f'id-{i}',
                            'externalId': f'ext-{i}'
                        }
                    }
                    for i in range(3, 5)
                ],
                'nextToken': None
            }
        }
        
        # Mock execute to return different responses based on call count
        mock_api_client.execute = MagicMock(side_effect=[mock_response_page1, mock_response_page2])
        
        with patch('plexus.dashboard.api.models.feedback_item.FeedbackItem.from_dict', side_effect=sample_feedback_items):
            result = await feedback_utils.fetch_feedback_items_for_score(
                mock_api_client,
                "test-account-id",
                "scorecard-1",
                "score-1",
                start_date,
                end_date
            )
        
        assert len(result) == 5
        assert mock_api_client.execute.call_count == 2


class TestIdentifyScorecardsWithFeedback:
    """Tests for identify_scorecards_with_feedback function."""
    
    @pytest.mark.asyncio
    async def test_identify_scorecards_with_feedback_success(self, mock_api_client, sample_scorecards, sample_feedback_items):
        """Test successfully identifying scorecards with feedback."""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        # Mock fetch_all_scorecards
        with patch('plexus.reports.blocks.feedback_utils.fetch_all_scorecards', return_value=sample_scorecards):
            # Mock fetch_scores_for_scorecard
            with patch('plexus.reports.blocks.feedback_utils.fetch_scores_for_scorecard', return_value=[
                {'plexus_score_id': 'score-1', 'plexus_score_name': 'Score 1', 'cc_question_id': 'ext-1'},
                {'plexus_score_id': 'score-2', 'plexus_score_name': 'Score 2', 'cc_question_id': 'ext-2'}
            ]):
                # Mock fetch_feedback_items_for_score - return items for score-1 only
                async def mock_fetch_feedback(api_client, account_id, scorecard_id, score_id, start, end):
                    if score_id == 'score-1':
                        return sample_feedback_items
                    return []
                
                with patch('plexus.reports.blocks.feedback_utils.fetch_feedback_items_for_score', side_effect=mock_fetch_feedback):
                    result = await feedback_utils.identify_scorecards_with_feedback(
                        mock_api_client,
                        "test-account-id",
                        start_date,
                        end_date
                    )
        
        # Should have 2 scorecards, each with 1 score with feedback (score-1)
        assert len(result) == 2
        assert result[0]['scorecard'].id == 'scorecard-1'
        assert len(result[0]['scores_with_feedback']) == 1
        assert result[0]['scores_with_feedback'][0]['score_id'] == 'score-1'
        assert result[0]['scores_with_feedback'][0]['feedback_count'] == 5
    
    @pytest.mark.asyncio
    async def test_identify_scorecards_filters_empty(self, mock_api_client, sample_scorecards):
        """Test that scorecards without feedback are filtered out."""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        # Mock fetch_all_scorecards
        with patch('plexus.reports.blocks.feedback_utils.fetch_all_scorecards', return_value=sample_scorecards):
            # Mock fetch_scores_for_scorecard
            with patch('plexus.reports.blocks.feedback_utils.fetch_scores_for_scorecard', return_value=[
                {'plexus_score_id': 'score-1', 'plexus_score_name': 'Score 1', 'cc_question_id': 'ext-1'}
            ]):
                # Mock fetch_feedback_items_for_score - return empty for all
                with patch('plexus.reports.blocks.feedback_utils.fetch_feedback_items_for_score', return_value=[]):
                    result = await feedback_utils.identify_scorecards_with_feedback(
                        mock_api_client,
                        "test-account-id",
                        start_date,
                        end_date
                    )
        
        # No scorecards should be returned since none have feedback
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_identify_scorecards_no_scorecards(self, mock_api_client):
        """Test when no scorecards exist."""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        # Mock fetch_all_scorecards to return empty list
        with patch('plexus.reports.blocks.feedback_utils.fetch_all_scorecards', return_value=[]):
            result = await feedback_utils.identify_scorecards_with_feedback(
                mock_api_client,
                "test-account-id",
                start_date,
                end_date
            )
        
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_identify_scorecards_date_filtering(self, mock_api_client, sample_scorecards, sample_feedback_items):
        """Test that date filtering is properly applied."""
        # Use a narrow date range that should filter out some items
        start_date = datetime.now(timezone.utc) - timedelta(days=2)
        end_date = datetime.now(timezone.utc)
        
        # Mock fetch_all_scorecards
        with patch('plexus.reports.blocks.feedback_utils.fetch_all_scorecards', return_value=[sample_scorecards[0]]):
            # Mock fetch_scores_for_scorecard
            with patch('plexus.reports.blocks.feedback_utils.fetch_scores_for_scorecard', return_value=[
                {'plexus_score_id': 'score-1', 'plexus_score_name': 'Score 1', 'cc_question_id': 'ext-1'}
            ]):
                # Mock fetch_feedback_items_for_score - return only recent items (first 2)
                with patch('plexus.reports.blocks.feedback_utils.fetch_feedback_items_for_score', return_value=sample_feedback_items[:2]):
                    result = await feedback_utils.identify_scorecards_with_feedback(
                        mock_api_client,
                        "test-account-id",
                        start_date,
                        end_date
                    )
        
        assert len(result) == 1
        assert result[0]['scores_with_feedback'][0]['feedback_count'] == 2



