"""
Test suite for Score model.

Tests all lookup methods and data handling for the Score model.
"""
import pytest
from unittest.mock import Mock
from .score import Score


@pytest.fixture
def mock_client():
    """Create a mock API client."""
    return Mock()


@pytest.fixture
def sample_score_data():
    """Sample score data for testing."""
    return {
        'id': 'score-123',
        'name': 'Test Score',
        'key': 'test-score',
        'externalId': '0',
        'type': 'classification',
        'order': 1,
        'sectionId': 'section-456',
        'accuracy': 0.95,
        'version': '1.0.0',
        'aiProvider': 'openai',
        'aiModel': 'gpt-4'
    }


@pytest.fixture
def sample_score(mock_client, sample_score_data):
    """Create a sample Score instance."""
    return Score.from_dict(sample_score_data, mock_client)


class TestScoreFromDict:
    """Test Score.from_dict() method."""
    
    def test_from_dict_with_all_fields(self, mock_client, sample_score_data):
        """Test creating a Score from dict with all fields."""
        score = Score.from_dict(sample_score_data, mock_client)
        
        assert score.id == sample_score_data['id']
        assert score.name == sample_score_data['name']
        assert score.key == sample_score_data['key']
        assert score.externalId == sample_score_data['externalId']
        assert score.type == sample_score_data['type']
        assert score.order == sample_score_data['order']
        assert score.sectionId == sample_score_data['sectionId']
        assert score.accuracy == sample_score_data['accuracy']
        assert score.version == sample_score_data['version']
        assert score.aiProvider == sample_score_data['aiProvider']
        assert score.aiModel == sample_score_data['aiModel']
    
    def test_from_dict_with_optional_fields_missing(self, mock_client):
        """Test creating a Score with only required fields."""
        minimal_data = {
            'id': 'score-123',
            'name': 'Test Score',
            'key': 'test-score',
            'externalId': '0',
            'type': 'classification',
            'order': 1,
            'sectionId': 'section-456'
        }
        
        score = Score.from_dict(minimal_data, mock_client)
        
        assert score.id == minimal_data['id']
        assert score.name == minimal_data['name']
        assert score.accuracy is None
        assert score.version is None
        assert score.aiProvider is None
        assert score.aiModel is None


class TestScoreGetById:
    """Test Score.get_by_id() method."""
    
    def test_get_by_id_success(self, mock_client, sample_score_data):
        """Test successfully getting a score by ID."""
        mock_client.execute.return_value = {
            'getScore': sample_score_data
        }
        
        score = Score.get_by_id('score-123', mock_client)
        
        assert score.id == sample_score_data['id']
        assert score.name == sample_score_data['name']
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'getScore' in query
        assert variables == {'id': 'score-123'}
    
    def test_get_by_id_not_found(self, mock_client):
        """Test get_by_id when score doesn't exist."""
        mock_client.execute.side_effect = Exception("Failed to get Score score-999")
        
        with pytest.raises(Exception):
            Score.get_by_id('score-999', mock_client)


class TestScoreGetByName:
    """Test Score.get_by_name() method."""
    
    def test_get_by_name_success(self, mock_client, sample_score_data):
        """Test successfully getting a score by name."""
        mock_client.execute.return_value = {
            'listScoreByName': {
                'items': [sample_score_data]
            }
        }
        
        score = Score.get_by_name('Test Score', 'scorecard-123', mock_client)
        
        assert score is not None
        assert score.name == 'Test Score'
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        
        assert 'listScoreByName' in query
    
    def test_get_by_name_not_found(self, mock_client):
        """Test get_by_name when score doesn't exist."""
        mock_client.execute.return_value = {
            'listScoreByName': {
                'items': []
            }
        }
        
        score = Score.get_by_name('Nonexistent Score', 'scorecard-123', mock_client)
        
        assert score is None


