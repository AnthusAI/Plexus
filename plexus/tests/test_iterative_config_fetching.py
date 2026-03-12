#!/usr/bin/env python3

"""
Unit tests for iterative_config_fetching.py

Tests the dependency resolution and iterative configuration fetching functionality
that loads scorecards from the API with proper dependency discovery.
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Add the plexus module to the path for testing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from plexus.cli.shared.iterative_config_fetching import iteratively_fetch_configurations
from plexus.cli.shared.dependency_discovery import build_name_id_mappings


class TestIterativeConfigFetching:
    """Test cases for iterative configuration fetching with dependency resolution."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Mock scorecard data
        self.mock_scorecard_data = {
            'id': 'test-scorecard-id',
            'name': 'Test Scorecard',
            'key': 'test-scorecard'
        }
        
        # Mock target scores
        self.mock_target_scores = [
            {
                'id': 'score-with-deps-id',
                'name': 'Score With Dependencies',
                'key': 'score-with-deps',
                'championVersionId': 'version-1'
            }
        ]
        
        # Mock dependency scores
        self.mock_dependency_scores = [
            {
                'id': 'dependency-score-id',
                'name': 'Dependency Score',
                'key': 'dependency-score',
                'championVersionId': 'version-2'
            }
        ]
        
        # Mock complete scorecard structure (for dependency resolution)
        self.mock_complete_structure = {
            'getScorecard': {
                'id': 'test-scorecard-id',
                'name': 'Test Scorecard',
                'sections': {
                    'items': [
                        {
                            'id': 'section-1',
                            'name': 'Test Section',
                            'scores': {
                                'items': self.mock_target_scores + self.mock_dependency_scores
                            }
                        }
                    ]
                }
            }
        }
        
        # Mock score configurations (YAML content)
        self.mock_score_config_with_deps = """
name: Score With Dependencies
id: score-with-deps-id
class: TestScore
depends_on:
  - Dependency Score
model: test-model
"""
        
        self.mock_dependency_config = """
name: Dependency Score
id: dependency-score-id
class: TestScore
model: test-model
"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock GraphQL client."""
        client = Mock()
        session = Mock()
        client.__enter__ = Mock(return_value=session)
        client.__exit__ = Mock(return_value=None)
        
        # Mock the complete structure query response
        session.execute.return_value = self.mock_complete_structure
        
        return client

    @pytest.fixture  
    def mock_fetch_configurations(self):
        """Mock the fetch_score_configurations function."""
        with patch('plexus.cli.iterative_config_fetching.fetch_score_configurations') as mock:
            # Return configurations based on which scores are requested
            def side_effect(client, scorecard_data, scores, cache_status, use_cache=False):
                configs = {}
                for score in scores:
                    score_id = score.get('id')
                    if score_id == 'score-with-deps-id':
                        configs[score_id] = self.mock_score_config_with_deps
                    elif score_id == 'dependency-score-id':
                        configs[score_id] = self.mock_dependency_config
                return configs
            
            mock.side_effect = side_effect
            yield mock

    @pytest.fixture
    def mock_check_cache(self):
        """Mock the check_local_score_cache function."""
        with patch('plexus.cli.iterative_config_fetching.check_local_score_cache') as mock:
            # Return that nothing is cached by default
            mock.return_value = {}
            yield mock

    def test_basic_dependency_resolution(self, mock_client, mock_fetch_configurations, mock_check_cache):
        """Test that dependencies are correctly discovered and fetched."""
        
        # Run the iterative fetching
        result = iteratively_fetch_configurations(
            mock_client,
            self.mock_scorecard_data,
            self.mock_target_scores,
            use_cache=False
        )
        
        # Verify results
        assert len(result) == 2, "Should have fetched both target score and its dependency"
        assert 'score-with-deps-id' in result, "Should have target score configuration"
        assert 'dependency-score-id' in result, "Should have dependency score configuration"
        
        # Verify content
        assert 'Score With Dependencies' in result['score-with-deps-id']
        assert 'Dependency Score' in result['dependency-score-id']
        
        # Verify fetch_score_configurations was called twice (once per iteration)
        assert mock_fetch_configurations.call_count == 2

    def test_complete_structure_fetching(self, mock_client, mock_fetch_configurations, mock_check_cache):
        """Test that complete scorecard structure is fetched for dependency resolution."""
        
        iteratively_fetch_configurations(
            mock_client,
            self.mock_scorecard_data,
            self.mock_target_scores,
            use_cache=False
        )
        
        # Verify the complete structure query was executed
        mock_client.__enter__.return_value.execute.assert_called()
        
        # Verify that complete structure query was made by checking call count
        # The function should call the client twice: once for complete structure, once for detailed structure
        assert mock_client.__enter__.return_value.execute.call_count >= 1

    def test_name_to_id_mapping_building(self):
        """Test that name-to-ID mappings are built correctly."""
        
        all_scores = self.mock_target_scores + self.mock_dependency_scores
        id_to_name, name_to_id = build_name_id_mappings(all_scores)
        
        # Verify mappings
        assert len(name_to_id) == 2
        assert name_to_id['Score With Dependencies'] == 'score-with-deps-id'
        assert name_to_id['Dependency Score'] == 'dependency-score-id'
        
        assert len(id_to_name) == 2
        assert id_to_name['score-with-deps-id'] == 'Score With Dependencies'
        assert id_to_name['dependency-score-id'] == 'Dependency Score'

    def test_cache_utilization(self, mock_client, mock_fetch_configurations, mock_check_cache):
        """Test that local cache is properly utilized when use_cache=True."""
        
        # Mock that dependency score is cached
        mock_check_cache.return_value = {'dependency-score-id': True}
        
        result = iteratively_fetch_configurations(
            mock_client,
            self.mock_scorecard_data,
            self.mock_target_scores,
            use_cache=True
        )
        
        # Should still get both configurations
        assert len(result) == 2
        
        # Verify cache check was called
        mock_check_cache.assert_called()

    def test_no_dependencies_case(self, mock_client, mock_fetch_configurations, mock_check_cache):
        """Test behavior when target score has no dependencies."""
        
        # Create a score without dependencies
        no_deps_score = [{
            'id': 'no-deps-id',
            'name': 'No Dependencies Score', 
            'key': 'no-deps',
            'championVersionId': 'version-3'
        }]
        
        no_deps_config = """
name: No Dependencies Score
id: no-deps-id
class: TestScore
model: test-model
"""
        
        # Mock fetch to return config without dependencies
        def no_deps_side_effect(client, scorecard_data, scores, cache_status, use_cache=False):
            return {'no-deps-id': no_deps_config}
        
        mock_fetch_configurations.side_effect = no_deps_side_effect
        
        result = iteratively_fetch_configurations(
            mock_client,
            self.mock_scorecard_data,
            no_deps_score,
            use_cache=False
        )
        
        # Should only have one score
        assert len(result) == 1
        assert 'no-deps-id' in result
        
        # Should only call fetch once (no second iteration needed)
        assert mock_fetch_configurations.call_count == 1

    def test_error_handling_invalid_structure(self, mock_client, mock_fetch_configurations, mock_check_cache):
        """Test error handling when complete structure fetch fails."""
        
        # Mock client to raise exception on structure fetch
        mock_client.__enter__.return_value.execute.side_effect = Exception("API Error")
        
        # Should not raise exception but continue with partial mappings
        result = iteratively_fetch_configurations(
            mock_client,
            self.mock_scorecard_data,
            self.mock_target_scores,
            use_cache=False
        )
        
        # Should still work with limited functionality
        assert isinstance(result, dict)

    def test_circular_dependency_prevention(self, mock_client, mock_fetch_configurations, mock_check_cache):
        """Test that circular dependencies don't cause infinite loops."""
        
        # Create circular dependency configs
        circular_config_a = """
name: Score A
id: score-a-id
class: TestScore
depends_on:
  - Score B
"""
        
        circular_config_b = """
name: Score B  
id: score-b-id
class: TestScore
depends_on:
  - Score A
"""
        
        def circular_side_effect(client, scorecard_data, scores, cache_status, use_cache=False):
            configs = {}
            for score in scores:
                score_id = score.get('id')
                if score_id == 'score-a-id':
                    configs[score_id] = circular_config_a
                elif score_id == 'score-b-id':
                    configs[score_id] = circular_config_b
            return configs
        
        mock_fetch_configurations.side_effect = circular_side_effect
        
        # Set up circular dependency scores
        circular_scores = [{'id': 'score-a-id', 'name': 'Score A', 'championVersionId': 'v1'}]
        
        # Mock complete structure to include both scores
        mock_client.__enter__.return_value.execute.return_value = {
            'getScorecard': {
                'sections': {
                    'items': [{
                        'scores': {
                            'items': [
                                {'id': 'score-a-id', 'name': 'Score A', 'championVersionId': 'v1'},
                                {'id': 'score-b-id', 'name': 'Score B', 'championVersionId': 'v2'}
                            ]
                        }
                    }]
                }
            }
        }
        
        # Should complete without infinite loop due to max iterations limit
        result = iteratively_fetch_configurations(
            mock_client,
            self.mock_scorecard_data,
            circular_scores,
            use_cache=False
        )
        
        # Should have processed configurations (limited by max iterations)
        assert isinstance(result, dict)


