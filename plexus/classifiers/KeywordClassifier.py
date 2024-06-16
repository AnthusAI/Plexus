import re
from plexus.classifiers.Score import Score
from plexus.CustomLogging import logging

class KeywordClassifier(Score):
    def __init__(self, keywords):
        super().__init__()
        self.keywords = keywords

    def is_relevant(self, sentence):
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
        # Implement the context loading logic if necessary
        pass

    def predict(self, context, model_input):
        # Implement prediction logic using the is_relevant method
        return [self.is_relevant(sentence) for sentence in model_input]
