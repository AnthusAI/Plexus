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
            ("Simple Name", "Simple Name"),
            ("Multiple   Spaces", "Multiple   Spaces"),
            ("Mixed-Case Name", "Mixed-Case Name"),
            
            # Special characters
            ("Name with @#$%^&*()", "Name with @#$%^&-()"),
            ("Name with dots...", "Name with dots..."),
            ("Name with slashes/\\", "Name with slashes"),
            
            # Leading/trailing characters
            ("-Name with hyphens-", "Name with hyphens"),
            ("_Name with underscores_", "_Name with underscores_"),
            ("-Name with both-_", "Name with both-_"),
            
            # Empty and edge cases
            ("", ""),
            ("   ", ""),
            ("---", ""),
            ("___", "___"),
            ("-_-", "_"),
            
            # Unicode characters
            ("Name with éèêë", "Name with éèêë"),
            ("Name with 你好", "Name with 你好"),
            
            # Characters unsafe for filesystem
            ("File<>:\"/?*|Name", "File-Name"),
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = sanitize_path_name(input_name)
                self.assertEqual(result, expected)
    
    def test_get_score_yaml_path(self):
        """Test the score YAML path computation function."""
        test_cases = [
            # Basic cases
            ("My Scorecard", "Call Quality", "scorecards/My Scorecard/Call Quality.yaml"),
            ("Customer Service", "Response Time", "scorecards/Customer Service/Response Time.yaml"),
            
            # Cases with special characters
            ("Scorecard@#$", "Score!@#", "scorecards/Scorecard@#$/Score!@#.yaml"),
            ("My Scorecard...", "Call Quality...", "scorecards/My Scorecard.../Call Quality....yaml"),
            
            # Cases with spaces and mixed case
            ("My Score Card", "Call Quality Score", "scorecards/My Score Card/Call Quality Score.yaml"),
            ("CUSTOMER SERVICE", "RESPONSE TIME", "scorecards/CUSTOMER SERVICE/RESPONSE TIME.yaml"),
            
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
        self.assertEqual(str(result), "scorecards/Parent-Child/My Score.yaml")
        
        # Test with multiple levels
        result = get_score_yaml_path("Level1/Level2/Level3", "My Score")
        self.assertTrue(result.parent.exists())
        self.assertEqual(str(result), "scorecards/Level1-Level2-Level3/My Score.yaml")
    
    def test_get_score_yaml_path_existing_directory(self):
        """Test behavior with existing directories."""
        # Create a directory manually
        manual_dir = Path("scorecards/manual_dir")
        manual_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to create a file in the existing directory
        result = get_score_yaml_path("Manual Dir", "My Score")
        self.assertEqual(str(result), "scorecards/Manual Dir/My Score.yaml")
        
        # Verify the directory still exists
        self.assertTrue(result.parent.exists())
        
        # Try to create another file in the same directory
        result2 = get_score_yaml_path("Manual Dir", "Another Score")
        self.assertEqual(str(result2), "scorecards/Manual Dir/Another Score.yaml")
        self.assertTrue(result2.parent.exists())

if __name__ == '__main__':
    unittest.main() 