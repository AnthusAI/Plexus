import pytest
import pandas as pd
from unittest.mock import patch
from sklearn.datasets import make_classification
from plexus.scores.MLClassifier import MLClassifier

class ConcreteMLClassifier(MLClassifier):
    def train_model(self):
        self.model = "trained_model"

    def predict_validation(self):
        self.val_labels = self.dataframe[self.parameters.score_name]
        self.val_predictions = self.val_labels

    def register_model(self):
        pass

    def save_model(self):
        pass

    def predict(self, model_input):
        return {"prediction": pd.Series(["__label__relevant"])}

@pytest.fixture
def sample_data():
    X, y = make_classification(n_samples=100, n_features=20, n_classes=2, random_state=42)
    df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(20)])
    df["label"] = y
    df["Transcription"] = "Sample transcription"
    return df

@pytest.fixture
def classifier_parameters():
    return {
        "scorecard_name": "test_scorecard",
        "score_name": "label",
        "data": {
            "percentage": 100.0,
            "processors": []
        }
    }

@pytest.fixture
def classifier(sample_data, classifier_parameters):
    class TestParameters(MLClassifier.Parameters):
        pass

    TestParameters.data = sample_data
    return ConcreteMLClassifier(**classifier_parameters)

def test_initialization(classifier):
    assert classifier.parameters.scorecard_name == "test_scorecard"
    assert classifier.parameters.score_name == "label"
    assert classifier._is_multi_class is None

# @patch('plexus.scores.MLClassifier.DataCache')
# def test_load_data(mock_data_cache, monkeypatch, classifier, sample_data):
#     # Mock environment variables
#     monkeypatch.setenv('PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME', 'dummy_db')
#     monkeypatch.setenv('PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME', 'dummy_bucket')
#     monkeypatch.setenv('PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME', 'dummy_bucket')
#     monkeypatch.setenv('AWS_REGION_NAME', 'us-west-2')

#     # Mock the DataCache methods
#     mock_data_cache.return_value.load_dataframe_from_excel.return_value = sample_data

#     classifier.load_data(excel="dummy_path")
#     assert not classifier.dataframe.empty

def test_analyze_dataset(classifier, sample_data):
    classifier.dataframe = sample_data
    classifier.analyze_dataset()

def test_process_data(classifier, sample_data):
    classifier.dataframe = sample_data
    classifier.process_data()
    assert not classifier.dataframe.empty

# def test_evaluate_model(classifier, sample_data):
#     classifier.dataframe = sample_data
#     classifier.val_labels = sample_data["label"]
#     classifier.val_predictions = sample_data["label"]
#     classifier.val_confidence_scores = pd.Series([0.9] * len(sample_data))
#     classifier.label_map = {0: "No", 1: "Yes"}
#     classifier.evaluate_model()

def test_is_relevant(classifier):
    assert classifier.is_relevant("This is a relevant text")