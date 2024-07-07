import os
import json
import mlflow
import pandas as pd
import numpy as np
import inspect
import functools
from pydantic import BaseModel, ValidationError, field_validator
from typing import Optional
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
from rich import print as rich_print
from rich.text import Text
from plexus.cli.console import console
from plexus.CustomLogging import logging
from sklearn.preprocessing import LabelBinarizer
from collections import Counter
import xgboost as xgb

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
        data : dict
            Dictionary containing data-related parameters.
        """
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

    class ModelInput(BaseModel):
        """
        Model input data structure.

        Attributes
        ----------
        transcript : str
            The transcript text to be classified.
        """
        transcript: str

    class ModelOutput(BaseModel):
        """
        Model output data structure.

        Attributes
        ----------
        score : str
            The predicted score label.
        """
        score: str
    
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
            self.start_mlflow_experiment_run()
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



    def log_stored_parameters(self):
        """
        Log the stored parameters to MLflow.
        """
        if hasattr(self, '_stored_parameters'):
            for name, value in self.parameters.items():
                mlflow.log_param(name, value)

    def name(self):
        """
        Get the name of the classifier.

        Returns
        -------
        str
            The name of the classifier, which is a combination of the enclosing folder name and the class name.
        """
        subclass_file = inspect.getfile(self.__class__)
        folder_name = os.path.basename(os.path.dirname(subclass_file))
        computed_name = folder_name + "_" + self.__class__.__name__
        logging.info(f"Classifier name: {computed_name}")
        return computed_name

    def start_mlflow_experiment_run(self):
        """
        Start an MLflow experiment run and log common parameters.
        """
        experiment_name = f"{self.parameters.scorecard_name} - {self.parameters.score_name}"
        if os.getenv('MLFLOW_EXPERIMENT_NAME'):
            experiment_name = experiment_name + " - " + os.getenv('MLFLOW_EXPERIMENT_NAME')
        logging.info(f"Setting MLFLow experiment name to [magenta1][b]{experiment_name}[/b][/magenta1]")
        mlflow.set_experiment(experiment_name)

        mlflow_tracking_uri = os.getenv('MLFLOW_TRACKING_URI')
        if mlflow_tracking_uri:
            logging.info(f"Using MLFlow tracking URL: {mlflow_tracking_uri}")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        else:
            mlflow.set_tracking_uri(f'file:///{os.path.abspath("./mlruns")}')

        try:
            mlflow.start_run()
        except Exception as e:
            logging.error(f"Error: {e}")
            logging.info("Attempting to end the previous run and start a new one.")
            mlflow.end_run()
            mlflow.start_run()

        mlflow.log_param("classifier_class", self.__class__.__name__)

        mlflow.log_param("scorecard_name", self.parameters.scorecard_name)
        mlflow.log_param("score_name", self.parameters.score_name)

        self.log_stored_parameters()

    def log_evaluation_metrics(self, metrics):
        """
        Log evaluation metrics to MLflow.

        Parameters
        ----------
        metrics : dict
            Dictionary containing evaluation metrics.
        """
        mlflow.log_metric("accuracy", metrics["accuracy"])
        mlflow.log_metric("precision", metrics["precision"])
        mlflow.log_metric("recall", metrics["recall"])
        mlflow.log_metric("f1_score", metrics["f1_score"])

    def load_data(self, *, queries=None, excel=None):
        """
        Load the specified queries from the training data lake, with caching, into a combined DataFrame in the class instance.

        Parameters
        ----------
        queries : list, optional
            List of queries to load data from the training data lake.
        excel : str, optional
            Path to an Excel file to load data from.
        """
        from plexus.DataCache import DataCache
        data_cache = DataCache(os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME'],
            os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME'],
            os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME'])
        if queries:
            self.dataframe = data_cache.load_dataframe_from_queries(queries=queries)
        elif excel:
            self.dataframe = data_cache.load_dataframe_from_excel(excel=excel)

        console.print(Text("Loaded dataframe from training data lake:", style="royal_blue1"))
        self.analyze_dataset()

    def analyze_dataset(self):
        """
        Analyze the loaded dataset and display various summaries and breakdowns.
        """
        panels = []

        answer_breakdown_table = Table(
            title="[royal_blue1][b]Answer Breakdown[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        answer_breakdown_table.add_column("Answer", justify="right", style="royal_blue1", no_wrap=True)
        answer_breakdown_table.add_column("Count", style="magenta1", justify="right")
        answer_breakdown_table.add_column("Percentage", style="magenta1 bold", justify="right")

        try:
            answer_counts = self.dataframe[self.parameters.score_name].value_counts()
            total_responses = answer_counts.sum()
            for answer_value, count in answer_counts.items():
                percentage_of_total = (count / total_responses) * 100
                formatted_percentage = f"{percentage_of_total:.1f}%"
                answer_breakdown_table.add_row(str(answer_value), str(count), formatted_percentage)
        except KeyError:
            pass

        panels.append(Panel(answer_breakdown_table, border_style="royal_blue1"))

        dataframe_summary_title = "[royal_blue1][b]Dataframe Summary[/b][/royal_blue1]"
        dataframe_summary_table = Table(
            title=dataframe_summary_title,
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        dataframe_summary_table.add_column("Description", justify="right", style="royal_blue1", no_wrap=True)
        dataframe_summary_table.add_column("Value", style="magenta1", justify="right")
        dataframe_summary_table.add_row("Number of Rows", str(self.dataframe.shape[0]), style="magenta1 bold")
        dataframe_summary_table.add_row("Number of Columns", str(self.dataframe.shape[1]))
        dataframe_summary_table.add_row("Total Cells", str(self.dataframe.size))

        if 'answer_counts' in locals():
            smallest_answer_count = answer_counts.min()
            total_kinds_of_non_null_answers = self.dataframe[self.parameters.score_name].nunique()
            total_balanced_count = smallest_answer_count * total_kinds_of_non_null_answers

            dataframe_summary_table.add_row("Smallest Count", str(smallest_answer_count))
            dataframe_summary_table.add_row("Total Balanced Count", str(total_balanced_count), style="magenta1 bold")
        panels.append(Panel(dataframe_summary_table, border_style="royal_blue1"))

        column_names_table = Table(
            title="[royal_blue1][b]Column Names[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        column_names_table.add_column("Column Name", style="magenta1")
        for column_name in self.dataframe.columns:
            column_names_table.add_row(column_name)

        panels.append(Panel(column_names_table, border_style="royal_blue1"))

        columns = Columns(panels)
        header_text = f"[bold royal_blue1]{self.parameters.score_name}[/bold royal_blue1]"

        rich_print(Panel(columns, title=header_text, border_style="magenta1"))

    def process_data(self):
        """
        Handle any pre-processing of the training data, including the training/validation splits.
        """
        if 'processors' in self.parameters.data:
            console.print(Text("Running configured processors...", style="royal_blue1"))

            processors = []
            for processor in self.parameters.data['processors']:
                processor_class = processor['class']
                processor_parameters = processor.get('parameters', {})
                from plexus.processors import ProcessorFactory
                processor_instance = ProcessorFactory.create_processor(processor_class, **processor_parameters)
                processors.append(processor_instance)

            first_transcript_before = self.dataframe["Transcription"].iloc[0]

            for processor in processors:
                self.dataframe = processor.process(self.dataframe)

            first_transcript_after = self.dataframe["Transcription"].iloc[0]

            if first_transcript_before and first_transcript_after:
                first_transcript_before_truncated = first_transcript_before[:1000] + '...'
                first_transcript_after_truncated = first_transcript_after[:1000] + '...'

                transcript_comparison_table = Table(
                    title=f"[royal_blue1][b]Processors[/b][/royal_blue1]",
                    header_style="sky_blue1",
                    border_style="sky_blue1"
                )
                transcript_comparison_table.add_column("Before", style="magenta1", justify="left")
                transcript_comparison_table.add_column("After", style="magenta1", justify="left")
                transcript_comparison_table.add_row(first_transcript_before_truncated, first_transcript_after_truncated)

                console.print(Panel(transcript_comparison_table, border_style="royal_blue1"))

        console.print(Text("Processed dataframe:", style="royal_blue1"))
        self.analyze_dataset()

        before_subsample_count = len(self.dataframe)
        self.dataframe = self.dataframe.sample(frac=self.parameters.data['percentage'] / 100, random_state=42)
        after_subsample_count = len(self.dataframe)

        subsample_comparison_table = Table(
            title=f"[royal_blue1][b]Subsampling {self.parameters.data['percentage']}% of the data[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        subsample_comparison_table.add_column("Before", style="magenta1", justify="left")
        subsample_comparison_table.add_column("After", style="magenta1", justify="left")
        subsample_comparison_table.add_row(str(before_subsample_count), str(after_subsample_count))

        console.print(Panel(subsample_comparison_table, border_style="royal_blue1"))

        if 'balance' in self.parameters.data and not self.parameters.data['balance']:
            logging.info("data->balance: [red][b]false.[/b][/red]  Skipping data balancing.")
            return

        print("\nDistribution of labels in the dataframe:")
        print(self.dataframe[self.parameters.score_name].value_counts(dropna=False))

        unique_labels = self.dataframe[self.parameters.score_name].unique()

        label_dataframes = {label: self.dataframe[self.dataframe[self.parameters.score_name] == label] for label in unique_labels}

        smallest_class_size = min(len(df) for df in label_dataframes.values())

        balanced_dataframes = []
        for label, dataframe in label_dataframes.items():
            print(f"Sampling {smallest_class_size} instances from the '{label}' class...")
            balanced_dataframes.append(dataframe.sample(n=smallest_class_size, random_state=42))

        balanced_dataframe = pd.concat(balanced_dataframes)

        balanced_dataframe = balanced_dataframe.sample(frac=1, random_state=42)

        print("\nDistribution of labels in the balanced dataframe:")
        print(balanced_dataframe[self.parameters.score_name].value_counts())

        self.dataframe = balanced_dataframe

        console.print(Text("Final, balanced dataframe:", style="royal_blue1"))
        self.analyze_dataset()

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

        self._generate_confusion_matrix()
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
    def predict(self, model_input: ModelInput):
        """
        Make predictions on the input data.

        Parameters
        ----------
        model_input : Score.ModelInput
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

    def _generate_confusion_matrix(self):
        """
        Generate and save a confusion matrix plot.
        """
        file_name = self.report_file_name("confusion_matrix.png")

        all_classes = set(self.label_map.values())
        all_classes.update(set(self.val_labels))
        all_classes.update(set(self.val_predictions))
        
        all_classes = set(str(label) for label in all_classes)
        
        sorted_labels = sorted(all_classes)
        
        label_to_int = {label: i for i, label in enumerate(sorted_labels)}
        logging.info(f"Label to int mapping: {label_to_int}")

        val_labels_int = np.array([label_to_int[str(label)] for label in self.val_labels])
        val_predictions_int = np.array([label_to_int[str(pred)] for pred in self.val_predictions])

        relevant_labels = [label_to_int[label] for label in self.label_map.keys()]
        logging.info(f"Relevant labels: {relevant_labels}")
        cm = confusion_matrix(val_labels_int, val_predictions_int, labels=relevant_labels)
        
        plt.figure(figsize=(10, 8))
        custom_colormap = sns.light_palette(self._fuchsia, as_cmap=True)
        sns.heatmap(cm, annot=True, fmt='d', cmap=custom_colormap, 
                    xticklabels=list(self.label_map.keys()), yticklabels=list(self.label_map.keys()))
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.title('Confusion Matrix')

        plt.tight_layout()
        plt.savefig(file_name, dpi=300)
        plt.close()

        mlflow.log_artifact(file_name)
        
        cm_text = np.array2string(cm, separator=', ')
        logging.info(f"Confusion matrix: {cm_text}")

        class_distribution = Counter(self.val_labels)
        logging.info(f"Class distribution in validation set: {dict(class_distribution)}")

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
        scale_pos_weight = self.params.positive_class_weight

        self.model = xgb.XGBClassifier(scale_pos_weight=scale_pos_weight)
        self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)], early_stopping_rounds=10)

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
        decision_threshold = self.params.decision_threshold

        y_proba = self.model.predict_proba(X)[:, 1]

        y_pred = (y_proba >= decision_threshold).astype(int)
        return y_pred

    def _plot_roc_curve(self):
        """
        Generate and save a ROC curve plot.
        """
        file_name = self.report_file_name("roc_curve.png")

        all_classes = set(self.label_map.values())
        all_classes.update(set(self.val_labels))
        all_classes.update(set(self.val_predictions))
        
        all_classes = set(str(label) for label in all_classes)
        
        sorted_labels = sorted(all_classes)
        
        label_to_int = {label: i for i, label in enumerate(sorted_labels)}

        val_labels_int = np.array([label_to_int[str(label)] for label in self.val_labels])

        if self.val_confidence_scores.ndim == 2:
            if self.val_confidence_scores.shape[1] == 1:
                val_confidence_scores = self.val_confidence_scores.ravel()
            else:
                positive_class_index = self.label_map['Yes']
                val_confidence_scores = self.val_confidence_scores[:, positive_class_index]
        else:
            val_confidence_scores = self.val_confidence_scores

        pos_label = label_to_int['Yes']

        fpr, tpr, _ = roc_curve(val_labels_int, val_confidence_scores, pos_label=pos_label)
        roc_auc = auc(fpr, tpr)

        plt.figure(figsize=(10, 8))
        plt.plot(fpr, tpr, color=self._fuchsia, lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
        plt.plot([0, 1], [0, 1], color=self._sky_blue, lw=2, linestyle='--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC) Curve')
        plt.legend(loc="lower right")
        plt.savefig(file_name)
        plt.close()

        mlflow.log_artifact(file_name)
        mlflow.log_metric("roc_auc", roc_auc)

        logging.info(f"Number of unique labels: {len(sorted_labels)}")
        logging.info(f"Shape of val_confidence_scores: {val_confidence_scores.shape}")
        logging.info(f"Shape of val_labels_int: {val_labels_int.shape}")
        logging.info(f"label_to_int mapping: {label_to_int}")

    def _plot_precision_recall_curve(self):
        """
        Generate and save a precision-recall curve plot.
        """
        file_name = self.report_file_name("precision_and_recall_curve.png")

        plt.figure()

        all_classes = set(self.label_map.values())
        all_classes.update(set(self.val_labels))
        all_classes.update(set(self.val_predictions))
        
        all_classes = set(str(label) for label in all_classes)
        
        sorted_labels = sorted(all_classes)
        
        label_to_int = {label: i for i, label in enumerate(sorted_labels)}

        val_labels_int = np.array([label_to_int[str(label)] for label in self.val_labels])
        val_predictions_int = np.array([label_to_int[str(pred)] for pred in self.val_predictions])

        valid_indices = (val_labels_int != -1) & (val_predictions_int != -1)
        val_labels_int = val_labels_int[valid_indices]
        val_predictions_int = val_predictions_int[valid_indices]
        val_confidence_scores = self.val_confidence_scores[valid_indices]

        if self._is_multi_class:
            lb = LabelBinarizer()
            val_labels_one_hot = lb.fit_transform(val_labels_int)
            
            if val_confidence_scores.ndim == 1:
                temp_scores = np.zeros((len(val_confidence_scores), len(label_to_int)))
                temp_scores[np.arange(len(val_predictions_int)), val_predictions_int] = val_confidence_scores
                val_confidence_scores = temp_scores

            n_classes = val_labels_one_hot.shape[1]
            for i in range(n_classes):
                precision, recall, _ = precision_recall_curve(val_labels_one_hot[:, i], val_confidence_scores[:, i])
                pr_auc = auc(recall, precision)
                class_label = list(label_to_int.keys())[list(label_to_int.values()).index(i)]
                plt.plot(recall, precision, lw=2, label=f'Class {class_label} (area = {pr_auc:0.2f})')
        else:
            # Convert binary labels to 0 and 1
            val_labels_binary = (val_labels_int == label_to_int['Yes']).astype(int)
            precision, recall, _ = precision_recall_curve(val_labels_binary, val_confidence_scores)
            pr_auc = auc(recall, precision)
            plt.plot(recall, precision, color=self._sky_blue, lw=2, label='PR curve (area = %0.2f)' % pr_auc)

        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall curve')
        plt.legend(loc="lower left")
        plt.savefig(file_name)
        plt.close()
        mlflow.log_artifact(file_name)
    def _plot_training_history(self):
        """
        Plot and save the training history of the model.

        This method generates a plot of the training history, including learning rate, loss, and accuracy over epochs.
        The plot is saved as a PNG file in the report directory.

        Returns
        -------
        None
        """
        file_name = self.report_file_name("training_history.png")

        plt.figure(figsize=(12, 9))  # Adjusted for a 4x3 aspect ratio with three subplots

        plt.suptitle(f"Training History\n{self.parameters.score_name}", fontsize=16, verticalalignment='top')

        # Learning Rate plot
        plt.subplot(1, 3, 1)  # First subplot for learning rate
        plt.plot(self.history.history['lr'], label='Learning Rate', color=self._fuchsia, lw=4)
        plt.title('Learning Rate')
        plt.ylabel('Learning Rate')
        plt.xlabel('Epoch')
        plt.legend(loc='upper right')
        plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        plt.gca().set_xticklabels(range(1, len(self.history.history['lr']) + 1))

        # Loss plot
        plt.subplot(1, 3, 2)  # Second subplot for loss
        plt.plot(self.history.history['loss'], label='Train Loss', color=self._sky_blue, lw=4)
        plt.plot(self.history.history['val_loss'], label='Validation Loss', color=self._fuchsia, lw=4)
        plt.title('Model Loss')
        plt.ylabel('Loss')
        plt.xlabel('Epoch')
        plt.yscale('log')  # Logarithmic scale for loss
        plt.legend(loc='upper right')
        plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        plt.gca().set_xticklabels(range(1, len(self.history.history['loss']) + 1))

        # Set the loss y-axis to have a fixed locator so it only shows specific ticks, and format them properly.
        plt.gca().yaxis.set_major_locator(ticker.FixedLocator(np.logspace(np.log10(plt.ylim()[0]), np.log10(plt.ylim()[1]), num=5)))
        plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: '{:.2g}'.format(y)))

        # Accuracy plot
        plt.subplot(1, 3, 3)  # Third subplot for accuracy
        plt.plot(self.history.history['accuracy'], label='Train Accuracy', color=self._sky_blue, lw=4)
        plt.plot(self.history.history['val_accuracy'], label='Validation Accuracy', color=self._fuchsia, lw=4)
        plt.title('Model Accuracy')
        plt.ylabel('Accuracy (%)')
        plt.xlabel('Epoch')
        plt.legend(loc='lower right')
        plt.ylim(0.45, 1.0)  # Adjust based on your model's accuracy range
        # Adjust y-axis to show percentages, and format them properly.
        plt.gca().yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0, decimals=0))
        plt.gca().set_xticklabels(range(1, len(self.history.history['accuracy']) + 1))

        # Add horizontal line and label for final validation accuracy
        final_val_accuracy = self.history.history['val_accuracy'][-1]
        plt.axhline(y=final_val_accuracy, color='gray', linestyle='--', lw=2)
        plt.text(len(self.history.history['val_accuracy']) - 1, final_val_accuracy, f'{final_val_accuracy:.3%}', 
                 color='black', ha='right', va='bottom')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(file_name)
        # plt.show()
        mlflow.log_artifact(file_name)

    def _plot_calibration_curve(self, *, target_accuracy=0.90):
        """
        Plot and save the calibration curve of the model.

        This method generates a calibration curve, showing the accuracy of predictions by confidence bucket.
        The plot is saved as a PNG file in the report directory.

        Parameters
        ----------
        target_accuracy : float, optional
            The target accuracy for determining the confidence threshold, by default 0.90

        Returns
        -------
        None
        """
        file_name = self.report_file_name("calibration_curve.png")

        confidences = self.val_confidence_scores.flatten()
        predicted_labels = self.val_predictions
        true_labels = self.val_labels

        logging.info(f"Calibration curve - Unique values in predicted_labels: {set(predicted_labels)}")
        logging.info(f"Calibration curve - Unique values in true_labels: {set(true_labels)}")
        logging.info(f"Calibration curve - label_map: {self.label_map}")

        # Ensure all classes are represented
        all_classes = set(self.label_map.values())
        all_classes.update(set(true_labels))
        all_classes.update(set(predicted_labels))
        
        # Convert all labels to strings
        all_classes = set(str(label) for label in all_classes)
        
        # Create a sorted list of unique labels
        sorted_labels = sorted(all_classes)
        
        # Create label_to_int mapping
        label_to_int = {label: i for i, label in enumerate(sorted_labels)}

        logging.info(f"Calibration curve - label_to_int dictionary: {label_to_int}")

        try:
            predicted_labels_numeric = np.array([label_to_int[str(label)] for label in predicted_labels])
            true_labels_numeric = np.array([label_to_int[str(label)] for label in true_labels])
        except KeyError as e:
            logging.error(f"KeyError encountered: {e}")
            logging.error(f"Label causing the error: {e.args[0]}")
            logging.error(f"All unique labels in predicted_labels: {set(predicted_labels)}")
            logging.error(f"All unique labels in true_labels: {set(true_labels)}")
            raise

        def find_confidence_threshold(confidences, true_labels, predicted_labels, target_accuracy):
            sorted_indices = np.argsort(confidences)
            sorted_confidences = confidences[sorted_indices]
            sorted_true_labels = true_labels[sorted_indices]
            sorted_predicted_labels = predicted_labels[sorted_indices]
            
            for i in range(len(sorted_confidences)):
                remaining_accuracy = np.mean(sorted_predicted_labels[i:] == sorted_true_labels[i:])
                if remaining_accuracy >= target_accuracy:
                    return sorted_confidences[i]
            
            return sorted_confidences[-1]  # Return the highest confidence if target not achievable

        confidence_threshold = find_confidence_threshold(confidences, true_labels_numeric, predicted_labels_numeric, target_accuracy)

        sorted_indices = np.argsort(confidences)
        sorted_confidences = confidences[sorted_indices]
        sorted_predictions = predicted_labels_numeric[sorted_indices]
        sorted_true_labels = true_labels_numeric[sorted_indices]

        n = len(confidences)
        bucket_sizes = [n // 6, n // 3, n - (n // 6) - (n // 3)]

        buckets = []
        start_index = 0
        for size in bucket_sizes:
            end_index = start_index + size

            bucket_confidences = sorted_confidences[start_index:end_index]
            bucket_predictions = sorted_predictions[start_index:end_index]
            bucket_true_labels = sorted_true_labels[start_index:end_index]

            bucket_accuracy = np.mean(bucket_predictions == bucket_true_labels)
            bucket_mean_confidence = np.mean(bucket_confidences)

            buckets.append((bucket_mean_confidence, bucket_accuracy, len(bucket_predictions)))

            start_index = end_index

        plt.figure(figsize=(10, 8))
        plt.plot([0, 1], [0, 1], linestyle='--', color=self._sky_blue, label='Perfectly calibrated')

        bucket_confidences, bucket_accuracies, bucket_sample_counts = zip(*buckets)
        plt.plot(bucket_confidences, bucket_accuracies, label='Model calibration', marker='o', color=self._fuchsia)

        plt.axvline(x=confidence_threshold, color='blue', linestyle='-', label=f'Confidence threshold ({confidence_threshold:.2%})')

        plt.xlabel('Confidence')
        plt.ylabel('Accuracy')
        plt.title('Calibration Curve: Accuracy by Confidence Bucket')
        plt.legend(loc='lower right')

        x_ticks = np.arange(0, 1.1, 0.1)
        plt.xticks(x_ticks)
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.0%}"))

        y_ticks = np.arange(0, 1.1, 0.1)
        plt.yticks(y_ticks)
        plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, p: f"{y:.0%}"))

        plt.ylim(0, 1)
        plt.xlim(0, 1)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.savefig(file_name)
        mlflow.log_artifact(file_name)

        print("\nOverall statistics:")
        print(f"Total samples: {len(confidences)}")
        print(f"Min confidence: {np.min(confidences):.2%}")
        print(f"Max confidence: {np.max(confidences):.2%}")
        print(f"Mean confidence: {np.mean(confidences):.2%}")
        print(f"Overall accuracy: {np.mean(predicted_labels_numeric == true_labels_numeric)::.2%}")
        print(f"\nConfidence threshold for {target_accuracy:.0%} accuracy: {confidence_threshold:.2%}")
        print(f"Predictions above threshold: {np.sum(confidences > confidence_threshold)}")
        print(f"Predictions at or below threshold: {np.sum(confidences <= confidence_threshold)}")
        remaining_predictions = confidences > confidence_threshold
        remaining_accuracy = np.mean(predicted_labels_numeric[remaining_predictions] == true_labels_numeric[remaining_predictions])
        print(f"Accuracy of predictions above threshold: {remaining_accuracy:.2%}")
        predictions_below_threshold = np.sum(confidences <= confidence_threshold)
        percentage_below_threshold = predictions_below_threshold / len(confidences) * 100
        print(f"Percentage of predictions below threshold: {percentage_below_threshold:.2f}%")

        plt.figure(figsize=(10, 6))
        plt.hist(confidences, bins=20, edgecolor='black')
        plt.title('Distribution of Confidences')
        plt.xlabel('Confidence')
        plt.ylabel('Count')
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.0%}"))
        plt.savefig(self.report_file_name("confidence_distribution.png"))
        mlflow.log_artifact(self.report_file_name("confidence_distribution.png"))

        print("\nBucket details:")
        for i, (conf, acc, count) in enumerate(buckets):
            print(f"Bucket {i+1}:")
            print(f"  Confidence range: {conf:.2%}")
            print(f"  Mean confidence: {conf:.2%}")
            print(f"  Accuracy: {acc:.2%}")
            print(f"  Number of samples: {count}")
            
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