"""
Tests for score dependency resolution functionality.

This module tests the functionality for discovering and resolving score dependencies,
including:
- Extracting dependencies from score configurations
- Building a complete dependency graph
- Handling different dependency formats (list, dict)
- Resolving dependency names to IDs
"""
import json
import unittest
from unittest.mock import patch, mock_open

import pytest
from ruamel.yaml import YAML

from plexus.cli.dependency_discovery import (
    extract_dependencies_from_config,
    discover_dependencies,
    build_name_id_mappings
)


class TestDependencyExtraction(unittest.TestCase):
    """Tests for extracting dependencies from score configurations."""
    
    def test_extract_list_dependencies(self):
        """Test extracting dependencies specified as a list."""
        config_yaml = """
name: Test Score
key: test_score
depends_on:
  - Base Score
  - Other Score
"""
        expected = ["Base Score", "Other Score"]
        result = extract_dependencies_from_config(config_yaml)
        self.assertEqual(set(result), set(expected))
    
    def test_extract_dict_dependencies(self):
        """Test extracting dependencies specified as a dictionary."""
        config_yaml = """
name: Test Score
key: test_score
depends_on:
  Base Score:
    operator: "=="
    value: "Yes"
  Other Score:
    operator: "!="
    value: "No"
"""
        expected = ["Base Score", "Other Score"]
        result = extract_dependencies_from_config(config_yaml)
        self.assertEqual(set(result), set(expected))
    
    def test_no_dependencies(self):
        """Test extracting dependencies when none are specified."""
        config_yaml = """
name: Test Score
key: test_score
"""
        result = extract_dependencies_from_config(config_yaml)
        self.assertEqual(result, [])
    
    def test_empty_dependencies(self):
        """Test extracting dependencies when an empty list is specified."""
        config_yaml = """
name: Test Score
key: test_score
depends_on: []
"""
        result = extract_dependencies_from_config(config_yaml)
        self.assertEqual(result, [])
    
    def test_invalid_yaml(self):
        """Test extracting dependencies from invalid YAML."""
        config_yaml = """
name: Test Score
key: test_score
depends_on: - Invalid YAML
"""
        result = extract_dependencies_from_config(config_yaml)
        self.assertEqual(result, [])


class TestDependencyDiscovery(unittest.TestCase):
    """Tests for discovering all dependencies for a set of scores."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock configurations
        self.configurations = {
            "score-001": """
name: Simple Score
key: simple_score
class: Score
description: A simple score with no dependencies
metrics:
  - name: accuracy
    type: float
    range: [0, 1]
    description: Accuracy of the score
""",
            "score-002": """
name: Dependent Score
key: dependent_score
class: Score
description: A score that depends on base_score
depends_on:
  - Base Score
metrics:
  - name: accuracy
    type: float
    range: [0, 1]
    description: Accuracy of the score
""",
            "score-003": """
name: Base Score
key: base_score
class: Score
description: A base score that others depend on
metrics:
  - name: accuracy
    type: float
    range: [0, 1]
    description: Accuracy of the score
""",
            "score-004": """
name: Complex Score
key: complex_score
class: Score
description: A score with complex dependencies
depends_on:
  - Base Score
  - Simple Score
metrics:
  - name: accuracy
    type: float
    range: [0, 1]
    description: Accuracy of the score
"""
        }
        
        # Create ID-to-name and name-to-ID mappings
        self.id_to_name = {
            "score-001": "Simple Score",
            "score-002": "Dependent Score",
            "score-003": "Base Score",
            "score-004": "Complex Score"
        }
        
        self.name_to_id = {
            "Simple Score": "score-001",
            "Dependent Score": "score-002",
            "Base Score": "score-003",
            "Complex Score": "score-004"
        }
    
    def test_single_score_no_dependencies(self):
        """Test discovering dependencies for a single score with no dependencies."""
        target_ids = {"score-001"}  # Simple Score
        required_ids = discover_dependencies(
            target_ids,
            self.configurations,
            self.id_to_name,
            self.name_to_id
        )
        self.assertEqual(required_ids, {"score-001"})
    
    def test_single_score_with_dependencies(self):
        """Test discovering dependencies for a single score with dependencies."""
        target_ids = {"score-002"}  # Dependent Score
        required_ids = discover_dependencies(
            target_ids,
            self.configurations,
            self.id_to_name,
            self.name_to_id
        )
        self.assertEqual(required_ids, {"score-002", "score-003"})
    
    def test_complex_dependencies(self):
        """Test discovering dependencies for a score with multiple dependencies."""
        target_ids = {"score-004"}  # Complex Score
        required_ids = discover_dependencies(
            target_ids,
            self.configurations,
            self.id_to_name,
            self.name_to_id
        )
        self.assertEqual(required_ids, {"score-001", "score-003", "score-004"})
    
    def test_multiple_target_scores(self):
        """Test discovering dependencies for multiple target scores."""
        target_ids = {"score-001", "score-002"}  # Simple Score, Dependent Score
        required_ids = discover_dependencies(
            target_ids,
            self.configurations,
            self.id_to_name,
            self.name_to_id
        )
        self.assertEqual(required_ids, {"score-001", "score-002", "score-003"})
    
    def test_missing_configuration(self):
        """Test handling missing configurations."""
        target_ids = {"score-999"}  # Non-existent score
        required_ids = discover_dependencies(
            target_ids,
            self.configurations,
            self.id_to_name,
            self.name_to_id
        )
        self.assertEqual(required_ids, {"score-999"})
    
    def test_unresolvable_dependency(self):
        """Test handling unresolvable dependencies."""
        # Add a score with an unresolvable dependency
        self.configurations["score-005"] = """
