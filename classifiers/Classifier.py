from abc import ABC, abstractmethod

from ..CustomLogging import logging

class Classifier(ABC):
    """
    Abstract base class for a classifier, with a simple boolean classification function.
    """

    def __init__(self):
        pass

    @abstractmethod
    def is_relevant(self, text):
        """
        Determine if a given text is relevant.

        :param text: The text to classify.
        :return: A boolean indicating if the text is relevant.
        """
        pass