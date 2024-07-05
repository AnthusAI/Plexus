import re
from plexus.scores.Score import Score
from plexus.CustomLogging import logging

class KeywordClassifier(Score):
    """
    A keyword classifier that returns True if the input sentence contains any of the keywords or matches any of the regular expressions.

    This classifier supports both plain string keywords and regular expressions for more flexible matching.

    Examples
    --------
    Plain string keywords:
    - "child"
    - "children"
    - "dependent"

    Regular expressions:
    - r"\bchild\b"
    - r"\bchildren\b"
    - r"\bdependent\b"
    """
    def __init__(self, keywords, scorecard_name, score_name, **kwargs):
        super().__init__(scorecard_name=scorecard_name, score_name=score_name, **kwargs)
        self.keywords = keywords

    def is_relevant(self, sentence):
        """
        Check if the input sentence is relevant based on the keywords.

        :param sentence: The input sentence to check.
        :return: True if the sentence is relevant, False otherwise.
        """
        logging.debug(f"Checking if sentence is relevant: {sentence}")
        for keyword in self.keywords:
            if isinstance(keyword, str):
                pattern = re.escape(keyword)
                search_result = re.search(pattern, sentence, re.IGNORECASE)
            elif hasattr(keyword, 'search'):
                search_result = keyword.search(sentence)
            else:
                raise ValueError("Keyword must be a string or a compiled regular expression")

            if search_result:
                logging.debug(f"  True: {keyword}")
                return True
        return False

    def load_context(self, context=None):
        """
        Load any necessary artifacts or models based on the MLflow context.

        This function is required by the standard MLFlow model interface for running inference in production.
        """
        pass

    def predict(self, model_input: Score.ModelInput):
        """
        Make predictions on the input data.

        :param model_input: The input data for making predictions, which conforms to Score.ModelInput.
        :return: The predictions, which can be one of the supported output types (numpy.ndarray, pandas.Series, pandas.DataFrame, List, Dict, pyspark.sql.DataFrame).
        """
        return Score.ModelOutput(
            classification = self.is_relevant(model_input.transcript)
        )

    def predict_validation(self):
        pass
    def register_model(self):
        pass
    def save_model(self):
        pass