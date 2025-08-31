"""
Test cases for Score model configuration pull and push functionality.

These tests cover:
- Pulling configurations from API to local files
- Pushing local configurations back to API as new versions
- Version conflict detection and content comparison
- Error handling for various failure scenarios
"""

import unittest
import tempfile
import json
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard


class MockAPIClient:
    """Mock API client for testing Score configuration methods."""
    
    def __init__(self):
        self.execute_responses = {}
        self.call_history = []
    
    def execute(self, query, variables=None):
        """Mock execute method that returns pre-configured responses."""
        self.call_history.append({'query': query, 'variables': variables})
        
        # Return appropriate response based on query content
        if 'GetScore' in query and 'championVersionId' in query:
            return self.execute_responses.get('get_champion', {
                'getScore': {'championVersionId': 'version-123'}
            })
        elif 'GetScoreVersion' in query:
            return self.execute_responses.get('get_version', {
                'getScoreVersion': {
                    'configuration': 'test: yaml content',
                    'createdAt': '2024-01-01T00:00:00Z',
                    'updatedAt': '2024-01-01T00:00:00Z',
                    'note': 'Test version'
                }
            })
        elif 'GetSection' in query:
            return self.execute_responses.get('get_section', {
                'getSection': {'scorecardId': 'scorecard-456'}
            })
        elif 'CreateScoreVersion' in query:
            return self.execute_responses.get('create_version', {
                'createScoreVersion': {
                    'id': 'new-version-789',
                    'configuration': 'test: yaml content',
                    'createdAt': '2024-01-02T00:00:00Z',
                    'updatedAt': '2024-01-02T00:00:00Z',
                    'note': 'New version',
                    'score': {
                        'id': 'score-123',
                        'championVersionId': 'new-version-789'
                    }
                }
            })
        elif 'UpdateScore' in query:
            return self.execute_responses.get('update_score', {
                'updateScore': {
                    'id': 'score-123',
                    'name': 'Test Score',
                    'championVersionId': 'new-version-789'
                }
            })
        
        return {}


