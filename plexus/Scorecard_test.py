import unittest
from decimal import Decimal

from plexus.Scorecard import Scorecard
from plexus.scorecards import TermLifeAI

class MockScoreResult:
    def __init__(self, value):
        self.value = value
        self.element_results = "dummy_element_results"
        self.metadata = {}

class MockScore:
    def __init__(self, transcript):
        self.transcript = transcript

    def compute_result(self):
        # Mock computation, return a dummy result wrapped in an object with a 'value' attribute
        return MockScoreResult(42)

    def accumulated_expenses(self):
        # Mock expenses, return dummy values
        return {
            'prompt_tokens': 10,
            'completion_tokens': 20,
            'input_cost': Decimal('0.5'),
            'output_cost': Decimal('0.3'),
            'total_cost': Decimal('0.8')
        }

# class TestScorecard(unittest.TestCase):
#     def setUp(self):
#         self.scorecard = Scorecard(scorecard_folder_path="scorecards/TermLifeAI")

#     def test_get_score_result(self):
#         score_result = self.scorecard.get_score_result(
#             score_name="Dependents",
#             transcript="Well hello there!")
        
#         self.assertEqual(score_result.value, 42)  # Compare the value attribute, not the object itself
#         self.assertEqual(self.scorecard.prompt_tokens, 10)
#         self.assertEqual(self.scorecard.completion_tokens, 20)
#         self.assertEqual(self.scorecard.input_cost, Decimal('0.5'))
#         self.assertEqual(self.scorecard.output_cost, Decimal('0.3'))
#         self.assertEqual(self.scorecard.total_cost, Decimal('0.8'))

if __name__ == '__main__':
    unittest.main()