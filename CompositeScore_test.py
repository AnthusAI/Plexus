import os
import re
import json
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from plexus.CompositeScore import CompositeScore

class MockCompositeScore(CompositeScore):
    def compute_element(self, name, transcript):
        pass  # Dummy implementation

    def compute_result(self):
        pass  # Dummy implementation

    def construct_system_prompt(self, *, transcript):
        return "Mock prompt"  # Dummy implementation

class TestCompositeScore(unittest.TestCase):

    def setUp(self):
        self.transcript = "This is a test transcript."
        self.composite_score = MockCompositeScore(transcript=self.transcript)
        self.composite_score.filtered_transcript = "Filtered transcript."
        self.composite_score.compute_element = MagicMock()
        self.composite_score.element_results = []  # Ensure this is initialized for tests that use it

    def test_element_with_provided_transcript(self):
        # Test the element method with a provided transcript
        self.composite_score.compute_element.return_value = MagicMock(is_yes=lambda: True)
        result = self.composite_score.compute_element(name="test_element", transcript=self.transcript)
        self.composite_score.compute_element.assert_called_once_with(name="test_element", transcript=self.transcript)
        self.assertTrue(result)

    # def test_element_with_no_transcript(self):
    #     # Test the element method with no transcript provided (should use filtered_transcript)
    #     self.composite_score.compute_element.return_value = MagicMock(is_yes=lambda: False)
    #     result = self.composite_score.compute_element(name="test_element")
    #     self.composite_score.compute_element.assert_called_with(name="test_element", transcript=self.composite_score.filtered_transcript)
    #     self.assertFalse(result)

    def test_element_with_no_cached_result(self):
        # Test the element method when there is no cached result
        self.composite_score.compute_element.return_value = MagicMock(is_yes=lambda: True)
        result = self.composite_score.compute_element(name="test_element")
        self.assertTrue(result)
        self.composite_score.compute_element.assert_called_once()

class TestGetElementByName(unittest.TestCase):

    def setUp(self):
        class MockCompositeScore(CompositeScore):
            def compute_element(self, name, transcript):
                pass

            def compute_result(self):
                pass

            def construct_system_prompt(self, *, transcript):
                return "Please answer the following questions about dependents:"

        self.composite_score = MockCompositeScore(transcript="Test transcript")
        self.composite_score.elements = [
            {'name': 'element1', 'value': 'value1'},
            {'name': 'element2', 'value': 'value2'}
        ]

    def test_get_element_by_name_found(self):
        # Test that the correct element is returned when it exists
        element = self.composite_score.get_element_by_name(name='element1')
        self.assertIsNotNone(element)
        self.assertEqual(element['name'], 'element1')
        self.assertEqual(element['value'], 'value1')

    def test_get_element_by_name_not_found(self):
        # Test that None is returned when the element does not exist
        element = self.composite_score.get_element_by_name(name='nonexistent_element')
        self.assertIsNone(element)

class TestAccumulatedExpenses(unittest.TestCase):

    def setUp(self):
        class MockCompositeScore(CompositeScore):
            def compute_element(self, name, transcript):
                pass

            def compute_result(self):
                pass

            def construct_system_prompt(self, *, transcript):
                return "Please answer the following questions about dependents:"

        self.composite_score = MockCompositeScore(transcript="Test transcript")

    def test_accumulated_expenses(self):
        # Set the expense attributes
        self.composite_score.prompt_tokens = 100
        self.composite_score.completion_tokens = 200
        self.composite_score.input_cost = Decimal('1.50')
        self.composite_score.output_cost = Decimal('2.50')
        self.composite_score.total_cost = Decimal('4.00')

        # Call the method
        expenses = self.composite_score.accumulated_expenses()

        # Check that the returned dictionary matches the expected values
        expected_expenses = {
            'llm_request_count': 0,
            'prompt_tokens': 100,
            'completion_tokens': 200,
            'input_cost': Decimal('1.50'),
            'output_cost': Decimal('2.50'),
            'total_cost': Decimal('4.00')
        }
        self.assertEqual(expenses, expected_expenses)

