import os
import functools
import json
from abc import ABC, abstractmethod
import mlflow.pyfunc
from plexus.CustomLogging import logging
from pydantic import BaseModel, ValidationError

class Classifier(ABC, mlflow.pyfunc.PythonModel):
    """
    Abstract base class for a classifier, with a simple boolean classification function.
    """

    def __init__(self, **parameters):
        try:
            self.parameters = self.Parameters(**parameters)
        except ValidationError as e:
            Classifier.log_validation_errors(e)
            raise

    class Parameters(BaseModel):
        scorecard_name: str
        score_name: str
        configuration: dict

    @staticmethod
    def log_validation_errors(error: ValidationError):
        error_messages = []
        for error_detail in error.errors():
            field = ".".join(str(loc) for loc in error_detail["loc"])
            message = error_detail["msg"]
            error_messages.append(f"Field: {field}, Error: {message}")

        logging.error("Parameter validation errors occurred:")
        for message in error_messages:
            logging.error(message)

    def ensure_report_directory_exists(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            report_directory_path = f"./reports/{self.parameters.scorecard_name}/{self.parameters.score_name}/"
            if not os.path.exists(report_directory_path):
                os.makedirs(report_directory_path)
            return func(self, *args, **kwargs)
        return wrapper

    @ensure_report_directory_exists
    def record_configuration(self, configuration):
        """
        Record the provided configuration dictionary as a JSON file in the appropriate report folder for this model.

        :param configuration: Dictionary containing the configuration to be recorded.
        :type configuration: dict
        """
        directory_path = f"reports/{self.parameters.scorecard_name}/{self.parameters.score_name}/"
        file_name = os.path.join(directory_path, "configuration.json")

        with open(file_name, 'w') as json_file:
            json.dump(configuration, json_file, indent=4)

    @abstractmethod
    def load_context(self, context):
        """
        Load any necessary artifacts or models based on the MLflow context.
        """
        pass

    @abstractmethod
    def predict(self, context, model_input):
        """
        Make predictions on the input data.

        :param context: MLflow context for the prediction.
        :param model_input: The input data for making predictions (agnostic dataframe).
        :return: The predictions.
        """
        pass
