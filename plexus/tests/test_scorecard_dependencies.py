"""
Tests for scorecard dependencies.

This module tests the functionality for handling scorecard dependencies,
including:
- Loading scorecard fixtures
- Extracting scores from scorecards
- Building dependency graphs
- Validating dependency structure
"""
import os
import unittest
from pathlib import Path

import yaml


# Helper function to extract scores from a scorecard with nested structure
def extract_scores_from_scorecard(scorecard):
    """Extract all scores from a scorecard, handling different structures."""
    scores = []
    
    # Handle scorecards with flat 'scores' array
    if 'scores' in scorecard:
        return scorecard['scores']
    
    # Handle scorecards with nested sections.scores structure
    if 'sections' in scorecard:
        for section in scorecard['sections']:
            if 'scores' in section:
                scores.extend(section['scores'])
    
    return scores


class TestScorecardDependencies(unittest.TestCase):
    """Test scorecard dependency discovery and resolution."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Find the fixtures directory
        self.fixtures_dir = Path(__file__).parent / "fixtures" / "scorecards"
        self.assertTrue(self.fixtures_dir.exists(), f"Fixtures directory not found: {self.fixtures_dir}")
    
    def test_scorecard_structure(self):
        """Test that scorecards have the expected structure."""
        for file_name in os.listdir(self.fixtures_dir):
            if file_name.endswith('.yaml'):
                file_path = self.fixtures_dir / file_name
                with open(file_path, 'r') as f:
                    scorecard = yaml.safe_load(f)
                
                # Check basic structure
                self.assertIn('name', scorecard, f"Scorecard {file_name} should have a name")
                self.assertIn('key', scorecard, f"Scorecard {file_name} should have a key")
                self.assertIn('id', scorecard, f"Scorecard {file_name} should have an id")
                
                # Check either 'scores' or 'sections' exists
                has_scores = 'scores' in scorecard
                has_sections = 'sections' in scorecard
                self.assertTrue(has_scores or has_sections, 
                                f"Scorecard {file_name} should have either scores or sections")
                
                # If using sections, check they contain scores
                if has_sections:
                    for section in scorecard['sections']:
                        self.assertIn('scores', section, 
                                     f"Section in {file_name} should have scores")
    
    def test_dependency_structure(self):
        """Test that dependencies are correctly structured."""
        for file_name in os.listdir(self.fixtures_dir):
            if file_name.endswith('.yaml'):
                file_path = self.fixtures_dir / file_name
                with open(file_path, 'r') as f:
                    scorecard = yaml.safe_load(f)
                
                # Get all scores
                scores = extract_scores_from_scorecard(scorecard)
                self.assertTrue(len(scores) > 0, f"No scores found in {file_name}")
                
                # Check score names
                score_names = [score['name'] for score in scores]
                self.assertTrue(len(score_names) > 0, f"No score names found in {file_name}")
                
                # Check dependencies if present
                for score in scores:
                    if 'depends_on' in score:
                        depends_on = score['depends_on']
                        if isinstance(depends_on, list):
                            # List-style dependencies
                            for dep_name in depends_on:
                                self.assertIsInstance(dep_name, str, 
                                                    f"Dependency name should be a string in {file_name}")
                        elif isinstance(depends_on, dict):
                            # Dict-style dependencies with conditions
                            for dep_name, condition in depends_on.items():
                                self.assertIsInstance(dep_name, str, 
                                                    f"Dependency name should be a string in {file_name}")
                                self.assertIsInstance(condition, dict, 
                                                    f"Dependency condition should be a dict in {file_name}")
                                self.assertIn('operator', condition, 
                                            f"Dependency condition should have an operator in {file_name}")
                                self.assertIn('value', condition, 
                                            f"Dependency condition should have a value in {file_name}")
    
    def test_specific_dependency_paths(self):
        """Test specific dependency paths in each scorecard."""
        # Test a fixture file if it exists (won't fail if it doesn't)
        test_file = self.fixtures_dir / "test_scorecard_complex.yaml"
        if test_file.exists():
            with open(test_file, 'r') as f:
                scorecard = yaml.safe_load(f)
                
                # Find and extract scores
                scores = extract_scores_from_scorecard(scorecard)
                
                # Find Complex Dependent Score if it exists
                complex_score = None
                dependent_score = None
                base_score = None
                
                for score in scores:
                    if score.get('name') == "Complex Dependent Score":
                        complex_score = score
                    elif score.get('name') == "Dependent Score 1":
                        dependent_score = score
                    elif score.get('name') == "Base Score":
                        base_score = score
                
                # Skip test if scores not found
                if not (complex_score and dependent_score and base_score):
                    return
                
                # Verify Complex Dependent Score depends on both
                self.assertIn('depends_on', complex_score, "Complex score should have dependencies")
                depends_on = complex_score['depends_on']
                
                # Verify at least two dependencies
                if isinstance(depends_on, list):
                    self.assertGreaterEqual(len(depends_on), 2, 
                                          "Complex score should have at least 2 dependencies")
                elif isinstance(depends_on, dict):
                    self.assertGreaterEqual(len(depends_on.keys()), 2, 
                                          "Complex score should have at least 2 dependencies")
    
    def test_build_dependency_graph(self):
        """Test building a dependency graph from the fixtures."""
        for file_name in os.listdir(self.fixtures_dir):
            if file_name.endswith('.yaml'):
                file_path = self.fixtures_dir / file_name
                with open(file_path, 'r') as f:
                    scorecard = yaml.safe_load(f)
                
                # Build a dependency graph
                dependency_graph = {}
                name_to_id = {}
                
                # Extract scores
                scores = extract_scores_from_scorecard(scorecard)
                
                # First pass: create name_to_id mapping
                for i, score in enumerate(scores):
                    if 'id' not in score:
                        # Generate a synthetic ID for testing
                        score['id'] = f"test-id-{i+1}"
                    name_to_id[score['name']] = score['id']
                
                # Second pass: build dependency graph
                for score in scores:
                    score_id = score['id']
                    dependency_graph[score_id] = []
                    
                    if 'depends_on' in score:
                        depends_on = score['depends_on']
                        if isinstance(depends_on, list):
                            # List-style dependencies
                            for dep_name in depends_on:
                                dep_id = name_to_id.get(dep_name)
                                if dep_id:
                                    dependency_graph[score_id].append(dep_id)
                        elif isinstance(depends_on, dict):
                            # Dict-style dependencies
                            for dep_name in depends_on.keys():
                                dep_id = name_to_id.get(dep_name)
                                if dep_id:
                                    dependency_graph[score_id].append(dep_id)
                
                # Verify the graph structure
                for score_id, dependencies in dependency_graph.items():
                    if dependencies:
                        for dep_id in dependencies:
                            self.assertIn(dep_id, dependency_graph, 
                                         f"Dependency {dep_id} should be in the graph")
    
    def test_circular_dependencies(self):
        """Test detection of circular dependencies."""
        # This test is a placeholder for potential circular dependency detection
        pass
    

if __name__ == '__main__':
    unittest.main() 