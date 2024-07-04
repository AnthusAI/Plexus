import os
import functools
import json
from abc import ABC, abstractmethod
import mlflow.pyfunc
from plexus.CustomLogging import logging
from pydantic import BaseModel, ValidationError

class Score(ABC, mlflow.pyfunc.PythonModel):
    """
    Abstract base class for a score.

    This class provides a framework for implementing different scoring models. 
    It includes methods for parameter validation, report directory management, 
    and configuration recording. Subclasses must implement the `load_context` 
    and `predict` methods.

    Attributes
    ----------
    parameters : Parameters
        An instance of the Parameters class containing the scorecard and score names.
    """

    class Parameters(BaseModel):
        """
        Parameters required for scoring.

        Attributes
        ----------
        scorecard_name : str
            The name of the scorecard.
        score_name : str
            The name of the score.
        """
        scorecard_name: str
        score_name: str

    def __init__(self, **parameters):
        """
        Initialize the Score instance with the given parameters.

        Parameters
        ----------
        **parameters : dict
            Arbitrary keyword arguments that are used to initialize the Parameters instance.

        Raises
        ------
        ValidationError
            If the provided parameters do not pass validation.
        """
        try:
            self.parameters = self.Parameters(**parameters)
        except ValidationError as e:
            Score.log_validation_errors(e)
            raise

    @staticmethod
    def log_validation_errors(error: ValidationError):
        """
        Log validation errors for the parameters.

        Parameters
        ----------
        error : ValidationError
            The validation error object containing details about the validation failures.
        """
        error_messages = []
        for error_detail in error.errors():
            field = ".".join(str(loc) for loc in error_detail["loc"])
            message = error_detail["msg"]
            error_messages.append(f"Field: {field}, Error: {message}")

        logging.error("Parameter validation errors occurred:")
        for message in error_messages:
            logging.error(message)

    def ensure_report_directory_exists(func):
        """
        Decorator to ensure the report directory exists before executing the decorated function.

        Parameters
        ----------
        func : function
            The function to be decorated.

        Returns
        -------
        function
            The wrapped function that ensures the report directory exists.
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not os.path.exists(self.report_directory_path()):
                os.makedirs(self.report_directory_path())
            return func(self, *args, **kwargs)
        return wrapper

    def report_directory_path(self):
        return f"./reports/{self.parameters.scorecard_name}/{self.parameters.score_name}/".replace(' ', '_')

    @ensure_report_directory_exists
    def report_file_name(self, file_name):
        """
        Generate the full path for a report file within the report directory.

        Calling this function will implicitly trigger the function to ensure that the report directory exists.

        Parameters
        ----------
        file_name : str
            The name of the report file.

        Returns
        -------
        str
            The full path to the report file with spaces replaced by underscores.
        """
        return os.path.join(self.report_directory_path(), file_name).replace(' ', '_')

    @ensure_report_directory_exists
    def record_configuration(self, configuration):
        """
        Record the provided configuration dictionary as a JSON file in the appropriate report folder for this model.

        Parameters
        ----------
        configuration : dict
            Dictionary containing the configuration to be recorded.

        Notes
        -----
        The configuration JSON file can be useful as an artifact for logging in MLFlow.
        """
        file_name = self.report_file_name("configuration.json")

        with open(file_name, 'w') as json_file:
            json.dump(configuration, json_file, indent=4)