class TestTranscriptChunker(unittest.TestCase):

    def setUp(self):
        self.transcript = "This is a test transcript."
        self.composite_score = MockCompositeScore(transcript=self.transcript)

    def test_short_transcript(self):
        transcript = "This is a short transcript."
        chunks = self.composite_score.break_transcript_into_chunks(transcript)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], transcript)

    def test_no_need_to_split_on_delimiter(self):
        transcript = "First part.\n...\nSecond part."
        chunks = self.composite_score.break_transcript_into_chunks(transcript)
        # Expecting a single chunk since the transcript does not exceed the max chunk size
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], transcript)

    def test_split_on_delimiter_with_long_transcript(self):
        transcript = "a" * 1000 + "\n...\n" + "b" * 1000
        chunks = self.composite_score.break_transcript_into_chunks(transcript)
        self.assertEqual(len(chunks), 2, "Expected transcript to be split into two chunks")
        # Use regex to check the start of the second chunk for 'b's, accounting for potential inclusion of the delimiter
        self.assertTrue(re.match(r'^b+', chunks[1]), "Second chunk does not start with expected 'b' pattern")

    def test_balanced_split(self):
        transcript = "a" * 1100 + "\n...\n" + "b" * 1100
        max_chunk_size = 2000
        chunks = self.composite_score.break_transcript_into_chunks(transcript, max_chunk_size=max_chunk_size)
        self.assertEqual(len(chunks), 2, "Expected transcript to be split into two chunks")
        # Adjust the assertion to account for the delimiter at the end of the first chunk
        self.assertTrue(re.match(r'a{1000}', chunks[0]), "First chunk does not contain the expected pattern of 1000 'a's")
        self.assertTrue(re.match(r'b{1000}', chunks[1]), "Second chunk does not contain the expected pattern of 1000 'b's")
        
    def test_unbalanced_split_fallback(self):
        transcript = "a" * 1999 + " " + "b"
        chunks = self.composite_score.break_transcript_into_chunks(transcript, 2000)
        self.maxDiff = None
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= 2000 for chunk in chunks))
        self.assertEqual(chunks[0], "a" * 1999)
        self.assertEqual(chunks[1], "b")

class TestExtractYamlSection(unittest.TestCase):

    def test_extract_yaml_section_with_valid_section(self):
        markdown_content = """
# Preprocessing
tokenize: true
lowercase: true

# Decision Tree
- decision: first_decision
  true: second_decision
  false: third_decision
"""
        preprocessing_expected = {'tokenize': True, 'lowercase': True}
        decision_tree_expected = [{'decision': 'first_decision', True: 'second_decision', False: 'third_decision'}]

        preprocessing_result = MockCompositeScore.extract_yaml_section(markdown_content, 'Preprocessing')
        decision_tree_result = MockCompositeScore.extract_yaml_section(markdown_content, 'Decision Tree')

        self.assertEqual(preprocessing_expected, preprocessing_result)
        self.assertEqual(decision_tree_expected, decision_tree_result)

    def test_extract_yaml_section_with_missing_section(self):
        markdown_content = """
# Preprocessing
tokenize: true
lowercase: true
"""
        result = MockCompositeScore.extract_yaml_section(markdown_content, 'Nonexistent Section')
        self.assertIsNone(result)

    def test_extract_yaml_section_with_empty_section(self):
        markdown_content = """
# Preprocessing

# Decision Tree
"""
        result = MockCompositeScore.extract_yaml_section(markdown_content, 'Preprocessing')
        self.assertEqual(None, result)

class TestJSONSerialization(unittest.TestCase):
    def setUp(self):
        self.score = MockCompositeScore(transcript="Test transcript")
        self.session_id = "12345"
        self.output_directory_path = "tests/output"

    def test_save_results_to_json(self):
        # Save the results to a JSON file
        self.score.save_results_to_json(self.session_id, self.output_directory_path)

        # Define the expected output file path
        output_file_path = os.path.join(self.output_directory_path, f"{self.session_id}.json")

        # Check that the output file exists
        self.assertTrue(os.path.exists(output_file_path))

        # Load the data from the output file
        with open(output_file_path, 'r') as file:
            data = json.load(file)

        # Check that the loaded data matches the original data
        self.assertEqual(data, self.score.to_dict())

        # Clean up the test output directory
        os.remove(output_file_path)

    def test_load_results_from_json(self):
        # Save the results to a JSON file
        self.score.save_results_to_json(self.session_id, self.output_directory_path)

        # Load the results from the JSON file into a new CompositeScore instance
        loaded_score = MockCompositeScore.load_results_from_json(self.session_id, self.output_directory_path)

        # Check that the loaded CompositeScore instance matches the original CompositeScore instance
        self.assertEqual(loaded_score.to_dict(), self.score.to_dict())

        # Clean up the test output directory
        os.remove(os.path.join(self.output_directory_path, f"{self.session_id}.json"))

if __name__ == '__main__':
    unittest.main()