class TestScoreConfiguration(unittest.TestCase):
    """Test cases for Score configuration pull/push functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MockAPIClient()
        self.score = Score(
            id='score-123',
            name='Test Score',
            key='test_score',
            externalId='ext-123',
            type='Classifier',
            order=1,
            sectionId='section-789',
            client=self.mock_client
        )
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id')
    def test_pull_configuration_success(self, mock_get_scorecard):
        """Test successful configuration pull."""
        # Setup mocks
        mock_scorecard = Mock()
        mock_scorecard.name = 'Test Scorecard'
        mock_get_scorecard.return_value = mock_scorecard
        
        # Mock the get_local_code_path method to return our test path
        yaml_path = Path(self.temp_dir) / 'test_score.yaml'
        with patch.object(self.score, 'get_local_code_path', return_value=yaml_path):
            with patch.object(self.score, 'get_local_guidelines_path', return_value=yaml_path.with_suffix('.md')):
                # Execute pull
                result = self.score.pull_configuration()
                
                # Verify success
                self.assertTrue(result['success'])
                self.assertEqual(result['version_id'], 'version-123')
                # The file path should be the one returned by the mocked function
                self.assertEqual(result['file_path'], str(yaml_path))
                
                # Verify file was created with correct content
                self.assertTrue(yaml_path.exists())
                with open(yaml_path, 'r') as f:
                    content = f.read()
                
                self.assertIn('# Pulled from Plexus API', content)
                self.assertIn('# Score: Test Score', content)
                self.assertIn('# Champion Version ID: version-123', content)
                self.assertIn('test: yaml content', content)

    def test_pull_configuration_no_client(self):
        """Test pull configuration fails without API client."""
        score_no_client = Score(
            id='score-123',
            name='Test Score',
            key='test_score',
            externalId='ext-123',
            type='Classifier',
            order=1,
            sectionId='section-789',
            client=None
        )
        
        result = score_no_client.pull_configuration()
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No API client available')

    def test_pull_configuration_no_champion_version(self):
        """Test pull configuration when no champion version exists."""
        self.mock_client.execute_responses['get_champion'] = {
            'getScore': {'championVersionId': None}
        }
        
        result = self.score.pull_configuration()
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'NO_CHAMPION_VERSION')

    @patch('plexus.dashboard.api.models.score.get_score_yaml_path')
    @patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id')
    def test_push_configuration_success(self, mock_get_scorecard, mock_get_path):
        """Test successful configuration push with content changes."""
        # Setup mocks
        mock_scorecard = Mock()
        mock_scorecard.name = 'Test Scorecard'
        mock_get_scorecard.return_value = mock_scorecard
        
        yaml_path = Path(self.temp_dir) / 'test_score.yaml'
        mock_get_path.return_value = yaml_path
        
        # Create test YAML file with changed content
        with open(yaml_path, 'w') as f:
            f.write("# Pulled from Plexus API\n")
            f.write("# Score: Test Score\n") 
            f.write("# Champion Version ID: version-123\n")
            f.write("#\n")
            f.write("test: modified yaml content")
        
        # Setup different current version content to trigger push
        self.mock_client.execute_responses['get_version'] = {
            'getScoreVersion': {
                'configuration': 'test: original yaml content'
            }
        }
        
        # Execute push
        result = self.score.push_configuration(note='Test update')
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['version_id'], 'new-version-789')
        self.assertFalse(result['champion_updated'])  # MCP tools should not promote to champion
        self.assertFalse(result['skipped'])

    @patch('plexus.dashboard.api.models.score.get_score_yaml_path')
    @patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id')
    def test_push_configuration_no_changes(self, mock_get_scorecard, mock_get_path):
        """Test push configuration skips when no changes detected."""
        # Setup mocks
        mock_scorecard = Mock()
        mock_scorecard.name = 'Test Scorecard'
        mock_get_scorecard.return_value = mock_scorecard
        
        yaml_path = Path(self.temp_dir) / 'test_score.yaml'
        mock_get_path.return_value = yaml_path
        
        # Create test YAML file with same content as current version
        with open(yaml_path, 'w') as f:
            f.write("# Pulled from Plexus API\n")
            f.write("# Score: Test Score\n")
            f.write("# Champion Version ID: version-123\n") 
            f.write("#\n")
            f.write("test: yaml content")
        
        # Setup same content in current version (exactly what will be extracted after comment stripping)
        self.mock_client.execute_responses['get_version'] = {
            'getScoreVersion': {
                'configuration': 'test: yaml content'
            }
        }
        
        # Execute push
        result = self.score.push_configuration(scorecard_name='Test Scorecard')
        
        # Verify skipped
        self.assertTrue(result['success'])
        self.assertEqual(result['version_id'], 'version-123')
        self.assertFalse(result['champion_updated'])
        self.assertTrue(result['skipped'])

    def test_push_configuration_file_not_found(self):
        """Test push configuration fails when local file doesn't exist."""
        yaml_path = Path(self.temp_dir) / 'nonexistent.yaml'
        guidelines_path = yaml_path.with_suffix('.md')
        
        with patch.object(self.score, 'get_local_code_path', return_value=yaml_path):
            with patch.object(self.score, 'get_local_guidelines_path', return_value=guidelines_path):
                # Provide scorecard name to avoid API lookup
                result = self.score.push_configuration(scorecard_name='Test Scorecard')
                
                self.assertFalse(result['success'])
                self.assertEqual(result['error'], 'NO_FILES_FOUND')

    def test_push_configuration_no_client(self):
        """Test push configuration fails without API client."""
        score_no_client = Score(
            id='score-123',
            name='Test Score',
            key='test_score',
            externalId='ext-123',
            type='Classifier',
            order=1,
            sectionId='section-789',
            client=None
        )
        
        result = score_no_client.push_configuration()
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'NO_CLIENT')

    @patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id')
    def test_get_local_configuration_path_with_scorecard_name(self, mock_get_scorecard):
        """Test getting local path when scorecard name is provided."""
        with patch('plexus.cli.shared.get_score_yaml_path') as mock_get_path:
            mock_get_path.return_value = Path('./scorecards/Test_Scorecard/test_score.yaml')
            
            result = self.score.get_local_configuration_path('Test Scorecard')
            
            mock_get_path.assert_called_once_with('Test Scorecard', 'Test Score')
            # Should not call API when scorecard name is provided
            mock_get_scorecard.assert_not_called()

    @patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id')
    def test_get_local_configuration_path_lookup_scorecard(self, mock_get_scorecard):
        """Test getting local path when scorecard name needs to be looked up."""
        # Setup mocks
        mock_scorecard = Mock()
        mock_scorecard.name = 'Looked Up Scorecard'
        mock_get_scorecard.return_value = mock_scorecard
        
        with patch('plexus.cli.shared.get_score_yaml_path') as mock_get_path:
            mock_get_path.return_value = Path('./scorecards/Looked_Up_Scorecard/test_score.yaml')
            
            result = self.score.get_local_configuration_path()
            
            # Verify section lookup occurred
            section_call = self.mock_client.call_history[0]
            self.assertIn('GetSection', section_call['query'])
            self.assertEqual(section_call['variables']['id'], 'section-789')
            
            # Verify scorecard lookup with correct ID
            mock_get_scorecard.assert_called_once_with('scorecard-456', self.mock_client)
            
            # Verify final path call
            mock_get_path.assert_called_once_with('Looked Up Scorecard', 'Test Score')

    def test_get_local_configuration_path_no_client(self):
        """Test getting local path fails without API client when lookup needed."""
        score_no_client = Score(
            id='score-123',
            name='Test Score', 
            key='test_score',
            externalId='ext-123',
            type='Classifier',
            order=1,
            sectionId='section-789',
            client=None
        )
        
        with self.assertRaises(ValueError) as context:
            score_no_client.get_local_configuration_path()
        
        self.assertIn('No API client available', str(context.exception))

    @patch('plexus.dashboard.api.models.score.get_score_yaml_path')
    @patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_id')
    def test_error_handling_api_failures(self, mock_get_scorecard, mock_get_path):
        """Test error handling for various API failure scenarios."""
        yaml_path = Path(self.temp_dir) / 'test_score.yaml'
        mock_get_path.return_value = yaml_path
        
        # Test API failure during pull
        self.mock_client.execute_responses['get_champion'] = None
        
        result = self.score.pull_configuration()
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'API_ERROR')

    def test_yaml_content_cleaning(self):
        """Test that metadata comments are properly stripped during push."""
        yaml_path = Path(self.temp_dir) / 'test_score.yaml'
        
        with patch.object(self.score, 'get_local_code_path', return_value=yaml_path):
            with patch.object(self.score, 'get_local_guidelines_path', return_value=yaml_path.with_suffix('.md')):
                # Create YAML file with metadata comments and content
                test_content = """# Pulled from Plexus API
# Score: Test Score
# Champion Version ID: version-123
# Created: 2024-01-01T00:00:00Z
# Updated: 2024-01-01T00:00:00Z
# Note: Previous version
#
test: yaml content
nested:
  key: value
# This comment should remain
"""
                
                with open(yaml_path, 'w') as f:
                    f.write(test_content)
                
                # Setup API to return different content to trigger push
                self.mock_client.execute_responses['get_version'] = {
                    'getScoreVersion': {
                        'configuration': 'different: content'
                    }
                }
                
                # Execute push
                self.score.push_configuration(scorecard_name='Test Scorecard')
                
                # Verify the API call used cleaned content (no metadata comments)
                create_call = None
                for call in self.mock_client.call_history:
                    if 'CreateScoreVersion' in call['query']:
                        create_call = call
                        break
                
                self.assertIsNotNone(create_call)
                pushed_content = create_call['variables']['input']['configuration']
                
                # Should not contain metadata comments
                self.assertNotIn('# Pulled from Plexus API', pushed_content)
                self.assertNotIn('# Score:', pushed_content)
                self.assertNotIn('# Champion Version ID:', pushed_content)
                
                # Should contain the actual YAML content
                self.assertIn('test: yaml content', pushed_content)
                self.assertIn('nested:', pushed_content)
                self.assertIn('key: value', pushed_content)
                # Regular comments should remain
                self.assertIn('# This comment should remain', pushed_content)

    def test_get_champion_configuration_yaml_success(self):
        """Test get_champion_configuration_yaml with successful retrieval."""
        self.mock_client.execute_responses['get_champion'] = {
            'getScore': {'championVersionId': 'version-123'}
        }
        self.mock_client.execute_responses['get_version'] = {
            'getScoreVersion': {'configuration': 'graph:\n  - node_id: test\n    class: SimpleClassifier'}
        }
        
        yaml_config = self.score.get_champion_configuration_yaml()
        
        self.assertEqual(yaml_config, 'graph:\n  - node_id: test\n    class: SimpleClassifier')
        
        # Verify the correct queries were made
        self.assertEqual(len(self.mock_client.call_history), 2)
        
        # Check first call (getScore)
        first_call = self.mock_client.call_history[0]
        self.assertIn('GetScore', first_call['query'])
        self.assertEqual(first_call['variables'], {'id': 'score-123'})
        
        # Check second call (getScoreVersion)
        second_call = self.mock_client.call_history[1]
        self.assertIn('GetScoreVersion', second_call['query'])
        self.assertEqual(second_call['variables'], {'id': 'version-123'})
    
    def test_get_champion_configuration_yaml_no_champion(self):
        """Test get_champion_configuration_yaml when no champion version exists."""
        self.mock_client.execute_responses['get_champion'] = {
            'getScore': {'championVersionId': None}
        }
        
        yaml_config = self.score.get_champion_configuration_yaml()
        
        self.assertIsNone(yaml_config)
    
    def test_get_champion_configuration_yaml_no_configuration(self):
        """Test get_champion_configuration_yaml when version has no configuration."""
        self.mock_client.execute_responses['get_champion'] = {
            'getScore': {'championVersionId': 'version-123'}
        }
        self.mock_client.execute_responses['get_version'] = {
            'getScoreVersion': {'configuration': None}
        }
        
        yaml_config = self.score.get_champion_configuration_yaml()
        
        self.assertIsNone(yaml_config)

    def test_get_champion_configuration_yaml_no_client(self):
        """Test get_champion_configuration_yaml fails without API client."""
        score_no_client = Score(
            id='score-123',
            name='Test Score',
            key='test_score',
            externalId='external-123',
            type='classification',
            order=1,
            sectionId='section-123',
            accuracy=0.95
        )
        
        with self.assertRaises(ValueError) as context:
            score_no_client.get_champion_configuration_yaml()
        
        self.assertEqual(str(context.exception), "No API client available")


