import os
from datetime import datetime
from .StorageBackend import StorageBackend

class FileStorageBackend(StorageBackend):

    def compute_file_path(self, *, year=None, month=None, day=None, scorecard_id, report_id, job_id, suffix=None, extension):
        # Use current date for year, month, and day if not provided
        now = datetime.now()
        year = year if year is not None else now.year
        month = month if month is not None else now.month
        day = day if day is not None else now.day

        # Constructs the file path based on the provided parameters
        directory_path = os.path.join(self.base_path, f"year={year}", f"month={month:02d}", f"day={day:02d}",
                                      f"scorecard_id={scorecard_id}", f"report_id={report_id}")
        file_name = f"{job_id}{suffix}.{extension}"
        return os.path.join(directory_path, file_name)

    def save_file(self, *, tmp_path, target_path):
        # Creates the target directory if it does not exist
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        # Moves the file from tmp_path to target_path
        os.rename(tmp_path, target_path)
