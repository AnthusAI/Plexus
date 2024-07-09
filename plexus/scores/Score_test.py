import os
import json
import pytest
from pydantic import ValidationError
from plexus.scores.Score import Score

class ConcreteScore(Score):
    def predict_validation(self):
        pass
    def register_model(self):
        pass
    def save_model(self):
        pass
    def load_context(self, context):
        pass
    def predict(self, model_input: Score.ModelInput):
        return "computed score"

def test_compute_score_result():
    score = ConcreteScore(
        scorecard_name="Test scorecard",
        score_name="Test score"
    )
    result = score.predict(
        Score.ModelInput(
            transcript="Test transcript"
        )
    )
    assert result == "computed score"

def test_invalid_parameters():
    with pytest.raises(ValidationError):
        ConcreteScore(scorecard_name=123, score_name=None)

def test_report_directory_creation(tmp_path):
    score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
    report_directory = tmp_path / "reports" / "Test_scorecard" / "Test_score"
    score.report_directory_path = lambda: str(report_directory)
    score.report_file_name("test_file.txt")
    assert report_directory.exists()

def test_report_file_name():
    score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
    report_file = score.report_file_name("test_file.txt")
    expected_path = "./reports/Test_scorecard/Test_score/test_file.txt".replace(' ', '_')
    assert report_file == expected_path

def test_record_configuration():
    score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
    configuration = {"param1": "value1", "param2": "value2"}
    score.record_configuration(configuration)
    config_path = score.report_file_name("configuration.json")
    with open(config_path, 'r') as json_file:
        recorded_config = json.load(json_file)
    assert recorded_config == configuration

def test_report_file_name(tmp_path):
    score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
    report_directory = tmp_path / "reports" / "Test_scorecard" / "Test_score"
    score.report_directory_path = lambda: str(report_directory)
    report_file = score.report_file_name("explicit_test_file.txt")
    expected_path = str(report_directory / "explicit_test_file.txt").replace(' ', '_')
    assert report_file == expected_path
    assert report_directory.exists()
    
def test_ensure_report_directory_exists_creates_directory(tmp_path):
    score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
    report_directory = tmp_path / "reports" / "Test_scorecard" / "Test_score"
    score.report_directory_path = lambda: str(report_directory)
    score.report_file_name("test_file.txt")
    assert report_directory.exists()

def test_ensure_report_directory_exists_no_error_if_exists(tmp_path):
    score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
    report_directory = tmp_path / "reports" / "Test_scorecard" / "Test_score"
    report_directory.mkdir(parents=True, exist_ok=True)
    score.report_directory_path = lambda: str(report_directory)
    score.report_file_name("test_file.txt")
    assert report_directory.exists()