class TestRealWorldScenario:
    """Integration-style tests that simulate real scorecard scenarios."""

    @pytest.mark.asyncio
    async def test_presumed_acceptance_scenario(self):
        """Test the real Presumed Acceptance -> Campaign Name dependency scenario."""
        
        # This test simulates the exact scenario that was failing before the fix
        mock_scorecard = {
            'id': 'andersen-windows-id',
            'name': 'Andersen Windows IB Sales'
        }
        
        mock_target_scores = [{
            'id': '45341',
            'name': 'Presumed Acceptance',
            'championVersionId': 'version-1'
        }]
        
        presumed_acceptance_config = """
name: Presumed Acceptance
id: 45341
class: LangGraphScore
depends_on:
  - Campaign Name
model: test-model
"""
        
        campaign_name_config = """
name: Campaign Name  
id: 45333
class: LangGraphScore
model: test-model
"""
        
        # Mock client
        mock_client = Mock()
        mock_session = Mock()
        mock_client.__enter__ = Mock(return_value=mock_session)
        mock_client.__exit__ = Mock(return_value=None)
        
        # Mock complete structure response
        mock_session.execute.return_value = {
            'getScorecard': {
                'sections': {
                    'items': [{
                        'scores': {
                            'items': [
                                {'id': '45341', 'name': 'Presumed Acceptance', 'championVersionId': 'v1'},
                                {'id': '45333', 'name': 'Campaign Name', 'championVersionId': 'v2'}
                            ]
                        }
                    }]
                }
            }
        }
        
        # Mock fetch configurations  
        with patch('plexus.cli.iterative_config_fetching.fetch_score_configurations') as mock_fetch:
            def fetch_side_effect(client, scorecard_data, scores, cache_status, use_cache=False):
                configs = {}
                for score in scores:
                    score_id = score.get('id')
                    if score_id == '45341':
                        configs[score_id] = presumed_acceptance_config
                    elif score_id == '45333':
                        configs[score_id] = campaign_name_config
                return configs
            
            mock_fetch.side_effect = fetch_side_effect
            
            # Mock cache check
            with patch('plexus.cli.iterative_config_fetching.check_local_score_cache') as mock_cache:
                mock_cache.return_value = {}
                
                # Run the function
                result = iteratively_fetch_configurations(
                    mock_client,
                    mock_scorecard,
                    mock_target_scores,
                    use_cache=False
                )
                
                # Verify both scores were fetched
                assert len(result) == 2
                assert '45341' in result  # Presumed Acceptance
                assert '45333' in result  # Campaign Name
                
                # Verify configurations contain expected content
                assert 'Presumed Acceptance' in result['45341']
                assert 'Campaign Name' in result['45333']
                assert 'depends_on' in result['45341']


if __name__ == '__main__':
    pytest.main([__file__])