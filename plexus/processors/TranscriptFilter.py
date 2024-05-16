from abc import ABC, abstractmethod

class TranscriptFilter(ABC):

    @abstractmethod
    def process(self, *, transcript):
        pass