class TestScoreVersionCreation(unittest.TestCase):
    """Test cases for Score.create_version_from_yaml() - the foundational string-based method."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MockAPIClient()
        self.score = Score(
            id='score-123',
            name='Test Score',
            key='test_score',
            externalId='ext-123',
            type='Classifier',
            order=1,
            sectionId='section-789',
            client=self.mock_client
        )
        
    def test_create_version_from_yaml_success(self):
        """Test successful version creation from YAML string."""
        yaml_content = """
test: configuration
nodes:
  - type: classifier
    name: test_classifier
"""
        
        # Setup different current version to trigger creation
        self.mock_client.execute_responses['get_version'] = {
            'getScoreVersion': {
                'configuration': 'different: content'
            }
        }
        
        result = self.score.create_version_from_yaml(yaml_content, note="Test version creation")
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['version_id'], 'new-version-789')
        self.assertFalse(result['champion_updated'])  # MCP tools should not promote to champion
        self.assertFalse(result['skipped'])
        
        # Verify GraphQL calls
        create_call = None
        for call in self.mock_client.call_history:
            if 'CreateScoreVersion' in call['query']:
                create_call = call
                break
        
        self.assertIsNotNone(create_call)
        # Note: No UpdateScore call expected since MCP tools don't promote to champion
        
        # Verify version input
        version_input = create_call['variables']['input']
        self.assertEqual(version_input['scoreId'], 'score-123')
        self.assertEqual(version_input['note'], 'Test version creation')
        self.assertTrue(version_input['isFeatured'])
        self.assertEqual(version_input['parentVersionId'], 'version-123')

    def test_create_version_from_yaml_no_changes(self):
        """Test version creation skipped when content hasn't changed."""
        yaml_content = "test: yaml content"
        
        # Setup same content in current version
        self.mock_client.execute_responses['get_version'] = {
            'getScoreVersion': {
                'configuration': 'test: yaml content'
            }
        }
        
        result = self.score.create_version_from_yaml(yaml_content)
        
        # Verify skipped
        self.assertTrue(result['success'])
        self.assertEqual(result['version_id'], 'version-123')
        self.assertFalse(result['champion_updated'])
        self.assertTrue(result['skipped'])
        
        # Verify no CreateScoreVersion call was made
        for call in self.mock_client.call_history:
            self.assertNotIn('CreateScoreVersion', call['query'])

    def test_create_version_from_yaml_invalid_yaml(self):
        """Test version creation fails with invalid YAML."""
        invalid_yaml = """
test: [unclosed bracket
another: "unclosed quote
invalid: yaml: structure: with: colons
"""
        
        result = self.score.create_version_from_yaml(invalid_yaml)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'INVALID_YAML')
        self.assertIn('Invalid YAML code content', result['message'])

    def test_create_version_from_yaml_no_client(self):
        """Test version creation fails without API client."""
        score_no_client = Score(
            id='score-123',
            name='Test Score',
            key='test_score',
            externalId='ext-123',
            type='Classifier',
            order=1,
            sectionId='section-789',
            client=None
        )
        
        result = score_no_client.create_version_from_yaml("test: yaml")
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'NO_CLIENT')

    def test_create_version_from_yaml_no_current_champion(self):
        """Test version creation when no current champion version exists."""
        yaml_content = "test: new configuration"
        
        # Setup no champion version
        self.mock_client.execute_responses['get_champion'] = {
            'getScore': {'championVersionId': None}
        }
        
        result = self.score.create_version_from_yaml(yaml_content)
        
        # Should still create version successfully
        self.assertTrue(result['success'])
        self.assertEqual(result['version_id'], 'new-version-789')
        
        # Verify no parentVersionId was set
        create_call = None
        for call in self.mock_client.call_history:
            if 'CreateScoreVersion' in call['query']:
                create_call = call
                break
        
        self.assertIsNotNone(create_call)
        version_input = create_call['variables']['input']
        self.assertNotIn('parentVersionId', version_input)

    def test_create_version_from_yaml_api_error(self):
        """Test version creation handles API errors gracefully."""
        yaml_content = "test: configuration"
        
        # Setup API error
        self.mock_client.execute_responses['get_champion'] = None
        
        result = self.score.create_version_from_yaml(yaml_content)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'API_ERROR')

    def test_create_version_from_yaml_version_creation_failure(self):
        """Test handling of version creation API failure."""
        yaml_content = "test: configuration"
        
        # Setup successful champion lookup but failed version creation
        self.mock_client.execute_responses['create_version'] = None
        
        result = self.score.create_version_from_yaml(yaml_content)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'VERSION_CREATION_FAILED')

    def test_create_version_from_yaml_champion_update_failure(self):
        """Test handling when version creates but champion update fails."""
        yaml_content = "test: configuration"
        
        # Setup version creation success but champion update failure
        self.mock_client.execute_responses['update_score'] = {
            'errors': [{'message': 'Failed to update champion'}]
        }
        
        result = self.score.create_version_from_yaml(yaml_content)
        
        # Should still report success but with champion_updated = False
        self.assertTrue(result['success'])
        self.assertEqual(result['version_id'], 'new-version-789')
        self.assertFalse(result['champion_updated'])
        self.assertFalse(result['skipped'])

    def test_create_version_from_yaml_whitespace_handling(self):
        """Test that YAML content whitespace is properly handled."""
        yaml_content = """
        
test: configuration
nodes:
  - type: classifier
        
        """
        
        # Setup different current version to trigger creation
        self.mock_client.execute_responses['get_version'] = {
            'getScoreVersion': {
                'configuration': 'different: content'
            }
        }
        
        result = self.score.create_version_from_yaml(yaml_content)
        
        # Verify success
        self.assertTrue(result['success'])
        
        # Verify that the YAML was stripped before sending to API
        create_call = None
        for call in self.mock_client.call_history:
            if 'CreateScoreVersion' in call['query']:
                create_call = call
                break
        
        self.assertIsNotNone(create_call)
        sent_config = create_call['variables']['input']['configuration']
        
        # Should be stripped but maintain internal structure
        self.assertFalse(sent_config.startswith('\n'))
        self.assertFalse(sent_config.endswith('\n'))
        self.assertIn('test: configuration', sent_config)
        self.assertIn('nodes:', sent_config)

    def test_create_version_from_yaml_default_note(self):
        """Test that default note is used when none provided."""
        yaml_content = "test: configuration"
        
        # Setup different current version to trigger creation
        self.mock_client.execute_responses['get_version'] = {
            'getScoreVersion': {
                'configuration': 'different: content'
            }
        }
        
        result = self.score.create_version_from_yaml(yaml_content)
        
        # Verify default note was used
        create_call = None
        for call in self.mock_client.call_history:
            if 'CreateScoreVersion' in call['query']:
                create_call = call
                break
        
        self.assertIsNotNone(create_call)
        version_input = create_call['variables']['input']
        self.assertEqual(version_input['note'], 'Updated via Score.create_version_from_yaml()')


if __name__ == '__main__':
    unittest.main() 