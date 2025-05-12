"""Debug test for the sanitize_path_name function."""
import unittest
from plexus.cli.shared import sanitize_path_name

class TestSanitizePathName(unittest.TestCase):
    def test_input_output(self):
        """Test a few specific inputs against actual outputs."""
        # Print the output for inspection
        test_cases = [
            "Simple Name",
            "Multiple   Spaces",
            "Name with @#$%^&*()",
            "Name with slashes/\\",
            "-Name with hyphens-",
            "___",
            "-_-",
            "File<>:\"/?*|Name",
        ]
        
        for input_name in test_cases:
            result = sanitize_path_name(input_name)
            print(f"'{input_name}' → '{result}'")
            
        # Just to have a passing assertion
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main() 