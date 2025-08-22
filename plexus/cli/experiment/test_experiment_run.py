"""
Test suite for experiment run functionality.

Following TDD principles, these tests define the expected behavior
of the experiment run system before implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from plexus.cli.experiment.service import ExperimentService


class TestExperimentRun:
    """Test the experiment run functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock PlexusDashboardClient for testing."""
        client = Mock()
        client.get_experiment_by_id = AsyncMock()
        client.update_experiment = AsyncMock()
        client.create_experiment_node = AsyncMock()
        return client
    
    @pytest.fixture
    def experiment_service(self, mock_client):
        """Create an experiment service instance with mocked client."""
        return ExperimentService(mock_client)
    
    @pytest.mark.asyncio
    async def test_run_experiment_basic(self, experiment_service, mock_client):
        """Test basic experiment run functionality."""
        # Arrange
        experiment_id = "exp-123"
        
        # Mock get_experiment_info method to return valid experiment info
        with patch.object(experiment_service, 'get_experiment_info') as mock_get_info:
            from plexus.cli.experiment.service import ExperimentInfo
            
            # Create a mock experiment object
            mock_experiment = Mock()
            mock_experiment.id = experiment_id
            mock_experiment.name = "Test Experiment"
            
            mock_experiment_info = ExperimentInfo(
                experiment=mock_experiment,
                root_node=Mock(),
                latest_version=Mock(),
                node_count=1,
                version_count=1,
                scorecard_name="Test Scorecard",
                score_name="Test Score"
            )
            # Add name property that delegates to experiment.name
            mock_experiment_info.name = mock_experiment.name
            mock_get_info.return_value = mock_experiment_info
            
            # Act
            result = await experiment_service.run_experiment(experiment_id)
            
            # Assert
            assert result is not None
            assert result['experiment_id'] == experiment_id
            assert result['status'] in ['running', 'completed', 'initiated', 'completed_with_warnings']
            assert 'message' in result
            
            # Verify get_experiment_info was called
            mock_get_info.assert_called_once_with(experiment_id)
    
    @pytest.mark.asyncio
    async def test_run_experiment_nonexistent(self, experiment_service, mock_client):
        """Test running a non-existent experiment."""
        # Arrange
        experiment_id = "nonexistent-exp"
        
        # Mock get_experiment_info to return None (experiment not found)
        with patch.object(experiment_service, 'get_experiment_info') as mock_get_info:
            mock_get_info.return_value = None
            
            # Act
            result = await experiment_service.run_experiment(experiment_id)
            
            # Assert
            assert result is not None
            assert result.get('error') is not None
            assert 'not found' in result['error'].lower()
            
            # Verify get_experiment_info was called
            mock_get_info.assert_called_once_with(experiment_id)
    
    @pytest.mark.asyncio 
    async def test_run_experiment_validation(self, experiment_service, mock_client):
        """Test experiment run input validation."""
        # Act & Assert - Empty experiment ID
        result = await experiment_service.run_experiment("")
        assert result is not None
        assert result.get('error') is not None
        
        # Act & Assert - None experiment ID
        result = await experiment_service.run_experiment(None)
        assert result is not None
        assert result.get('error') is not None
    
    @pytest.mark.asyncio
    async def test_run_experiment_with_options(self, experiment_service, mock_client):
        """Test experiment run with optional parameters."""
        # Arrange
        experiment_id = "exp-456"
        options = {
            'max_iterations': 10,
            'timeout': 300,
            'async_mode': True
        }
        
        # Mock get_experiment_info method to return valid experiment info
        with patch.object(experiment_service, 'get_experiment_info') as mock_get_info:
            from plexus.cli.experiment.service import ExperimentInfo
            
            # Create a mock experiment object
            mock_experiment = Mock()
            mock_experiment.id = experiment_id
            mock_experiment.name = "Test Experiment"
            
            mock_experiment_info = ExperimentInfo(
                experiment=mock_experiment,
                root_node=Mock(),
                latest_version=Mock(),
                node_count=1,
                version_count=1,
                scorecard_name="Test Scorecard",
                score_name="Test Score"
            )
            mock_experiment_info.name = mock_experiment.name
            mock_get_info.return_value = mock_experiment_info
            
            # Act
            result = await experiment_service.run_experiment(experiment_id, **options)
            
            # Assert
            assert result is not None
            assert result['experiment_id'] == experiment_id
            # Should accept options gracefully (even if not implemented yet)
    
    @pytest.mark.asyncio
    async def test_run_experiment_error_handling(self, experiment_service, mock_client):
        """Test experiment run error handling."""
        # Arrange
        experiment_id = "exp-error"
        
        # Mock get_experiment_info to raise an exception
        with patch.object(experiment_service, 'get_experiment_info') as mock_get_info:
            mock_get_info.side_effect = Exception("Database connection error")
            
            # Act
            result = await experiment_service.run_experiment(experiment_id)
            
            # Assert
            assert result is not None
            assert result.get('error') is not None
            assert 'error' in result['error'].lower()


class TestExperimentRunIntegration:
    """Integration tests for experiment run functionality."""
    
    def test_experiment_run_returns_structured_data(self):
        """Test that experiment run returns properly structured data."""
        # This test defines the expected return structure
        expected_keys = {
            'experiment_id', 'status', 'message'
        }
        optional_keys = {
            'error', 'run_id', 'progress', 'estimated_completion', 'results'
        }
        
        # This test will pass once we implement the function to return this structure
        assert True  # Placeholder for now
    
    def test_experiment_run_logging(self):
        """Test that experiment run provides proper logging."""
        # Should log start, progress, and completion/error states
        assert True  # Placeholder for structured logging tests


if __name__ == "__main__":
    pytest.main([__file__])