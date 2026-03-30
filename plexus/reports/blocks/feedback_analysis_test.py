import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import yaml

from plexus.reports.blocks.feedback_analysis import FeedbackAnalysis
from plexus.dashboard.api.models.feedback_item import FeedbackItem


def parse_yaml_output(output):
    """Helper function to parse YAML output from FeedbackAnalysis."""
    if isinstance(output, dict):
        # Already a dictionary (error case)
        return output
    elif isinstance(output, str):
        # YAML string - need to parse it
        # Remove the comment header and parse the YAML content
        lines = output.split('\n')
        yaml_start = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('#'):
                yaml_start = i
                break
        yaml_content = '\n'.join(lines[yaml_start:])
        return yaml.safe_load(yaml_content)
    else:
        return None


@pytest.fixture
def mock_api_client():
    """Creates a mock API client."""
    client = MagicMock()
    client.account_id = "test-account-id"
    
    # Create a side_effect function to handle different queries
    def mock_execute(query, variables=None):
        # Handle scorecard lookup query (for get_by_external_id)
        if 'getScorecard' in query and variables and 'externalId' in variables:
            return {
                'getScorecard': {
                    'id': 'test-scorecard-id',
                    'name': 'Test Scorecard',
                    'externalId': variables['externalId']
                }
            }
        # Handle scorecard sections and scores query
        elif 'getScorecard' in query and variables and 'scorecardId' in variables:
            return {
                'getScorecard': {
                    'id': 'test-scorecard-id',
                    'name': 'Test Scorecard',
                    'sections': {
                        'items': [
                            {
                                'id': 'section-1',
                                'scores': {
                                    'items': [
                                        {
                                            'id': 'score1',
                                            'name': 'Score 1',
                                            'externalId': 'score1',
                                            'order': 1
                                        },
                                        {
                                            'id': 'score2',
                                            'name': 'Score 2',
                                            'externalId': 'score2',
                                            'order': 2
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        # Default fallback
        else:
            return {
                'getScorecard': {
                    'id': 'test-scorecard-id',
                    'name': 'Test Scorecard'
                }
            }
    
    # Set up the execute method with side_effect
    client.execute.side_effect = mock_execute
    
    return client


@pytest.fixture
def mock_feedback_items():
    """Creates mock feedback items for testing."""
    items = []
    
    # Create 10 items for score1 - 3 mismatches (70% agreement)
    for i in range(10):
        is_mismatch = i < 3  # 3 out of 10 are mismatches
        item = MagicMock(spec=FeedbackItem)
        item.id = f"item-score1-{i}"
        item.accountId = "test-account-id"
        item.scorecardId = "test-scorecard-id"
        item.scoreId = "score1"
        item.externalId = f"form-{i}"
        item.initialAnswerValue = "Yes" if is_mismatch else "No"
        item.finalAnswerValue = "No" if is_mismatch else "No"
        item.isMismatch = is_mismatch
        
        # Add timestamp attributes with timezone-aware timestamps within the test range
        now = datetime.now(timezone.utc)
        item.updatedAt = now - timedelta(days=5)  # Within the default 14 days
        item.createdAt = now - timedelta(days=10)  # Created earlier
        item.editedAt = None  # Not edited
        
        items.append(item)
    
    # Create 5 items for score2 - 1 mismatch (80% agreement)
    for i in range(5):
        is_mismatch = i < 1  # 1 out of 5 is a mismatch
        item = MagicMock(spec=FeedbackItem)
        item.id = f"item-score2-{i}"
        item.accountId = "test-account-id"
        item.scorecardId = "test-scorecard-id"
        item.scoreId = "score2"
        item.externalId = f"form-{i+10}"
        item.initialAnswerValue = "Good" if is_mismatch else "Better"
        item.finalAnswerValue = "Better" if is_mismatch else "Better"
        item.isMismatch = is_mismatch
        
        # Add timestamp attributes with timezone-aware timestamps within the test range
        now = datetime.now(timezone.utc)
        item.updatedAt = now - timedelta(days=5)  # Within the default 14 days
        item.createdAt = now - timedelta(days=10)  # Created earlier
        item.editedAt = None  # Not edited
        
        items.append(item)
    
    return items


class TestFeedbackAnalysis:
    """Tests for the FeedbackAnalysis class."""
    
    @pytest.mark.asyncio
    async def test_generate_with_data(self, mock_api_client, mock_feedback_items):
        """Tests generating a report with mock feedback data."""
        
        # Create the block with required configuration
        config = {
            "scorecard": "test-scorecard-id",
            "days": 14
        }
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Mock Scorecard get_by_external_id
        with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_external_id', return_value=MagicMock(id="test-scorecard-id", name="Test Scorecard")):
            # Mock _fetch_feedback_items_for_score to return filtered items based on score
            def mock_fetch_items(plexus_scorecard_id, plexus_score_id, start_date=None, end_date=None):
                # Filter items by the requested score ID
                return [item for item in mock_feedback_items if item.scoreId == plexus_score_id]
            
            with patch.object(block, '_fetch_feedback_items_for_score', side_effect=mock_fetch_items):
                # Call the generate method
                output, logs = await block.generate()
                
                # Parse the YAML output
                parsed_output = parse_yaml_output(output)
                
                # Verify the output
                assert parsed_output is not None
                assert "overall_ac1" in parsed_output
                assert "scores" in parsed_output
                
                # Now with proper filtering: score1 has 10 items, score2 has 5 items = 15 total
                assert parsed_output["total_items"] == 15
                assert parsed_output["total_mismatches"] == 4  # 3 mismatches for score1 + 1 mismatch for score2
                
                # Check that AC1 values are reasonable
                assert parsed_output["overall_ac1"] is not None
                assert isinstance(parsed_output["overall_ac1"], float)
                
                # Verify logs were generated
                assert logs is not None
                assert "Starting FeedbackAnalysis block generation" in logs
    
    @pytest.mark.asyncio
    async def test_generate_with_no_data(self, mock_api_client):
        """Tests generating a report with no feedback data."""
        
        # Create the block with required configuration
        config = {
            "scorecard": "test-scorecard-id",
            "days": 14
        }
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Mock Scorecard get_by_external_id
        with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_external_id', return_value=MagicMock(id="test-scorecard-id", name="Test Scorecard")):
            # Mock _fetch_feedback_items_for_score to return empty list
            with patch.object(block, '_fetch_feedback_items_for_score', return_value=[]):
                # Call the generate method
                output, logs = await block.generate()
                
                # Parse the YAML output
                parsed_output = parse_yaml_output(output)
                
                # Verify the output shows empty results
                assert parsed_output is not None
                assert parsed_output["overall_ac1"] is None
                assert len(parsed_output["scores"]) > 0  # Expect empty score objects, not an empty list
                assert all(s["item_count"] == 0 for s in parsed_output["scores"])  # All scores should have 0 items
                assert parsed_output["total_items"] == 0
                
                # Verify logs were generated
                assert logs is not None
                # Updated to match actual log message
                assert "No date-filtered items available for overall analysis" in logs
    
    @pytest.mark.asyncio
    async def test_generate_with_missing_config(self, mock_api_client):
        """Tests generating a report with missing required configuration."""
        
        # Create the block with missing scorecard config
        config = {
            "days": 14
        }
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Call the generate method and check that it returns an error structure
        output, logs = await block.generate()
        
        # For error cases, output should be a dictionary (not YAML)
        assert output is not None
        assert isinstance(output, dict)
        assert "error" in output
        assert "'scorecard' is required in the block configuration." in output["error"]
        
        # Verify logs were generated
        assert logs is not None
        assert "Configuration or Value Error: 'scorecard' is required in the block configuration." in logs
    
    def test_analyze_feedback_data_gwet(self, mock_api_client, mock_feedback_items):
        """Tests the _analyze_feedback_data_gwet method directly."""
        
        # Create the block
        config = {"scorecard": "test-scorecard-id"}
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Call the _analyze_feedback_data_gwet method
        results = block._analyze_feedback_data_gwet(mock_feedback_items, "test-score")
        
        # Verify results
        assert results is not None
        assert "ac1" in results
        assert results["ac1"] is not None
        assert "item_count" in results
        assert "mismatches" in results
        assert results["mismatches"] == 4
        assert results["item_count"] == 15


class TestEnrichedExemplars:
    """Tests that mismatch tuples carry initialAnswerValue / finalAnswerValue
    through to the memories structure."""

    def _make_fi(self, score_id, initial, final, edit_comment,
                 item_id="item-1", fi_id="fi-1"):
        fi = MagicMock(spec=FeedbackItem)
        fi.id = fi_id
        fi.itemId = item_id
        fi.scoreId = score_id
        fi.accountId = "acct-1"
        fi.scorecardId = "sc-1"
        fi.initialAnswerValue = initial
        fi.finalAnswerValue = final
        fi.editCommentValue = edit_comment
        fi.finalCommentValue = None
        fi.editedAt = None
        fi.updatedAt = None
        fi.createdAt = None
        return fi

    def test_mismatch_tuple_includes_answer_values(self):
        """The tuple appended to score_edit_comments must include positions [5] and [6]."""
        from datetime import datetime, timezone, timedelta

        fi = self._make_fi(
            score_id="score-1",
            initial="Yes",
            final="No",
            edit_comment="agent missed this",
        )
        fi.editedAt = datetime.now(timezone.utc) - timedelta(days=5)

        # Re-run the same construction logic used in feedback_analysis.py
        score_edit_comments = []
        for mfi in [fi]:
            _raw = mfi.editCommentValue or mfi.finalCommentValue or ""
            text = _raw.strip() if isinstance(_raw, str) else ""
            if text:
                score_edit_comments.append((
                    mfi.id or mfi.itemId or "",
                    text,
                    mfi.itemId,
                    mfi.editedAt,
                    mfi.id,
                    mfi.initialAnswerValue,
                    mfi.finalAnswerValue,
                ))

        assert len(score_edit_comments) == 1
        tup = score_edit_comments[0]
        assert tup[1] == "agent missed this"
        assert tup[5] == "Yes"   # initialAnswerValue
        assert tup[6] == "No"    # finalAnswerValue

    @pytest.mark.asyncio
    async def test_exemplar_stores_answer_values(self):
        """_run_memory_analysis must store initial/final answer values on exemplar dicts."""
        import numpy as np

        config = {
            "scorecard": "sc-1",
            "days": 30,
            "memory_llm_labels": False,
            "memory_causal_inference": False,
        }
        block = FeedbackAnalysis(config, {}, MagicMock())
        block.report_block_id = None

        score_data = {
            "score_id": "score-1",
            "score_name": "Test Score",
            "items": [
                ("fi-0", "agent did not do X",     "item-0", None, "fi-0", "Yes", "No"),
                ("fi-1", "agent forgot to verify", "item-1", None, "fi-1", "Yes", "No"),
                ("fi-2", "missing confirmation",   "item-2", None, "fi-2", "No",  "Yes"),
            ],
        }

        mock_embedder = MagicMock(return_value=np.random.rand(3, 8))
        mock_clusterer = MagicMock()
        mock_clusterer.cluster.return_value = (np.array([0, 0, 0]), None)
        mock_clusterer.get_keywords.return_value = ["verify", "agent"]
        mock_clusterer.get_representative_exemplars.return_value = [
            (0, "agent did not do X"),
            (1, "agent forgot to verify"),
        ]

        async def fake_identifiers(client, item_id):
            return [{"url": f"https://example.com/r/{item_id}"}]

        with patch("biblicus.analysis.reinforcement_memory.sentence_transformer_embedder",
                   return_value=mock_embedder), \
             patch("biblicus.analysis.reinforcement_memory._clusterer.TopicClusterer",
                   return_value=mock_clusterer), \
             patch("plexus.reports.blocks.feedback_analysis.fetch_item_identifiers",
                   side_effect=fake_identifiers):
            result = await block._run_memory_analysis([score_data])

        assert result is not None
        exemplars = result["scores"][0]["topics"][0]["exemplars"]
        assert len(exemplars) >= 1
        for ex in exemplars:
            assert "initial_answer_value" in ex, f"Missing initial_answer_value: {ex}"
            assert "final_answer_value" in ex, f"Missing final_answer_value: {ex}"
            assert ex["initial_answer_value"] in ("Yes", "No")
            assert ex["final_answer_value"] in ("Yes", "No")