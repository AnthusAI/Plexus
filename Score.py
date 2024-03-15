from abc import ABC, abstractmethod

from plexus.CustomLogging import logging

class Score(ABC):
    def __init__(self, *, transcript, name=None):
        self.transcript = transcript
        self.name = name

    def process_transcript(self, transcript):
        """
        Process the transcript. By default, this method returns the transcript as is.

        :param transcript: The transcript to process.
        :return: The processed transcript.
        """
        return transcript

    @abstractmethod
    def compute_result(self):
        """
        Compute the score based on the transcript.

        :return: The score result.
        """
        pass