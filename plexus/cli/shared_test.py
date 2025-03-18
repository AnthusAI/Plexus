"""Tests for shared utility functions."""
import unittest
from pathlib import Path
import shutil
import os
from plexus.cli.shared import sanitize_path_name, get_score_yaml_path

class TestPathHandling(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        # Create a temporary test directory
        self.test_dir = Path('test_scorecards')
        self.test_dir.mkdir(exist_ok=True)
        
        # Change to the test directory
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        # Change back to original directory
        os.chdir(self.original_cwd)
        
        # Remove test directory and all contents
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_sanitize_path_name(self):
        """Test the path name sanitization function."""
        test_cases = [
            # Basic cases
            ("Simple Name", "simple_name"),
            ("Multiple   Spaces", "multiple_spaces"),
            ("Mixed-Case Name", "mixed_case_name"),
            
            # Special characters
            ("Name with @#$%^&*()", "name_with"),
            ("Name with dots...", "name_with_dots"),
            ("Name with slashes/\\", "name_with_slashes"),
            
            # Leading/trailing characters
            ("-Name with hyphens-", "name_with_hyphens"),
            ("_Name with underscores_", "name_with_underscores"),
            ("-Name with both-_", "name_with_both"),
            
            # Empty and edge cases
            ("", ""),
            ("   ", ""),
            ("---", ""),
            ("___", ""),
            ("-_-", ""),
            
            # Unicode characters
            ("Name with éèêë", "name_with"),
            ("Name with 你好", "name_with"),
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = sanitize_path_name(input_name)
                self.assertEqual(result, expected)
    
    def test_get_score_yaml_path(self):
        """Test the score YAML path computation function."""
        test_cases = [
            # Basic cases
            ("My Scorecard", "Call Quality", "scorecards/my_scorecard/call_quality.yaml"),
            ("Customer Service", "Response Time", "scorecards/customer_service/response_time.yaml"),
            
            # Cases with special characters
            ("Scorecard@#$", "Score!@#", "scorecards/scorecard/score.yaml"),
            ("My Scorecard...", "Call Quality...", "scorecards/my_scorecard/call_quality.yaml"),
            
            # Cases with spaces and mixed case
            ("My Score Card", "Call Quality Score", "scorecards/my_score_card/call_quality_score.yaml"),
            ("CUSTOMER SERVICE", "RESPONSE TIME", "scorecards/customer_service/response_time.yaml"),
            
            # Edge cases
            ("", "", "scorecards/.yaml"),
            ("   ", "   ", "scorecards/.yaml"),
            ("---", "---", "scorecards/.yaml"),
        ]
        
        for scorecard_name, score_name, expected_path in test_cases:
            with self.subTest(scorecard=scorecard_name, score=score_name):
                result = get_score_yaml_path(scorecard_name, score_name)
                self.assertEqual(str(result), expected_path)
                
                # Verify the directory was created
                if scorecard_name.strip():
                    self.assertTrue(result.parent.exists())
    
    def test_get_score_yaml_path_directory_creation(self):
        """Test that directories are created correctly."""
        # Test with a nested path
        result = get_score_yaml_path("Parent/Child", "My Score")
        self.assertTrue(result.parent.exists())
        self.assertEqual(str(result), "scorecards/parentchild/my_score.yaml")
        
        # Test with multiple levels
        result = get_score_yaml_path("Level1/Level2/Level3", "My Score")
        self.assertTrue(result.parent.exists())
        self.assertEqual(str(result), "scorecards/level1level2level3/my_score.yaml")
    
    def test_get_score_yaml_path_existing_directory(self):
        """Test behavior with existing directories."""
        # Create a directory manually
        manual_dir = Path("scorecards/manual_dir")
        manual_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to create a file in the existing directory
        result = get_score_yaml_path("Manual Dir", "My Score")
        self.assertEqual(str(result), "scorecards/manual_dir/my_score.yaml")
        
        # Verify the directory still exists
        self.assertTrue(result.parent.exists())
        
        # Try to create another file in the same directory
        result2 = get_score_yaml_path("Manual Dir", "Another Score")
        self.assertEqual(str(result2), "scorecards/manual_dir/another_score.yaml")
        self.assertTrue(result2.parent.exists())

if __name__ == '__main__':
    unittest.main() 