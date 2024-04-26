from abc import ABC, abstractmethod
import os

class StorageBackend(ABC):

    def __init__(self, *, base_path):
        self.base_path = base_path

    @abstractmethod
    def compute_file_path(self, *, year, month, day, scorecard_id, report_id, job_id, extension):
        pass

    @abstractmethod
    def save_file(self, *, tmp_path, target_path):
        pass
