import os
import json
import mlflow
import pandas as pd
import numpy as np
import inspect
import functools
from pydantic import BaseModel, ValidationError, field_validator, ConfigDict
from typing import Optional, Union, List, Any
from abc import ABC, abstractmethod
import matplotlib.pyplot as plt
import seaborn as sns
# from tensorflow.keras.utils import plot_model
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

from plexus.Registries import scorecard_registry
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
    Abstract base class for implementing classification and scoring models in Plexus.

    Score is the fundamental building block of classification in Plexus. Each Score
    represents a specific classification task and can be implemented using various
    approaches:

    - Machine learning models (e.g., DeepLearningSemanticClassifier)
    - LLM-based classification (e.g., LangGraphScore)
    - Rule-based systems (e.g., KeywordClassifier)
    - Custom logic (by subclassing Score)

    The Score class provides:
    - Standard input/output interfaces using Pydantic models
    - MLFlow integration for experiment tracking
    - Visualization tools for model performance
    - Cost tracking for API-based models
    - Metrics computation and logging

    Common usage patterns:
    1. Creating a custom classifier:
        class MyClassifier(Score):
            def predict(self, context, model_input: Score.Input) -> Score.Result:
                text = model_input.text
                # Custom classification logic here
                return Score.Result(
                    parameters=self.parameters,
                    value="Yes" if is_positive(text) else "No"
                )

    2. Using in a Scorecard:
        scores:
          MyScore:
            class: MyClassifier
            parameters:
              threshold: 0.8

    3. Training a model:
        classifier = MyClassifier()
        classifier.train_model()
        classifier.evaluate_model()
        classifier.save_model()

    4. Making predictions:
        result = classifier.predict(context, Score.Input(
            text="content to classify",
            metadata={"source": "email"}
        ))

    The Score class is designed to be extended for different classification approaches
    while maintaining a consistent interface for use in Scorecards and Evaluations.
    """

    class SkippedScoreException(Exception):
        """Raised when a score is skipped due to dependency conditions not being met."""
        def __init__(self, score_name: str, reason: str):
            self.score_name = score_name
            self.reason = reason
            super().__init__(f"Score '{score_name}' was skipped: {reason}")

    class Parameters(BaseModel):
        """
        Parameters required for scoring.

        Attributes
        ----------
        data : dict
            Dictionary containing data-related parameters.
        """
        model_config = ConfigDict(protected_namespaces=())
        scorecard_name: Optional[str] = None
        name: Optional[str] = None
        id: Optional[Union[str, int]] = None
        key: Optional[str] = None
        dependencies: Optional[List[dict]] = None
        data: Optional[dict] = None
        number_of_classes: Optional[int] = None
        label_score_name: Optional[str] = None
        label_field: Optional[str] = None

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

    class Input(BaseModel):
        """
        Standard input structure for all Score classifications in Plexus.

        The Input class standardizes how content is passed to Score classifiers,
        supporting both the content itself and contextual metadata. It's used by:
        - Individual Score predictions
        - Batch processing jobs
        - Evaluation runs
        - Dashboard API integrations

        Attributes:
            text: The content to classify. Can be a transcript, document, etc.
            metadata: Additional context like source, timestamps, or tracking IDs
            results: Optional list of previous classification results, used for:
                    - Composite scores that depend on other scores
                    - Multi-step classification pipelines
                    - Score dependency resolution

        Common usage:
        1. Basic classification:
            input = Score.Input(
                text="content to classify",
                metadata={"source": "phone_call"}
            )

        2. With dependencies:
            input = Score.Input(
                text="content to classify",
                metadata={"source": "phone_call"},
                results=[{
                    "name": "PriorScore",
                    "result": prior_score_result
                }]
            )
        """
        model_config = ConfigDict(protected_namespaces=())
        text:     str
        metadata: dict = {}
        results: Optional[List[Any]] = None

    class Result(BaseModel):
        """
        Standard output structure for all Score classifications in Plexus.

        The Result class provides a consistent way to represent classification
        outcomes, supporting both simple yes/no results and complex multi-class
        classifications with explanations. It's used throughout Plexus for:
        - Individual Score results
        - Batch processing outputs
        - Evaluation metrics
        - Dashboard result tracking

        Attributes:
            parameters: Configuration used for this classification
            value: The classification result (e.g., "Yes"/"No" or class label)
            explanation: Detailed explanation of why this result was chosen
            confidence: Confidence score for the classification (0.0 to 1.0)
            metadata: Additional context about the classification
            error: Optional error message if classification failed

        The Result class provides helper methods for common operations:
        - is_yes(): Check if result is affirmative
        - is_no(): Check if result is negative
        - __eq__: Compare results (case-insensitive)

        Common usage:
        1. Basic classification with explanation:
            result = Score.Result(
                parameters=self.parameters,
                value="Yes",
                explanation="Clear greeting found at beginning of transcript",
                confidence=0.95
            )

        2. Classification with metadata:
            result = Score.Result(
                parameters=self.parameters,
                value="No",
                explanation="No greeting found in transcript",
                confidence=0.88,
                metadata={"source": "phone_call"}
            )

        3. Error case:
            result = Score.Result(
                parameters=self.parameters,
                value="ERROR",
                error="API timeout"
            )
        """
        model_config = ConfigDict(protected_namespaces=())
        parameters: 'Score.Parameters'
        value:      Union[str, bool]
        explanation: Optional[str] = None
        confidence:  Optional[float] = None
        metadata:   dict = {}
        error:      Optional[str] = None
        code:       Optional[str] = None

        def __eq__(self, other):
            if isinstance(other, Score.Result):
                return self.value.lower() == other.value.lower()
            elif isinstance(other, str):
                return self.value.lower() == other.lower()
            return NotImplemented
        
        def is_yes(self):
            return self.value.lower() == 'yes'

        def is_no(self):
            return self.value.lower() == 'no'
        
        @property
        def explanation_from_metadata(self) -> Optional[str]:
            """Backwards compatibility: explanation from metadata"""
            return self.metadata.get('explanation') if self.metadata else None
        
        @property
        def confidence_from_metadata(self) -> Optional[float]:
            """Backwards compatibility: confidence from metadata"""
            return self.metadata.get('confidence') if self.metadata else None
        
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
            self._is_multi_class = None
            self._number_of_classes = None
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
        return f"./reports/{self.parameters.scorecard_name}/{self.parameters.name}/".replace(' ', '_')
    def model_directory_path(self):
        return f"./models/{self.parameters.scorecard_name}/{self.parameters.name}/".replace(' ', '_')

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

    def train_model(self):
        """
        Train the model on the training data.

        Returns
        -------
        object
            The trained model.
        """
        pass

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

    def register_model(self):
        """
        Register the model with the model registry.
        """
        pass

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
        # self.model = mlflow.keras.load_model(context.artifacts["model"])

    @abstractmethod
    def predict(self, context, model_input: Input) -> Union[Result, List[Result]]:
        """
        Make predictions on the input data.

        Parameters
        ----------
        context : Any
            Context for the prediction (e.g., MLflow context)
        model_input : Score.Input
            The input data for making predictions.

        Returns
        -------
        Union[Score.Result, List[Score.Result]]
            Either a single Score.Result or a list of Score.Results
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
        This is currently disabled to avoid tensorflow dependency.
        """
        logging.info("Model diagram generation is disabled to avoid tensorflow dependency")

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
            score_name = self.get_label_score_name()
            unique_labels = self.dataframe[score_name].unique()
            self._is_multi_class = len(unique_labels) > 2
        return self._is_multi_class

    @property
    def number_of_classes(self):
        """
        Determine the number of classes for the classification problem.

        This property checks the unique labels in the dataframe to determine the number of classes.

        Returns
        -------
        int
            The number of unique classes.
        """
        if self._number_of_classes is None:
            score_name = self.get_label_score_name()
            unique_labels = self.dataframe[score_name].unique()
            self._number_of_classes = len(unique_labels)
        return self._number_of_classes

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

    def get_label_score_name(self):
        """
        Determine the appropriate score name based on the parameters.

        Returns
        -------
        str
            The determined score name.
        """
        score_name = self.parameters.name
        if hasattr(self.parameters, 'label_score_name') and self.parameters.label_score_name:
            score_name = self.parameters.label_score_name
            logging.info(f"Using label_score_name: {score_name}")
        if hasattr(self.parameters, 'label_field') and self.parameters.label_field:
            score_name = f"{score_name} {self.parameters.label_field}"
        return score_name

    @classmethod
    def from_name(cls, scorecard, score):
        
        scorecard_class = scorecard_registry.get(scorecard)
        if not scorecard_class:
            raise ValueError(f"Scorecard '{scorecard}' not found")
        
        score_parameters = scorecard_class.score_registry.get_properties(score)
        score_class =      scorecard_class.score_registry.get(score)
        
        if not score_class:
            raise ValueError(f"Score '{score}' not found in scorecard '{scorecard}'")
        
        return score_class(**score_parameters)

Score.Result.model_rebuild()