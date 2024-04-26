import re

from plexus.classifiers.Classifier import Classifier
from plexus.CustomLogging import logging

class KeywordClassifier(Classifier):
    def __init__(self, keywords):
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