name: Bad Score
key: bad_score
class: Score
description: A score with an unresolvable dependency
depends_on:
  - Non-existent Score
"""
        self.id_to_name["score-005"] = "Bad Score"
        self.name_to_id["Bad Score"] = "score-005"
        
        target_ids = {"score-005"}
        required_ids = discover_dependencies(
            target_ids,
            self.configurations,
            self.id_to_name,
            self.name_to_id
        )
        # Should only include the target score since the dependency can't be resolved
        self.assertEqual(required_ids, {"score-005"})


class TestNameIdMappings(unittest.TestCase):
    """Tests for building name-ID mappings."""
    
    def test_build_mappings(self):
        """Test building name-ID mappings from a list of scores."""
        scores = [
            {"id": "score-001", "name": "Score A"},
            {"id": "score-002", "name": "Score B"},
            {"id": "score-003", "name": "Score C"}
        ]
        
        id_to_name, name_to_id = build_name_id_mappings(scores)
        
        expected_id_to_name = {
            "score-001": "Score A",
            "score-002": "Score B",
            "score-003": "Score C"
        }
        
        expected_name_to_id = {
            "Score A": "score-001",
            "Score B": "score-002",
            "Score C": "score-003"
        }
        
        self.assertEqual(id_to_name, expected_id_to_name)
        self.assertEqual(name_to_id, expected_name_to_id)
    
    def test_missing_fields(self):
        """Test building mappings with scores missing fields."""
        scores = [
            {"id": "score-001", "name": "Score A"},
            {"id": "score-002"},  # Missing name
            {"name": "Score C"}   # Missing id
        ]
        
        id_to_name, name_to_id = build_name_id_mappings(scores)
        
        expected_id_to_name = {
            "score-001": "Score A"
        }
        
        expected_name_to_id = {
            "Score A": "score-001"
        }
        
        self.assertEqual(id_to_name, expected_id_to_name)
        self.assertEqual(name_to_id, expected_name_to_id)


# Create fixture files for more complex tests
class TestWithFixtures(unittest.TestCase):
    """Tests using fixture files for more complex scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Load fixture data
        self.fixture_path = "plexus/tests/fixtures/api_responses/scorecard_structure.json"
        self.config_path = "plexus/tests/fixtures/api_responses/score_configurations.json"
        
        with open(self.fixture_path, 'r') as f:
            self.structure_data = json.load(f)
        
        with open(self.config_path, 'r') as f:
            self.config_data = json.load(f)
        
        # Extract scores from structure data
        self.scores = []
        for section in self.structure_data['getScorecard']['sections']['items']:
            for score in section['scores']['items']:
                self.scores.append(score)
        
        # Build mappings
        self.id_to_name, self.name_to_id = build_name_id_mappings(self.scores)
        
        # Build configurations dictionary
        self.configurations = {}
        for score_id, data in self.config_data.items():
            self.configurations[score_id] = data['getScoreVersion']['configuration']
        
        # Fix the mappings for the base_score dependency
        # The dependency name in lowercase doesn't match the actual score name ("Base Score")
        self.name_to_id["base_score"] = "score-003"
    
    @patch('builtins.open', new_callable=mock_open)
    def test_fixture_dependency_resolution(self, mock_file):
        """Test dependency resolution with fixture data."""
        # Configure mock to return fixture data
        mock_file.side_effect = [
            mock_open(read_data=json.dumps(self.structure_data)).return_value,
            mock_open(read_data=json.dumps(self.config_data)).return_value
        ]
        
        # Test discovering dependencies for Dependent Score
        target_ids = {"score-002"}  # Dependent Score
        required_ids = discover_dependencies(
            target_ids,
            self.configurations,
            self.id_to_name,
            self.name_to_id
        )
        
        # Should include Dependent Score and Base Score
        self.assertIn("score-002", required_ids)
        self.assertIn("score-003", required_ids)


if __name__ == '__main__':
    unittest.main() 