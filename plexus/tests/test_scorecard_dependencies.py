import os
import unittest
import yaml
from pathlib import Path

class TestScorecardDependencies(unittest.TestCase):
    """Test cases for validating scorecard dependency structures."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.fixtures_dir = Path("plexus/tests/fixtures/scorecards")
        
    def test_fixture_files_exist(self):
        """Test that all expected fixture files exist."""
        expected_files = [
            "test_scorecard.yaml",
            "test_scorecard_linear.yaml",
            "test_scorecard_complex.yaml"
        ]
        
        for file_name in expected_files:
            file_path = self.fixtures_dir / file_name
            self.assertTrue(file_path.exists(), f"Fixture file {file_path} should exist")
    
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
                self.assertIn('scores', scorecard, f"Scorecard {file_name} should have scores")
                
                # Check scores
                self.assertTrue(isinstance(scorecard['scores'], list), 
                               f"Scores in {file_name} should be a list")
                self.assertTrue(len(scorecard['scores']) > 0, 
                               f"Scorecard {file_name} should have at least one score")
                
                # Check each score
                for score in scorecard['scores']:
                    self.assertIn('name', score, f"Score in {file_name} should have a name")
                    self.assertIn('key', score, f"Score in {file_name} should have a key")
                    self.assertIn('id', score, f"Score in {file_name} should have an id")
                    self.assertIn('class', score, f"Score in {file_name} should have a class")
    
    def test_dependency_structure(self):
        """Test that dependencies are correctly structured."""
        for file_name in os.listdir(self.fixtures_dir):
            if file_name.endswith('.yaml'):
                file_path = self.fixtures_dir / file_name
                with open(file_path, 'r') as f:
                    scorecard = yaml.safe_load(f)
                
                # Get all score names
                score_names = [score['name'] for score in scorecard['scores']]
                
                # Check dependencies
                for score in scorecard['scores']:
                    if 'depends_on' in score:
                        depends_on = score['depends_on']
                        
                        # Test list dependencies
                        if isinstance(depends_on, list):
                            for dep in depends_on:
                                self.assertIn(dep, score_names, 
                                             f"Dependency {dep} in {score['name']} should be a valid score name")
                        
                        # Test dict dependencies
                        elif isinstance(depends_on, dict):
                            for dep_name, condition in depends_on.items():
                                self.assertIn(dep_name, score_names, 
                                             f"Dependency {dep_name} in {score['name']} should be a valid score name")
                                
                                # Check condition structure
                                if isinstance(condition, dict):
                                    self.assertIn('operator', condition, 
                                                 f"Condition for {dep_name} in {score['name']} should have an operator")
                                    self.assertIn('value', condition, 
                                                 f"Condition for {dep_name} in {score['name']} should have a value")

    def test_specific_dependency_paths(self):
        """Test specific dependency paths in each scorecard."""
        # Test test_scorecard.yaml
        with open(self.fixtures_dir / "test_scorecard.yaml", 'r') as f:
            scorecard = yaml.safe_load(f)
            
            # Find Complex Dependent Score
            complex_score = None
            for score in scorecard['scores']:
                if score['name'] == 'Complex Dependent Score':
                    complex_score = score
                    break
            
            self.assertIsNotNone(complex_score, "Complex Dependent Score should exist")
            self.assertIn('depends_on', complex_score, "Complex Dependent Score should have dependencies")
            self.assertEqual(len(complex_score['depends_on']), 2, 
                            "Complex Dependent Score should depend on two other scores")
            
        # Test test_scorecard_linear.yaml
        with open(self.fixtures_dir / "test_scorecard_linear.yaml", 'r') as f:
            scorecard = yaml.safe_load(f)
            
            # Check Score D depends on Score C
            score_d = None
            for score in scorecard['scores']:
                if score['name'] == 'Score D':
                    score_d = score
                    break
            
            self.assertIsNotNone(score_d, "Score D should exist")
            self.assertIn('depends_on', score_d, "Score D should have dependencies")
            self.assertIn('Score C', score_d['depends_on'], "Score D should depend on Score C")
            
        # Test test_scorecard_complex.yaml
        with open(self.fixtures_dir / "test_scorecard_complex.yaml", 'r') as f:
            scorecard = yaml.safe_load(f)
            
            # Check Final Assessment dependencies
            final_score = None
            for score in scorecard['scores']:
                if score['name'] == 'Final Assessment':
                    final_score = score
                    break
            
            self.assertIsNotNone(final_score, "Final Assessment should exist")
            self.assertIn('depends_on', final_score, "Final Assessment should have dependencies")
            self.assertEqual(len(final_score['depends_on']), 2, 
                            "Final Assessment should depend on two integrator scores")

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
                
                # First pass: create name_to_id mapping
                for i, score in enumerate(scorecard['scores']):
                    score_id = str(i + 1)  # Simple numeric id for testing
                    score_name = score['name']
                    name_to_id[score_name] = score_id
                    dependency_graph[score_id] = {
                        'name': score_name,
                        'deps': [],
                        'conditions': {}
                    }
                
                # Second pass: add dependencies
                for i, score in enumerate(scorecard['scores']):
                    score_id = str(i + 1)
                    if 'depends_on' in score:
                        depends_on = score['depends_on']
                        
                        # List dependencies
                        if isinstance(depends_on, list):
                            for dep_name in depends_on:
                                dep_id = name_to_id.get(dep_name)
                                if dep_id:
                                    dependency_graph[score_id]['deps'].append(dep_id)
                        
                        # Dict dependencies with conditions
                        elif isinstance(depends_on, dict):
                            for dep_name, condition in depends_on.items():
                                dep_id = name_to_id.get(dep_name)
                                if dep_id:
                                    dependency_graph[score_id]['deps'].append(dep_id)
                                    
                                    # Add conditions if present
                                    if isinstance(condition, dict):
                                        dependency_graph[score_id]['conditions'][dep_id] = {
                                            'operator': condition.get('operator'),
                                            'value': condition.get('value')
                                        }
                
                # Verify the graph has expected properties
                self.assertEqual(len(dependency_graph), len(scorecard['scores']), 
                               f"Dependency graph for {file_name} should have one entry per score")
                
                # Check for cycles (simple check - not comprehensive)
                visited = set()
                def has_cycle(node_id, path=None):
                    if path is None:
                        path = set()
                    
                    if node_id in path:
                        return True
                    
                    if node_id in visited:
                        return False
                    
                    visited.add(node_id)
                    path.add(node_id)
                    
                    for dep_id in dependency_graph[node_id]['deps']:
                        if has_cycle(dep_id, path):
                            return True
                    
                    path.remove(node_id)
                    return False
                
                for node_id in dependency_graph:
                    self.assertFalse(has_cycle(node_id), 
                                    f"Dependency graph for {file_name} should not have cycles")

if __name__ == '__main__':
    unittest.main() 