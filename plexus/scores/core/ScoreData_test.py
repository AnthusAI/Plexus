import os
import pandas as pd
from unittest.mock import patch, MagicMock
from plexus.data.DataCache import DataCache
from plexus.scores.Score import Score

class MockDataCache(DataCache):
    def load_dataframe(self, *args, **kwargs):
        return pd.DataFrame({
            'score': [1, 2, 3]
        })

class ConcreteScore(Score):
    def predict_validation(self):
        pass
    def register_model(self):
        pass
    def save_model(self):
        pass
    def load_context(self, context):
        pass
    def predict(self, model_input: Score.Input):
        return "computed score"

# @patch('plexus.scores.core.ScoreData.console')
# def test_load_data(mock_load_data_cache):
#     # Create an instance of the ConcreteScore class
#     score = ConcreteScore(
#         scorecard_name="Test scorecard",
#         score_name="Test score",
#         data={'class': 'plexus.scores.core.ScoreData_test.MockDataCache'}
#     )

#     # Call the load_data method
#     score.load_data(queries=['query1', 'query2'])

#     # Assertions to ensure the dataframe was loaded correctly
#     assert not score.dataframe.empty
#     assert 'score' in score.dataframe.columns
#     mock_console.print.assert_called()  # Ensure console print was called