class TestScoreGetByKey:
    """Test Score.get_by_key() method."""
    
    def test_get_by_key_success(self, mock_client, sample_score_data):
        """Test successfully getting a score by key."""
        mock_client.execute.return_value = {
            'listScoreByKey': {
                'items': [sample_score_data]
            }
        }
        
        score = Score.get_by_key('test-score', 'scorecard-123', mock_client)
        
        assert score is not None
        assert score.key == 'test-score'
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        
        assert 'listScoreByKey' in query
    
    def test_get_by_key_not_found(self, mock_client):
        """Test get_by_key when score doesn't exist."""
        mock_client.execute.return_value = {
            'listScoreByKey': {
                'items': []
            }
        }
        
        score = Score.get_by_key('nonexistent-key', 'scorecard-123', mock_client)
        
        assert score is None


class TestScoreGetByExternalId:
    """Test Score.get_by_external_id() method."""
    
    def test_get_by_external_id_success(self, mock_client, sample_score_data):
        """Test successfully getting a score by external ID."""
        mock_client.execute.return_value = {
            'listScoreByExternalId': {
                'items': [sample_score_data]
            }
        }
        
        score = Score.get_by_external_id('0', 'scorecard-123', mock_client)
        
        assert score is not None
        assert score.externalId == '0'
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'listScoreByExternalId' in query
        assert variables == {'externalId': '0'}
    
    def test_get_by_external_id_not_found(self, mock_client):
        """Test get_by_external_id when score doesn't exist."""
        mock_client.execute.return_value = {
            'listScoreByExternalId': {
                'items': []
            }
        }
        
        score = Score.get_by_external_id('999', 'scorecard-123', mock_client)
        
        assert score is None
    
    def test_get_by_external_id_empty_result(self, mock_client):
        """Test get_by_external_id with empty result."""
        mock_client.execute.return_value = None
        
        score = Score.get_by_external_id('0', 'scorecard-123', mock_client)
        
        assert score is None


class TestScoreGetByScorecardAndExternalId:
    """Test Score.get_by_scorecard_and_external_id() method."""
    
    def test_get_by_scorecard_and_external_id_success(self, mock_client):
        """Test successfully getting a score by scorecard ID and external ID."""
        mock_client.execute.return_value = {
            'listScoreByScorecardIdAndExternalId': {
                'items': [
                    {
                        'id': 'score-123',
                        'name': 'Test Score'
                    }
                ]
            }
        }
        
        result = Score.get_by_scorecard_and_external_id('scorecard-456', '0', mock_client)
        
        assert result is not None
        assert result['id'] == 'score-123'
        assert result['name'] == 'Test Score'
        
        # Verify the query was called correctly
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]
        
        assert 'listScoreByScorecardIdAndExternalId' in query
        assert variables == {
            'scorecardId': 'scorecard-456',
            'externalId': '0'
        }
    
    def test_get_by_scorecard_and_external_id_not_found(self, mock_client):
        """Test get_by_scorecard_and_external_id when score doesn't exist."""
        mock_client.execute.return_value = {
            'listScoreByScorecardIdAndExternalId': {
                'items': []
            }
        }
        
        result = Score.get_by_scorecard_and_external_id('scorecard-456', '999', mock_client)
        
        assert result is None
    
    def test_get_by_scorecard_and_external_id_uses_gsi(self, mock_client):
        """Test that get_by_scorecard_and_external_id uses the correct GSI."""
        mock_client.execute.return_value = {
            'listScoreByScorecardIdAndExternalId': {
                'items': [{'id': 'score-123', 'name': 'Test'}]
            }
        }
        
        Score.get_by_scorecard_and_external_id('scorecard-456', '0', mock_client)
        
        # Verify it uses the GSI query with limit
        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        
        assert 'listScoreByScorecardIdAndExternalId' in query
        assert 'limit: 1' in query
        assert 'scorecardId: $scorecardId' in query
        assert 'externalId: {eq: $externalId}' in query
    
    def test_get_by_scorecard_and_external_id_returns_dict_format(self, mock_client):
        """Test that the method returns the expected dict format."""
        mock_client.execute.return_value = {
            'listScoreByScorecardIdAndExternalId': {
                'items': [
                    {
                        'id': 'score-123',
                        'name': 'My Score',
                        'extraField': 'ignored'  # Extra fields should be preserved
                    }
                ]
            }
        }
        
        result = Score.get_by_scorecard_and_external_id('scorecard-456', '0', mock_client)
        
        # Returns the raw dict with id and name (and any other fields)
        assert isinstance(result, dict)
        assert 'id' in result
        assert 'name' in result
        assert result['id'] == 'score-123'
        assert result['name'] == 'My Score'


