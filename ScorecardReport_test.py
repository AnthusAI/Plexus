from decimal import Decimal

from .ScorecardReport import ScorecardReport
from .CompositeScore import CompositeScore
from .ScoreResult import ScoreResult

class TestCompositeScore1(CompositeScore):
    def __init__(self, *, transcript):
        super().__init__(transcript=transcript)
        self.reasoning = ["Test reasoning 1"]
        self.relevant_quotes = ["Test quote 1"]
        self.llm_request_count = 0
        self.prompt_tokens     = 0
        self.completion_tokens = 0
        self.input_cost =  Decimal('0.0')
        self.output_cost = Decimal('0.0')
        self.total_cost =  Decimal('0.0')

    def construct_system_prompt(self, *, transcript):
        return "Test system prompt 1"

    def compute_element(self, *, name, transcript=None):
        return ScoreResult(
            name=name,
            value='Yes',
            reasoning='Test reasoning 1',
            relevant_quote='Test quote 1'
        )

class TestCompositeScore2(CompositeScore):
    def __init__(self, *, transcript):
        super().__init__(transcript=transcript)
        self.reasoning = ["Test reasoning 2"]
        self.relevant_quotes = ["Test quote 2"]
        self.llm_request_count = 0
        self.prompt_tokens     = 0
        self.completion_tokens = 0
        self.input_cost =  Decimal('0.0')
        self.output_cost = Decimal('0.0')
        self.total_cost =  Decimal('0.0')

    def construct_system_prompt(self, *, transcript):
        return "Test system prompt 2"

    def compute_element(self, *, name, transcript=None):
        return ScoreResult(
            name=name,
            value='No',
            reasoning='Test reasoning 2',
            relevant_quote='Test quote 2'
        )

class TestCompositeScore3(CompositeScore):
    def __init__(self, *, transcript):
        super().__init__(transcript=transcript)
        self.reasoning = ["Test reasoning 3"]
        self.relevant_quotes = ["Test quote 3"]
        self.llm_request_count = 0
        self.prompt_tokens     = 0
        self.completion_tokens = 0
        self.input_cost =  Decimal('0.0')
        self.output_cost = Decimal('0.0')
        self.total_cost =  Decimal('0.0')


    def construct_system_prompt(self, *, transcript):
        return "Test system prompt 3"

    def compute_element(self, *, name, transcript=None):
        return ScoreResult(
            name=name,
            value='Yes',
            reasoning='Test reasoning 3',
            relevant_quote='Test quote 3'
        )

def test_html_report_with_actual_composite_score():
    # Define some mock transcripts
    transcripts = ["Transcript 1", "Transcript 2", "Transcript 3"]

    # Create TestCompositeScore instances and convert them to dictionaries
    composite_scores = [TestCompositeScore1, TestCompositeScore2, TestCompositeScore3]
    results = [score(transcript=transcript).to_dict() for score, transcript in zip(composite_scores, transcripts)]

    # Define some mock metrics
    metrics = {
        'overall_accuracy': {
            'label': "Overall Accuracy",
            'value': 0.95
        },
        'another_metric': {
            'label': "Another Metric",
            'value': 0.85
        }
    }

    # Create a ScorecardReport instance
    report_generator = ScorecardReport(results, metrics)

    # Generate the HTML report
    html_report = report_generator.generate_html_report()

    # Check if the report is not empty
    assert html_report != ""

    # Print the report for manual inspection
    print("HTML Report:")
    print(html_report)

def test_csv_report_with_actual_composite_score():
    # Define some mock transcripts
    transcripts = ["Transcript 1", "Transcript 2", "Transcript 3"]

    # Create TestCompositeScore instances and convert them to dictionaries
    composite_scores = [TestCompositeScore1, TestCompositeScore2, TestCompositeScore3]
    results = [score(transcript=transcript).to_dict() for score, transcript in zip(composite_scores, transcripts)]

    # Define some mock metrics
    metrics = {
        'overall_accuracy': {
            'label': "Overall Accuracy",
            'value': 0.95
        },
        'another_metric': {
            'label': "Another Metric",
            'value': 0.85
        }
    }

    # Create a ScorecardReport instance
    report_generator = ScorecardReport(results, metrics)

    # Generate the CSV report
    csv_report = report_generator.generate_csv_report()

    # Check if the report is not empty
    assert csv_report != ""

    # Print the report for manual inspection
    print("CSV Report:")
    print(csv_report)

if __name__ == '__main__':
    unittest.main()