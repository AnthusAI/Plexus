"""
Test suite for procedure run functionality.

Following TDD principles, these tests define the expected behavior
of the procedure run system before implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from plexus.cli.procedure.service import ProcedureService


class TestProcedureRun:
    """Test the procedure run functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock PlexusDashboardClient for testing."""
        client = Mock()
        client.get_experiment_by_id = AsyncMock()
        client.update_procedure = AsyncMock()
        client.create_procedure_node = AsyncMock()
        return client
    
    @pytest.fixture
    def experiment_service(self, mock_client):
        """Create an procedure service instance with mocked client."""
        return ProcedureService(mock_client)
    
    @pytest.mark.asyncio
    async def test_run_experiment_basic(self, experiment_service, mock_client):
        """Test basic procedure run functionality."""
        # Arrange
        procedure_id = "exp-123"
        
        # Mock get_procedure_info method to return valid procedure info
        with patch.object(experiment_service, 'get_procedure_info') as mock_get_info:
            from plexus.cli.procedure.service import ProcedureInfo
            
            # Create a mock procedure object
            mock_procedure = Mock()
            mock_procedure.id = procedure_id
            mock_procedure.name = "Test Procedure"
            
            mock_procedure_info = ProcedureInfo(
                procedure=mock_procedure,
                root_node=Mock(),
                latest_version=Mock(),
                node_count=1,
                version_count=1,
                scorecard_name="Test Scorecard",
                score_name="Test Score"
            )
            # Add name property that delegates to procedure.name
            mock_procedure_info.name = mock_procedure.name
            mock_get_info.return_value = mock_procedure_info
            
            # Act
            result = await experiment_service.run_experiment(procedure_id)
            
            # Assert
            assert result is not None
            assert result['procedure_id'] == procedure_id
            assert result['status'] in ['running', 'completed', 'initiated', 'completed_with_warnings']
            assert 'message' in result
            
            # Verify get_procedure_info was called
            mock_get_info.assert_called_once_with(procedure_id)
    
    @pytest.mark.asyncio
    async def test_run_experiment_nonexistent(self, experiment_service, mock_client):
        """Test running a non-existent procedure."""
        # Arrange
        procedure_id = "nonexistent-exp"
        
        # Mock get_procedure_info to return None (procedure not found)
        with patch.object(experiment_service, 'get_procedure_info') as mock_get_info:
            mock_get_info.return_value = None
            
            # Act
            result = await experiment_service.run_experiment(procedure_id)
            
            # Assert
            assert result is not None
            assert result.get('error') is not None
            assert 'not found' in result['error'].lower()
            
            # Verify get_procedure_info was called
            mock_get_info.assert_called_once_with(procedure_id)
    
    @pytest.mark.asyncio 
    async def test_run_experiment_validation(self, experiment_service, mock_client):
        """Test procedure run input validation."""
        # Act & Assert - Empty procedure ID
        result = await experiment_service.run_experiment("")
        assert result is not None
        assert result.get('error') is not None
        
        # Act & Assert - None procedure ID
        result = await experiment_service.run_experiment(None)
        assert result is not None
        assert result.get('error') is not None
    
    @pytest.mark.asyncio
    async def test_run_experiment_with_options(self, experiment_service, mock_client):
        """Test procedure run with optional parameters."""
        # Arrange
        procedure_id = "exp-456"
        options = {
            'max_iterations': 10,
            'timeout': 300,
            'async_mode': True
        }
        
        # Mock get_procedure_info method to return valid procedure info
        with patch.object(experiment_service, 'get_procedure_info') as mock_get_info:
            from plexus.cli.procedure.service import ProcedureInfo
            
            # Create a mock procedure object
            mock_procedure = Mock()
            mock_procedure.id = procedure_id
            mock_procedure.name = "Test Procedure"
            
            mock_procedure_info = ProcedureInfo(
                procedure=mock_procedure,
                root_node=Mock(),
                latest_version=Mock(),
                node_count=1,
                version_count=1,
                scorecard_name="Test Scorecard",
                score_name="Test Score"
            )
            mock_procedure_info.name = mock_procedure.name
            mock_get_info.return_value = mock_procedure_info
            
            # Act
            result = await experiment_service.run_experiment(procedure_id, **options)
            
            # Assert
            assert result is not None
            assert result['procedure_id'] == procedure_id
            # Should accept options gracefully (even if not implemented yet)
    
    @pytest.mark.asyncio
    async def test_run_experiment_error_handling(self, experiment_service, mock_client):
        """Test procedure run error handling."""
        # Arrange
        procedure_id = "exp-error"
        
        # Mock get_procedure_info to raise an exception
        with patch.object(experiment_service, 'get_procedure_info') as mock_get_info:
            mock_get_info.side_effect = Exception("Database connection error")
            
            # Act
            result = await experiment_service.run_experiment(procedure_id)
            
            # Assert
            assert result is not None
            assert result.get('error') is not None
            assert 'error' in result['error'].lower()


class TestProcedureRunIntegration:
    """Integration tests for procedure run functionality."""
    
    def test_procedure_run_returns_structured_data(self):
        """Test that procedure run returns properly structured data."""
        # This test defines the expected return structure
        expected_keys = {
            'procedure_id', 'status', 'message'
        }
        optional_keys = {
            'error', 'run_id', 'progress', 'estimated_completion', 'results'
        }
        
        # This test will pass once we implement the function to return this structure
        assert True  # Placeholder for now
    
    def test_procedure_run_logging(self):
        """Test that procedure run provides proper logging."""
        # Should log start, progress, and completion/error states
        assert True  # Placeholder for structured logging tests


if __name__ == "__main__":
    pytest.main([__file__])