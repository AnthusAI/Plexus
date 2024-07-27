import os
import json
import mlflow
import pandas as pd
import numpy as np
import inspect
import functools
from pydantic import BaseModel, ValidationError, field_validator
from typing import Optional, Union
from abc import ABC, abstractmethod
import matplotlib.pyplot as plt
import seaborn as sns
from tensorflow.keras.utils import plot_model
from sklearn.metrics import confusion_matrix
from sklearn.metrics import roc_curve, auc, precision_recall_curve
from sklearn.metrics import accuracy_score, f1_score, recall_score, precision_score
from sklearn.calibration import calibration_curve
import matplotlib.ticker as ticker
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from plexus.CustomLogging import logging, console
from sklearn.preprocessing import LabelBinarizer
from collections import Counter
import xgboost as xgb

from plexus.scores.core.ScoreData import ScoreData
from plexus.scores.core.ScoreVisualization import ScoreVisualization
from plexus.scores.core.ScoreMLFlow import ScoreMLFlow
from plexus.scores.core.utils import ensure_report_directory_exists

class Score(ABC, mlflow.pyfunc.PythonModel,
    # Core Score functionality.   
    ScoreData,
    ScoreVisualization,
    ScoreMLFlow
):
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
        data : dict
            Dictionary containing data-related parameters.
        """
        id: Optional[Union[str, int]] = None
        scorecard_name: str
        score_name: str
        data: Optional[dict] = None

        @field_validator('data')
        def convert_data_percentage(cls, value):
            """
            Convert the percentage value in the data dictionary to a float.

            Parameters
            ----------
            value : dict
                Dictionary containing data-related parameters.

            Returns
            -------
            dict
                Updated dictionary with the percentage value converted to float.
            """
            if 'percentage' in value:
                value['percentage'] = float(str(value['percentage']).strip().replace('%', ''))
            else:
                value['percentage'] = 100.0
            return value

    class ScoreInput(BaseModel):
        """
        Model input data structure.

        Attributes
        ----------
        text : str
            The text to be classified.
        """
        text: str
        metadata: Optional[dict] = None

    class ScoreResult(BaseModel):
        """
        Model output data structure.

        Attributes
        ----------
        score : str
            The predicted score label.
        """
        score_name: str
        score: Union[str, bool]
    
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
            logging.info("Initializing [magenta1][b]Score[/b][/magenta1]")
            self._is_multi_class = None
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

    @abstractmethod
    def train_model(self):
        """
        Train the model on the training data.

        Returns
        -------
        object
            The trained model.
        """
        pass

    @abstractmethod
    def predict_validation(self):
        """
        Predict on the validation set.

        This method should be implemented by subclasses to provide the prediction logic on the validation set.
        """
        pass

    def evaluate_model(self):
        """
        Evaluate the model on the validation data.

        Returns
        -------
        dict
            Dictionary containing evaluation metrics.
        """
        print("Generating evaluation metrics...")

        self.predict_validation()

        logging.info(f"val_labels type: {type(self.val_labels)}, shape: {self.val_labels.shape}, sample: {self.val_labels[:5]}")
        logging.info(f"val_predictions type: {type(self.val_predictions)}, shape: {self.val_predictions.shape}, sample: {self.val_predictions[:5]}")
        
        self.val_predictions_labels = self.val_predictions

        accuracy = accuracy_score(self.val_labels, self.val_predictions_labels)
        f1 = f1_score(self.val_labels, self.val_predictions_labels, average='weighted')
        recall = recall_score(self.val_labels, self.val_predictions_labels, average='weighted')
        precision = precision_score(self.val_labels, self.val_predictions_labels, average='weighted')

        mlflow.log_metric("validation_f1_score", f1)
        mlflow.log_metric("validation_recall", recall)
        mlflow.log_metric("validation_precision", precision)

        print(f"Validation Accuracy: {accuracy:.4f}")
        print(f"Validation F1 Score: {f1:.4f}")
        print(f"Validation Recall: {recall:.4f}")
        print(f"Validation Precision: {precision:.4f}")

        print("Generating visualizations...")

        logging.info(f"Shape of self.val_labels: {self.val_labels.shape}")
        logging.info(f"Sample of self.val_labels: {self.val_labels[:5]}")
        logging.info(f"Shape of self.val_predictions: {self.val_predictions.shape}")
        logging.info(f"Sample of self.val_predictions: {self.val_predictions[:5]}")
        logging.info(f"Shape of self.val_confidence_scores: {self.val_confidence_scores.shape}")
        logging.info(f"Sample of self.val_confidence_scores: {self.val_confidence_scores[:5]}")
        logging.info(f"Unique values in self.val_labels: {set(self.val_labels)}")
        logging.info(f"Unique values in self.val_predictions: {set(self.val_predictions)}")
        logging.info(f"label_map: {self.label_map}")

        self._plot_confusion_matrix()
        self._plot_roc_curve()
        self._plot_precision_recall_curve()
        self._plot_training_history()
        self._plot_calibration_curve()

        metrics = {
            "validation_accuracy": accuracy,
            "validation_f1_score": f1,
            "validation_recall": recall,
            "validation_precision": precision
        }
        if hasattr(self, 'history') and hasattr(self.history, 'history'):
            metrics.update({
                "training_loss": self.history.history['loss'][-1],
                "training_accuracy": self.history.history['accuracy'][-1],
                "validation_loss": self.history.history['val_loss'][-1],
                "validation_accuracy": self.history.history['val_accuracy'][-1]
            })
        self._record_metrics(metrics)

        mlflow.end_run()

    @abstractmethod
    def register_model(self):
        """
        Register the model with the model registry.
        """
        pass

    @abstractmethod
    def save_model(self):
        """
        Save the model to the model registry.
        """
        pass

    def load_context(self, context):
        """
        Load the trained model and any necessary artifacts based on the MLflow context.

        Parameters
        ----------
        context : mlflow.pyfunc.PythonModelContext
            The context object containing artifacts and other information.
        """
        self.model = mlflow.keras.load_model(context.artifacts["model"])

    @abstractmethod
    def predict(self, model_input: ScoreInput):
        """
        Make predictions on the input data.

        Parameters
        ----------
        model_input : Score.ScoreInput
            The input data for making predictions.

        Returns
        -------
        dict
            The predictions, which can be one of the supported output types (numpy.ndarray, pandas.Series,
            pandas.DataFrame, List, Dict, pyspark.sql.DataFrame).
        """
        pass

    def is_relevant(self, text):
        """
        Determine if the given text is relevant using the predict method.

        Parameters
        ----------
        text : str
            The text to be classified.

        Returns
        -------
        bool
            True if the text is classified as relevant, False otherwise.
        """
        clean_text = text.replace('\n', ' ').strip()
        model_input = pd.DataFrame([clean_text], columns=['text'])
        prediction = self.predict(model_input)['prediction'].iloc[0]
        return prediction == '__label__relevant'

    _sky_blue = (0.012, 0.635, 0.996)
    _fuchsia = (0.815, 0.2, 0.51)
    _red = '#DD3333'
    _green = '#339933'

    def _generate_model_diagram(self):
        """
        Generate and save a diagram of the model architecture.
        """
        file_name = self.report_file_name("model_diagram.png")
        plot_model(self.model, to_file=file_name, show_shapes=True, show_layer_names=True, rankdir='TB')
        mlflow.log_artifact(file_name)

    def setup_label_map(self, labels):
        """
        Set up a mapping from labels to integers.

        Parameters
        ----------
        labels : list
            List of unique labels.
        """
        unique_labels = sorted(set(labels))
        self.label_map = {label: i for i, label in enumerate(unique_labels)}
        logging.info(f"Label map: {self.label_map}")

    def train_model(self, X_train, y_train, X_val, y_val):
        """
        Train the XGBoost model with the specified positive class weight.

        Parameters
        ----------
        X_train : numpy.ndarray
            Training data features.
        y_train : numpy.ndarray
            Training data labels.
        X_val : numpy.ndarray
            Validation data features.
        y_val : numpy.ndarray
            Validation data labels.
        """
        pass

    def predict(self, X):
        """
        Make predictions on the input data.

        Parameters
        ----------
        X : numpy.ndarray
            Input data features.

        Returns
        -------
        numpy.ndarray
            Predicted labels.
        """
        pass
            
    def _record_metrics(self, metrics):
        """
        Record the provided metrics dictionary as a JSON file in the appropriate report folder for this model.

        Parameters
        ----------
        metrics : dict
            Dictionary containing the metrics to be recorded.

        Returns
        -------
        None
        """
        file_name = self.report_file_name("metrics.json")

        with open(file_name, 'w') as json_file:
            json.dump(metrics, json_file, indent=4)

    @property
    def is_multi_class(self):
        """
        Determine if the classification problem is multi-class.

        This property checks the unique labels in the dataframe to determine if the problem is multi-class.

        Returns
        -------
        bool
            True if the problem is multi-class, False otherwise.
        """
        if self._is_multi_class is None:
            unique_labels = self.dataframe[self.parameters.score_name].unique()
            self._is_multi_class = len(unique_labels) > 2
        return self._is_multi_class

    def get_accumulated_costs(self):
        """
        Get the expenses that have been accumulated over all the computed elements.

        Returns:
            dict: A dictionary containing only one accumulated expense:
                  'total_cost'
        """

        return {
            "total_cost":  0
        }