class TestScoreListBySectionId:
    """Test Score.list_by_section_id() method."""
    
    def test_list_by_section_id_success(self, mock_client, sample_score_data):
        """Test successfully listing scores by section ID."""
        mock_client.execute.return_value = {
            'listScoreBySectionId': {
                'items': [sample_score_data],
                'nextToken': None
            }
        }
        
        result = Score.list_by_section_id('section-456', mock_client)
        
        assert 'items' in result
        assert len(result['items']) == 1
        assert isinstance(result['items'][0], Score)
        assert result['items'][0].id == 'score-123'
        assert result['nextToken'] is None
    
    def test_list_by_section_id_with_pagination(self, mock_client, sample_score_data):
        """Test listing scores with pagination."""
        mock_client.execute.return_value = {
            'listScoreBySectionId': {
                'items': [sample_score_data],
                'nextToken': 'token-abc'
            }
        }
        
        result = Score.list_by_section_id('section-456', mock_client, limit=10)
        
        assert result['nextToken'] == 'token-abc'
        
        # Verify query parameters
        call_args = mock_client.execute.call_args
        variables = call_args[0][1]
        assert variables['limit'] == 10
    
    def test_list_by_section_id_empty_result(self, mock_client):
        """Test listing scores with no results."""
        mock_client.execute.return_value = {
            'listScoreBySectionId': {
                'items': [],
                'nextToken': None
            }
        }
        
        result = Score.list_by_section_id('section-999', mock_client)
        
        assert result['items'] == []
        assert result['nextToken'] is None


class TestScoreFields:
    """Test Score.fields() method."""
    
    def test_fields_includes_required_fields(self):
        """Test that fields() includes all required fields."""
        fields = Score.fields()
        
        required_fields = [
            'id', 'name', 'key', 'externalId', 'type', 
            'order', 'sectionId'
        ]
        
        for field in required_fields:
            assert field in fields, f"Required field '{field}' missing from fields()"
    
    def test_fields_includes_optional_fields(self):
        """Test that fields() includes optional fields."""
        fields = Score.fields()
        
        optional_fields = ['accuracy', 'version', 'aiProvider', 'aiModel']
        
        for field in optional_fields:
            assert field in fields, f"Optional field '{field}' missing from fields()"


class TestScoreIntegration:
    """Integration tests for Score model."""
    
    def test_score_lookup_chain(self, mock_client, sample_score_data):
        """Test that different lookup methods can find the same score."""
        # Setup mock to return the same score for different lookups
        mock_client.execute.return_value = {
            'listScoreByName': {'items': [sample_score_data]},
            'listScoreByKey': {'items': [sample_score_data]},
            'listScoreByExternalId': {'items': [sample_score_data]}
        }
        
        # All lookups should find the same score
        by_name = Score.get_by_name('Test Score', 'scorecard-123', mock_client)
        
        mock_client.execute.return_value = {'listScoreByKey': {'items': [sample_score_data]}}
        by_key = Score.get_by_key('test-score', 'scorecard-123', mock_client)
        
        mock_client.execute.return_value = {'listScoreByExternalId': {'items': [sample_score_data]}}
        by_external = Score.get_by_external_id('0', 'scorecard-123', mock_client)
        
        assert by_name.id == by_key.id == by_external.id == 'score-123'
    
    def test_score_with_client_reference(self, mock_client, sample_score_data):
        """Test that Score maintains reference to its client."""
        score = Score.from_dict(sample_score_data, mock_client)
        
        assert score._client is mock_client


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

