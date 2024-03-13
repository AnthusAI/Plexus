import unittest

from .ScoreResult import ScoreResult

class TestScoreResult(unittest.TestCase):

    def test_score_result_initialization(self):
        score_result = ScoreResult(value="Pass", element_results=["element1", "element2"], metadata={"key": "value"})
        
        self.assertEqual(score_result.value, "Pass")
        self.assertEqual(score_result.element_results, ["element1", "element2"])
        self.assertEqual(score_result.metadata, {"key": "value"})

    def test_score_result_equality_with_score_result(self):
        score_result1 = ScoreResult(value="Pass")
        score_result2 = ScoreResult(value="pass")
        
        self.assertEqual(score_result1, score_result2)

    def test_score_result_equality_with_string(self):
        score_result = ScoreResult(value="Pass")
        self.assertEqual(score_result, "pass")

    def test_score_result_equality_with_different_types(self):
        score_result = ScoreResult(value="Pass")
        self.assertNotEqual(score_result, 42)

    def test_score_result_repr(self):
        score_result = ScoreResult(value="Pass", element_results=["element1", "element2"], metadata={"key": "value"})
        expected_repr = "ScoreResult(Pass)\n, element_results=['element1', 'element2'], metadata={'key': 'value'}"
        
        self.assertEqual(repr(score_result), expected_repr)
        
if __name__ == '__main__':
    unittest.main()